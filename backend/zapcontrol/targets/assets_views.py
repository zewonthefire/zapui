import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, F, OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Asset, Finding, RawZapResult, RiskSnapshot, ScanComparison, ScanJob


def _apply_context_scope(queryset, request):
    project = request.GET.get('project')
    target = request.GET.get('target')
    asset = request.GET.get('asset')
    node = request.GET.get('node')
    profile = request.GET.get('profile')

    if project and project != 'all':
        queryset = queryset.filter(target__project_id=project)
    if target and target != 'all':
        queryset = queryset.filter(target_id=target)
    if asset and asset != 'all' and hasattr(queryset.model, 'asset_id'):
        queryset = queryset.filter(asset_id=asset)
    if node and node != 'all':
        queryset = queryset.filter(scan_job__zap_node_id=node)
    if profile and profile != 'all':
        queryset = queryset.filter(scan_job__profile_id=profile)

    range_value = request.GET.get('range')
    if range_value and range_value != 'all':
        days = int(range_value)
        since = timezone.now() - timedelta(days=days)
        if hasattr(queryset.model, 'last_scanned_at'):
            queryset = queryset.filter(last_scanned_at__gte=since)
        elif hasattr(queryset.model, 'created_at'):
            queryset = queryset.filter(created_at__gte=since)
    return queryset


@login_required
def assets_inventory(request):
    latest_snapshot = RiskSnapshot.objects.filter(asset=OuterRef('pk')).order_by('-created_at')
    previous_snapshot = RiskSnapshot.objects.filter(asset=OuterRef('pk')).order_by('-created_at')[1:2]

    assets_qs = Asset.objects.select_related('target__project').annotate(
        latest_score=Subquery(latest_snapshot.values('risk_score')[:1]),
        previous_score=Subquery(previous_snapshot.values('risk_score')[:1]),
    )
    assets_qs = _apply_context_scope(assets_qs, request)
    assets_qs = assets_qs.order_by('-last_scanned_at', 'name')

    paginator = Paginator(assets_qs, 25)
    page = paginator.get_page(request.GET.get('page', 1))

    sparkline_data = {}
    for item in page.object_list:
        points = list(item.risk_snapshots.order_by('-created_at').values_list('risk_score', flat=True)[:12])
        sparkline_data[item.id] = [float(v) for v in reversed(points)]

    return render(request, 'targets/assets/inventory.html', {'page': page, 'sparkline_data': json.dumps(sparkline_data)})


@login_required
def asset_detail(request, asset_id: int):
    asset = get_object_or_404(Asset.objects.select_related('target__project'), pk=asset_id)
    tab = request.GET.get('tab', 'overview')

    findings = asset.findings.select_related('scan_job').order_by('-last_seen')
    if tab == 'findings':
        for field in ['severity', 'confidence', 'status']:
            value = request.GET.get(field)
            if value:
                findings = findings.filter(**{field: value})

    risk_history = asset.risk_snapshots.select_related('scan_job').order_by('-created_at')[:90]
    scans = ScanJob.objects.filter(target=asset.target).order_by('-created_at')[:50]
    raw_results = RawZapResult.objects.filter(scan_job__target=asset.target).select_related('scan_job').order_by('-fetched_at')[:20]
    comparisons = ScanComparison.objects.filter(asset=asset).select_related('scan_a', 'scan_b').prefetch_related('items').order_by('-created_at')[:20]

    context = {
        'asset': asset,
        'tab': tab,
        'findings': findings[:100],
        'risk_history': risk_history,
        'scans': scans,
        'raw_results': raw_results,
        'comparisons': comparisons,
    }
    return render(request, 'targets/assets/detail.html', context)


@login_required
def raw_results_page(request):
    qs = RawZapResult.objects.select_related('scan_job__project', 'scan_job__target', 'scan_job__profile', 'scan_job__zap_node')
    scan_job_id = request.GET.get('scan_job_id')
    if scan_job_id:
        qs = qs.filter(scan_job_id=scan_job_id)
    qs = qs.order_by('-fetched_at')
    selected = qs.first()
    return render(request, 'targets/assets/raw_results.html', {'results': qs[:100], 'selected': selected})


@login_required
def comparisons_page(request):
    comparisons = ScanComparison.objects.select_related('target', 'asset', 'scan_a', 'scan_b').prefetch_related('items').order_by('-created_at')
    scan_a = request.GET.get('scan_a')
    scan_b = request.GET.get('scan_b')
    if scan_a:
        comparisons = comparisons.filter(scan_a_id=scan_a)
    if scan_b:
        comparisons = comparisons.filter(scan_b_id=scan_b)

    return render(request, 'targets/assets/comparisons.html', {'comparisons': comparisons[:50]})
