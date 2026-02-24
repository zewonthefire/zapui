import time
from datetime import timedelta

import requests
from celery import shared_task
from django.db.models import Count, Q
from django.utils import timezone

from .models import RawZapResult, ScanJob, ScanProfile, ZapNode

RETRYABLE_EXCEPTIONS = (requests.Timeout, requests.ConnectionError)


class ScanOrchestrationError(Exception):
    pass


class ZapApiClient:
    def __init__(self, node: ZapNode):
        self.node = node
        self.base_url = node.base_url.rstrip('/')
        self.apikey = node.api_key

    def _params(self, extra: dict | None = None):
        params = {'apikey': self.apikey} if self.apikey else {}
        if extra:
            params.update(extra)
        return params

    def _get(self, path: str, params: dict | None = None, timeout: int = 20):
        resp = requests.get(f'{self.base_url}{path}', params=self._params(params), timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, params: dict | None = None, timeout: int = 20):
        resp = requests.get(f'{self.base_url}{path}', params=self._params(params), timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def version(self):
        return self._get('/JSON/core/view/version/')

    def start_spider(self, target_url: str):
        payload = self._post('/JSON/spider/action/scan/', {'url': target_url, 'recurse': 'true'})
        return payload.get('scan')

    def spider_status(self, spider_id: str):
        payload = self._get('/JSON/spider/view/status/', {'scanId': spider_id})
        return int(payload.get('status', '0'))

    def start_active_scan(self, target_url: str):
        payload = self._post('/JSON/ascan/action/scan/', {'url': target_url, 'recurse': 'true', 'inScopeOnly': 'false'})
        return payload.get('scan')

    def active_status(self, scan_id: str):
        payload = self._get('/JSON/ascan/view/status/', {'scanId': scan_id})
        return int(payload.get('status', '0'))

    def alerts(self, base_url: str):
        payload = self._get('/JSON/core/view/alerts/', {'baseurl': base_url, 'start': '0', 'count': '9999'}, timeout=60)
        return payload.get('alerts', [])


def _enabled_nodes_qs():
    return ZapNode.objects.filter(enabled=True)


def select_node_for_profile(profile: ScanProfile) -> ZapNode:
    if profile.zap_node_id:
        node = profile.zap_node
        if node and node.enabled and node.status == ZapNode.STATUS_HEALTHY:
            return node
        raise ScanOrchestrationError('Profile-selected ZAP node is not enabled and online.')

    candidate = (
        _enabled_nodes_qs()
        .filter(status=ZapNode.STATUS_HEALTHY)
        .annotate(
            running_jobs=Count('scan_jobs', filter=Q(scan_jobs__status=ScanJob.STATUS_RUNNING)),
        )
        .order_by('running_jobs', 'name')
        .first()
    )
    if candidate:
        return candidate

    fallback = _enabled_nodes_qs().order_by('name').first()
    if fallback:
        return fallback

    raise ScanOrchestrationError('No enabled ZAP node is available.')


def _poll_until_complete(status_getter, identifier: str, timeout_minutes: int):
    deadline = timezone.now() + timedelta(minutes=max(1, timeout_minutes))
    last_status = 0
    while timezone.now() < deadline:
        last_status = status_getter(identifier)
        if last_status >= 100:
            return
        time.sleep(2)
    raise ScanOrchestrationError(f'Scan step timed out at {last_status}% progress.')


@shared_task(bind=True, autoretry_for=RETRYABLE_EXCEPTIONS, retry_backoff=True, retry_jitter=True, max_retries=4)
def start_scan_job(self, scan_job_id: int):
    job = ScanJob.objects.select_related('profile', 'target', 'project').get(pk=scan_job_id)
    if job.status not in {ScanJob.STATUS_PENDING, ScanJob.STATUS_RUNNING}:
        return

    if job.status == ScanJob.STATUS_PENDING:
        node = select_node_for_profile(job.profile)
        job.zap_node = node
        job.status = ScanJob.STATUS_RUNNING
        job.started_at = timezone.now()
        job.error_message = ''
        job.save(update_fields=['zap_node', 'status', 'started_at', 'error_message'])

    node = job.zap_node
    client = ZapApiClient(node)

    try:
        client.version()

        if job.profile.scan_type == ScanProfile.TYPE_API_SCAN:
            job.status = ScanJob.STATUS_FAILED
            job.completed_at = timezone.now()
            job.error_message = 'API scan is not implemented yet.'
            job.save(update_fields=['status', 'completed_at', 'error_message'])
            return

        if job.profile.spider_enabled:
            spider_id = client.start_spider(job.target.base_url)
            if not spider_id:
                raise ScanOrchestrationError('ZAP spider did not return a scan identifier.')
            job.zap_spider_id = str(spider_id)
            job.save(update_fields=['zap_spider_id'])
            _poll_until_complete(client.spider_status, job.zap_spider_id, job.profile.max_duration_minutes)

        ascan_id = client.start_active_scan(job.target.base_url)
        if not ascan_id:
            raise ScanOrchestrationError('ZAP active scan did not return a scan identifier.')
        job.zap_ascan_id = str(ascan_id)
        job.save(update_fields=['zap_ascan_id'])
        _poll_until_complete(client.active_status, job.zap_ascan_id, job.profile.max_duration_minutes)

        alerts = client.alerts(job.target.base_url)
        RawZapResult.objects.create(scan_job=job, raw_alerts=alerts)

        job.status = ScanJob.STATUS_COMPLETED
        job.completed_at = timezone.now()
        job.error_message = ''
        job.save(update_fields=['status', 'completed_at', 'error_message'])
    except RETRYABLE_EXCEPTIONS as exc:
        if self.request.retries >= self.max_retries:
            job.status = ScanJob.STATUS_FAILED
            job.completed_at = timezone.now()
            job.error_message = f'Node connectivity failure: {exc}'
            job.save(update_fields=['status', 'completed_at', 'error_message'])
        raise
    except Exception as exc:
        job.status = ScanJob.STATUS_FAILED
        job.completed_at = timezone.now()
        job.error_message = str(exc)
        job.save(update_fields=['status', 'completed_at', 'error_message'])
        raise
