from __future__ import annotations

import hashlib
import json
import time
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone

from .models import RawZapResult, Report, ScanJob, ScanProfile, ScanRun, ZapNode
from .reports import generate_scan_report
from .risk import create_risk_snapshots, normalize_alerts_to_findings
from .zap_client import ZapClient, ZapClientError


class ScanEngineError(Exception):
    pass


def choose_node(scan_job: ScanJob) -> ZapNode:
    if scan_job.node_strategy == ScanJob.NODE_PINNED and scan_job.zap_node_id:
        return scan_job.zap_node

    node = (
        ZapNode.objects.filter(enabled=True, is_active=True)
        .annotate(running=Count('runs', filter=Q(runs__status=ScanRun.STATUS_RUNNING)))
        .filter(running__lt=F('max_concurrent'))
        .order_by('running', 'name')
        .first()
    )
    if not node:
        raise ScanEngineError('No active ZAP node with available concurrency.')
    return node


def claim_queued_run() -> ScanRun | None:
    with transaction.atomic():
        run = (
            ScanRun.objects.select_for_update(skip_locked=True)
            .filter(status=ScanRun.STATUS_QUEUED)
            .select_related('scan_job__target', 'scan_job__profile', 'scan_job__project')
            .order_by('created_at')
            .first()
        )
        if not run:
            return None
        if not run.zap_node_id:
            run.zap_node = choose_node(run.scan_job)
        run.status = ScanRun.STATUS_RUNNING
        run.started_at = timezone.now()
        run.save(update_fields=['zap_node', 'status', 'started_at'])
        return run


def _poll(fn, ident: str, timeout_minutes: int, progress_setter=None):
    deadline = timezone.now() + timedelta(minutes=max(1, timeout_minutes))
    last = 0
    while timezone.now() < deadline:
        last = int(fn(ident))
        if progress_setter:
            progress_setter(last)
        if last >= 100:
            return
        time.sleep(2)
    raise ScanEngineError(f'Timed out at {last}%')


def execute_run(run: ScanRun):
    job = run.scan_job
    node = run.zap_node
    # Safety guardrail: Only scan targets you own or have explicit permission to test.
    client = ZapClient(node.base_url, api_key=node.api_key)
    profile: ScanProfile = job.profile
    try:
        client.version()
        spider_id = None
        if profile.spider_enabled:
            spider_id = client.start_spider(job.target.base_url)
            _poll(
                client.spider_status,
                spider_id,
                profile.max_duration_minutes,
                progress_setter=lambda p: ScanRun.objects.filter(pk=run.pk).update(spider_progress=p),
            )

        ascan_id = client.start_active_scan(job.target.base_url)
        _poll(
            client.active_scan_status,
            ascan_id,
            profile.max_duration_minutes,
            progress_setter=lambda p: ScanRun.objects.filter(pk=run.pk).update(ascan_progress=p),
        )

        alerts = client.alerts(job.target.base_url)
        payload = {'alerts': alerts, 'spider_id': spider_id, 'ascan_id': ascan_id}
        encoded = json.dumps(payload, sort_keys=True).encode()
        RawZapResult.objects.create(
            scan_job=job,
            scan_run=run,
            payload=payload,
            raw_alerts=alerts,
            metadata={'source': 'zap_api', 'node': node.name},
            size_bytes=len(encoded),
            checksum=hashlib.sha256(encoded).hexdigest(),
        )

        normalize_alerts_to_findings(job, alerts, scan_run=run)
        create_risk_snapshots(job, scan_run=run)

        client.html_report()
        report = generate_scan_report(job)
        if report.scan_run_id != run.id:
            report.scan_run = run
            report.save(update_fields=['scan_run'])
        run.logs = f'Completed spider={spider_id} ascan={ascan_id} alerts={len(alerts)}'
        run.status = ScanRun.STATUS_SUCCEEDED
    except (ZapClientError, ScanEngineError) as exc:
        run.status = ScanRun.STATUS_FAILED
        run.error_message = str(exc)
    finally:
        run.finished_at = timezone.now()
        if run.started_at:
            run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)
        run.save(update_fields=['status', 'error_message', 'logs', 'finished_at', 'duration_ms'])


def schedule_due_jobs(now=None) -> int:
    now = now or timezone.now()
    created = 0
    for job in ScanJob.objects.filter(enabled=True):
        due = False
        if job.schedule_type == ScanJob.SCHEDULE_MANUAL:
            continue
        if job.schedule_type == ScanJob.SCHEDULE_INTERVAL and job.schedule_interval_minutes:
            due = not job.last_scheduled_at or (now - job.last_scheduled_at).total_seconds() >= job.schedule_interval_minutes * 60
        elif job.schedule_type == ScanJob.SCHEDULE_DAILY and job.schedule_time:
            due = now.time().hour == job.schedule_time.hour and now.time().minute == job.schedule_time.minute
        elif job.schedule_type == ScanJob.SCHEDULE_WEEKLY and job.schedule_time is not None and job.schedule_weekday is not None:
            due = now.weekday() == job.schedule_weekday and now.time().hour == job.schedule_time.hour and now.time().minute == job.schedule_time.minute
        if due:
            ScanRun.objects.create(scan_job=job, status=ScanRun.STATUS_QUEUED)
            job.last_scheduled_at = now
            job.save(update_fields=['last_scheduled_at'])
            created += 1
    return created


def enqueue_scan(scan_job_id: int) -> ScanRun:
    job = ScanJob.objects.get(pk=scan_job_id)
    return ScanRun.objects.create(scan_job=job, status=ScanRun.STATUS_QUEUED)
