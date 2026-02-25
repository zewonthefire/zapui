from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Avg, Count, Max, Min, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from targets.models import (
    Finding,
    FindingInstance,
    Project,
    RawZapResult,
    RiskSnapshot,
    ScanComparison,
    ScanJob,
    ScanProfile,
    Target,
    ZapNode,
)


@dataclass(frozen=True)
class DashboardFilters:
    project_id: int | None
    target_id: int | None
    asset_id: int | None
    node_id: int | None
    profile_id: int | None
    range_key: str
    scan_id: str
    start_at: timezone.datetime


RANGE_TO_DAYS = {
    '7d': 7,
    '30d': 30,
    '90d': 90,
}


def parse_filters(params) -> DashboardFilters:
    def _to_int(value):
        if not value or value == 'all':
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    range_key = params.get('range', '30d')
    if range_key not in RANGE_TO_DAYS and range_key != 'custom':
        range_key = '30d'

    if range_key == 'custom':
        start_raw = params.get('start')
        try:
            start_at = timezone.datetime.fromisoformat(start_raw)
            if timezone.is_naive(start_at):
                start_at = timezone.make_aware(start_at)
        except Exception:
            start_at = timezone.now() - timedelta(days=30)
    else:
        start_at = timezone.now() - timedelta(days=RANGE_TO_DAYS[range_key])

    return DashboardFilters(
        project_id=_to_int(params.get('project_id')),
        target_id=_to_int(params.get('target_id')),
        asset_id=_to_int(params.get('asset_id')),
        node_id=_to_int(params.get('node_id')),
        profile_id=_to_int(params.get('profile_id')),
        range_key=range_key,
        scan_id=params.get('scan_id', 'latest') or 'latest',
        start_at=start_at,
    )


def _scoped_scan_jobs(filters: DashboardFilters):
    qs = ScanJob.objects.select_related('project', 'target', 'profile', 'zap_node')
    if filters.project_id:
        qs = qs.filter(project_id=filters.project_id)
    if filters.target_id:
        qs = qs.filter(target_id=filters.target_id)
    if filters.asset_id:
        qs = qs.filter(target_id=filters.asset_id)
    if filters.node_id:
        qs = qs.filter(zap_node_id=filters.node_id)
    if filters.profile_id:
        qs = qs.filter(profile_id=filters.profile_id)
    return qs


def _scoped_targets(filters: DashboardFilters):
    qs = Target.objects.select_related('project')
    if filters.project_id:
        qs = qs.filter(project_id=filters.project_id)
    if filters.target_id:
        qs = qs.filter(id=filters.target_id)
    if filters.asset_id:
        qs = qs.filter(id=filters.asset_id)
    return qs


def _scoped_findings(filters: DashboardFilters):
    qs = Finding.objects.select_related('target', 'target__project', 'scan_job')
    if filters.project_id:
        qs = qs.filter(target__project_id=filters.project_id)
    if filters.target_id:
        qs = qs.filter(target_id=filters.target_id)
    if filters.asset_id:
        qs = qs.filter(target_id=filters.asset_id)
    if filters.node_id:
        qs = qs.filter(scan_job__zap_node_id=filters.node_id)
    if filters.profile_id:
        qs = qs.filter(scan_job__profile_id=filters.profile_id)
    return qs


def _scoped_snapshots(filters: DashboardFilters):
    qs = RiskSnapshot.objects.select_related('project', 'target', 'scan_job')
    if filters.project_id:
        qs = qs.filter(Q(project_id=filters.project_id) | Q(target__project_id=filters.project_id))
    if filters.target_id:
        qs = qs.filter(target_id=filters.target_id)
    if filters.asset_id:
        qs = qs.filter(target_id=filters.asset_id)
    if filters.node_id:
        qs = qs.filter(scan_job__zap_node_id=filters.node_id)
    if filters.profile_id:
        qs = qs.filter(scan_job__profile_id=filters.profile_id)
    return qs


def filter_signature(filters: DashboardFilters) -> str:
    return ':'.join(
        str(x)
        for x in [
            filters.project_id,
            filters.target_id,
            filters.asset_id,
            filters.node_id,
            filters.profile_id,
            filters.range_key,
            filters.scan_id,
            filters.start_at.date().isoformat(),
        ]
    )


def _cache_get_or_set(name: str, filters: DashboardFilters, producer):
    key = f'dashboard:{name}:{filter_signature(filters)}'
    data = cache.get(key)
    if data is None:
        data = producer()
        cache.set(key, data, 120)
    return data


def get_context_options(filters: DashboardFilters):
    projects = Project.objects.order_by('name').values('id', 'name')

    targets_qs = Target.objects.order_by('name')
    if filters.project_id:
        targets_qs = targets_qs.filter(project_id=filters.project_id)

    assets_qs = targets_qs
    if filters.target_id:
        assets_qs = assets_qs.filter(id=filters.target_id)

    scan_jobs = _scoped_scan_jobs(filters)
    if filters.asset_id:
        scan_jobs = scan_jobs.filter(target_id=filters.asset_id)

    node_ids = scan_jobs.exclude(zap_node_id__isnull=True).values_list('zap_node_id', flat=True).distinct()
    profile_ids = scan_jobs.values_list('profile_id', flat=True).distinct()
    scan_run_options = scan_jobs.order_by('-created_at').values('id', 'created_at')[:50]

    return {
        'projects': list(projects),
        'targets': list(targets_qs.values('id', 'name', 'project_id')),
        'assets': list(assets_qs.values('id', 'name', 'project_id')),
        'nodes': list(ZapNode.objects.filter(id__in=node_ids).values('id', 'name')),
        'profiles': list(ScanProfile.objects.filter(id__in=profile_ids).values('id', 'name')),
        'scan_runs': [
            {'id': row['id'], 'label': f"#{row['id']} ({row['created_at'].strftime('%Y-%m-%d %H:%M')})"}
            for row in scan_run_options
        ],
    }


def get_overview_data(filters: DashboardFilters):
    def _compute():
        snapshots = _scoped_snapshots(filters).order_by('-created_at')
        findings = _scoped_findings(filters)
        jobs_in_range = _scoped_scan_jobs(filters).filter(created_at__gte=filters.start_at)

        latest_snapshot = snapshots.first()
        previous_snapshot = snapshots[1] if snapshots.count() > 1 else None
        current_risk = float(latest_snapshot.risk_score) if latest_snapshot else 0
        previous_risk = float(previous_snapshot.risk_score) if previous_snapshot else 0

        severities = {
            'high': findings.filter(severity__iexact='High').count(),
            'medium': findings.filter(severity__iexact='Medium').count(),
            'low': findings.filter(severity__iexact='Low').count(),
        }
        new_findings = findings.filter(first_seen__gte=filters.start_at).count()

        scoped_targets = _scoped_targets(filters)
        scanned_target_ids = jobs_in_range.values_list('target_id', flat=True).distinct()
        total_assets = scoped_targets.count() or 1
        coverage_pct = round((len(set(scanned_target_ids)) / total_assets) * 100, 2)

        completed = jobs_in_range.filter(status=ScanJob.STATUS_COMPLETED).count()
        total_jobs = jobs_in_range.count() or 1
        success_rate = round((completed / total_jobs) * 100, 2)

        risk_trend = list(
            _scoped_snapshots(filters)
            .filter(created_at__gte=filters.start_at)
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(avg_risk=Avg('risk_score'))
            .order_by('day')
        )

        new_by_day = (
            findings.filter(first_seen__gte=filters.start_at)
            .annotate(day=TruncDate('first_seen'))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )
        resolved_by_day = (
            findings.filter(last_seen__gte=filters.start_at)
            .annotate(day=TruncDate('last_seen'))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )

        top_assets = list(
            _scoped_snapshots(filters)
            .values('target_id', 'target__name')
            .annotate(max_risk=Max('risk_score'))
            .order_by('-max_risk')[:10]
        )

        failed_jobs = list(jobs_in_range.filter(status=ScanJob.STATUS_FAILED).values('id', 'target__name', 'error_message')[:10])

        return {
            'kpis': {
                'current_risk_score': current_risk,
                'risk_delta': round(current_risk - previous_risk, 2),
                'open_findings': severities,
                'new_findings': new_findings,
                'coverage_pct': coverage_pct,
                'scan_success_rate': success_rate,
            },
            'risk_trend': [{'day': row['day'], 'value': float(row['avg_risk'])} for row in risk_trend],
            'findings_trend': {
                'new': list(new_by_day),
                'resolved': list(resolved_by_day),
            },
            'top_assets_by_risk': top_assets,
            'since_last_scan': {
                'new_high': list(findings.filter(first_seen__gte=filters.start_at, severity__in=['High', 'Critical']).values('id', 'title', 'target__name')[:10]),
                'risk_regressions': top_assets[:5],
                'failed_scan_jobs': failed_jobs,
            },
        }

    return _cache_get_or_set('overview', filters, _compute)


def get_risk_data(filters: DashboardFilters):
    def _compute():
        rows = list(
            _scoped_targets(filters)
            .values('project__name', 'name', 'id')
            .annotate(current_risk=Max('risk_snapshots__risk_score'), min_risk=Min('risk_snapshots__risk_score'))
            .order_by('-current_risk')
        )
        for row in rows:
            current = float(row['current_risk'] or 0)
            minimum = float(row['min_risk'] or 0)
            row['delta'] = round(current - minimum, 2)
        return {
            'rows': rows,
            'most_improved': sorted(rows, key=lambda x: x['delta'])[:5],
            'most_degraded': sorted(rows, key=lambda x: x['delta'], reverse=True)[:5],
        }

    return _cache_get_or_set('risk', filters, _compute)


def get_findings_data(filters: DashboardFilters):
    def _compute():
        findings = _scoped_findings(filters)
        top_by_severity = list(findings.values('severity').annotate(count=Count('id')).order_by('-count'))
        top_by_confidence = list(findings.values('instances__evidence').annotate(count=Count('id')).order_by('-count')[:5])

        now = timezone.now()
        aging = {
            'gt_7d': findings.filter(last_seen__lte=now - timedelta(days=7)).count(),
            'gt_30d': findings.filter(last_seen__lte=now - timedelta(days=30)).count(),
            'gt_90d': findings.filter(last_seen__lte=now - timedelta(days=90)).count(),
        }
        recurrence = list(
            findings.values('title').annotate(scan_hits=Count('instances__scan_job', distinct=True)).order_by('-scan_hits')[:10]
        )
        return {
            'top_by_severity': top_by_severity,
            'top_by_confidence': top_by_confidence,
            'aging_buckets': aging,
            'recurrence': recurrence,
        }

    return _cache_get_or_set('findings', filters, _compute)


def get_coverage_data(filters: DashboardFilters):
    def _compute():
        jobs = _scoped_scan_jobs(filters)
        stale_30 = list(_scoped_targets(filters).exclude(scan_jobs__created_at__gte=timezone.now() - timedelta(days=30)).values('id', 'name')[:50])
        stale_60 = list(_scoped_targets(filters).exclude(scan_jobs__created_at__gte=timezone.now() - timedelta(days=60)).values('id', 'name')[:50])
        stale_90 = list(_scoped_targets(filters).exclude(scan_jobs__created_at__gte=timezone.now() - timedelta(days=90)).values('id', 'name')[:50])

        by_profile = list(jobs.values('profile__name').annotate(scan_count=Count('id')).order_by('-scan_count'))
        node_rates = list(
            jobs.values('zap_node__name')
            .annotate(total=Count('id'), success=Count('id', filter=Q(status=ScanJob.STATUS_COMPLETED)))
            .order_by('-total')
        )
        for row in node_rates:
            total = row['total'] or 1
            row['success_rate'] = round((row['success'] / total) * 100, 2)

        duration_rows = jobs.exclude(started_at__isnull=True).exclude(completed_at__isnull=True).values('profile__name', 'started_at', 'completed_at')
        duration_accumulator: dict[str, list[float]] = {}
        for row in duration_rows:
            key = row['profile__name'] or 'Unknown'
            duration = (row['completed_at'] - row['started_at']).total_seconds()
            duration_accumulator.setdefault(key, []).append(duration)
        avg_duration_by_profile = [
            {'profile__name': profile, 'avg_duration_seconds': round(sum(values) / len(values), 2)}
            for profile, values in duration_accumulator.items()
        ]

        return {
            'not_scanned': {'d30': stale_30, 'd60': stale_60, 'd90': stale_90},
            'scan_frequency_by_profile': by_profile,
            'node_success_rates': node_rates,
            'avg_scan_duration_by_profile': avg_duration_by_profile,
        }

    return _cache_get_or_set('coverage', filters, _compute)


def get_changes_data(filters: DashboardFilters):
    def _compute():
        comparisons = ScanComparison.objects.select_related('target', 'from_scan_job', 'to_scan_job')
        if filters.project_id:
            comparisons = comparisons.filter(target__project_id=filters.project_id)
        if filters.target_id:
            comparisons = comparisons.filter(target_id=filters.target_id)
        if filters.asset_id:
            comparisons = comparisons.filter(target_id=filters.asset_id)

        selected = None
        if filters.scan_id != 'latest':
            try:
                scan_id = int(filters.scan_id)
                selected = comparisons.filter(to_scan_job_id=scan_id).first()
            except ValueError:
                selected = None
        if selected is None:
            selected = comparisons.first()

        if not selected:
            return {'counts': {'new': 0, 'resolved': 0, 'regressed': 0}, 'diff_feed': [], 'scan_options': []}

        diff_feed = list(
            Finding.objects.filter(id__in=selected.new_finding_ids)
            .values('id', 'title', 'severity', 'target__name')
            .order_by('-severity', 'title')[:50]
        )
        return {
            'counts': {
                'new': len(selected.new_finding_ids),
                'resolved': len(selected.resolved_finding_ids),
                'regressed': max(len(selected.new_finding_ids) - len(selected.resolved_finding_ids), 0),
            },
            'diff_feed': diff_feed,
            'selected_comparison': {
                'id': selected.id,
                'from_scan_job_id': selected.from_scan_job_id,
                'to_scan_job_id': selected.to_scan_job_id,
                'risk_delta': float(selected.risk_delta),
            },
        }

    return _cache_get_or_set('changes', filters, _compute)


def get_operations_data(filters: DashboardFilters):
    def _compute():
        jobs = _scoped_scan_jobs(filters)
        running = list(jobs.filter(status=ScanJob.STATUS_RUNNING).values('id', 'target__name', 'created_at')[:25])
        queued = list(jobs.filter(status=ScanJob.STATUS_PENDING).values('id', 'target__name', 'created_at')[:25])
        failed = list(jobs.filter(status=ScanJob.STATUS_FAILED).values('id', 'target__name', 'error_message', 'created_at')[:25])

        node_pool = list(
            ZapNode.objects.values('id', 'name', 'status', 'last_health_check', 'last_latency_ms', 'enabled').order_by('name')
        )
        raw_ingestion = {
            'total_raw_results': RawZapResult.objects.count(),
            'results_in_scope': RawZapResult.objects.filter(scan_job__in=jobs).count(),
        }

        return {
            'running_scans': running,
            'queue': queued,
            'failed_scans': failed,
            'node_pool_status': node_pool,
            'raw_ingestion_status': raw_ingestion,
        }

    return _cache_get_or_set('operations', filters, _compute)
