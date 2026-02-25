import hashlib
import json
from collections import Counter
from decimal import Decimal

from django.db import models
from django.utils import timezone

from core.models import Setting

from .models import Asset, Finding, FindingInstance, RiskSnapshot, ScanComparison, ScanComparisonItem, ScanJob

DEFAULT_RISK_WEIGHTS = {
    'High': 10,
    'Medium': 5,
    'Low': 1,
    'Info': 0,
}

CONFIDENCE_MULTIPLIERS = {
    'high': Decimal('1.0'),
    'medium': Decimal('0.8'),
    'low': Decimal('0.6'),
    'confirmed': Decimal('1.0'),
    'false positive': Decimal('0.0'),
}

SEVERITY_ALIASES = {
    'high': 'High',
    'medium': 'Medium',
    'low': 'Low',
    'informational': 'Info',
    'info': 'Info',
}


def normalize_severity(value: str | None) -> str:
    if not value:
        return 'Info'
    return SEVERITY_ALIASES.get(str(value).strip().lower(), 'Info')


def get_risk_weights() -> dict[str, int]:
    setting = Setting.objects.filter(key='risk_weights').first()
    configured = setting.value if setting else {}
    weights = DEFAULT_RISK_WEIGHTS.copy()
    for key, val in (configured or {}).items():
        normalized_key = normalize_severity(key)
        try:
            weights[normalized_key] = max(0, int(val))
        except (TypeError, ValueError):
            continue
    return weights


def build_finding_fingerprint(alert: dict) -> str:
    parts = [
        str(alert.get('pluginId') or alert.get('alertId') or '').strip(),
        str(alert.get('url') or '').strip().lower(),
        str(alert.get('param') or '').strip().lower(),
        str(alert.get('method') or '').strip().upper(),
        str(alert.get('evidence') or alert.get('instance') or '').strip().lower(),
    ]
    payload = '|'.join(parts)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def compute_risk_score(findings: list[dict] | models.QuerySet, weights: dict[str, int] | None = None) -> tuple[Decimal, dict[str, int]]:
    active_weights = weights or get_risk_weights()
    severity_counts = Counter({key: 0 for key in DEFAULT_RISK_WEIGHTS.keys()})
    total = Decimal('0')

    for finding in findings:
        if isinstance(finding, dict):
            severity = normalize_severity(finding.get('severity') or finding.get('risk'))
            confidence = str(finding.get('confidence') or 'medium').lower()
        else:
            severity = normalize_severity(finding.severity)
            confidence = str(finding.confidence or 'medium').lower()

        severity_counts[severity] += 1
        multiplier = CONFIDENCE_MULTIPLIERS.get(confidence, Decimal('0.8'))
        total += Decimal(active_weights.get(severity, 0)) * multiplier

    return total.quantize(Decimal('0.01')), dict(severity_counts)


def _extract_asset_key(alert: dict) -> tuple[str, str]:
    url = str(alert.get('url') or '').strip()
    if url:
        return (url, Asset.TYPE_URL)
    host = str(alert.get('host') or '').strip()
    if host:
        return (host, Asset.TYPE_HOST)
    return ('unknown-asset', Asset.TYPE_APP)


def normalize_alerts_to_findings(scan_job: ScanJob, alerts: list[dict]) -> None:
    now = timezone.now()
    touched_asset_ids = set()

    for alert in alerts:
        asset_name, asset_type = _extract_asset_key(alert)
        asset, _ = Asset.objects.get_or_create(
            target=scan_job.target,
            name=asset_name,
            asset_type=asset_type,
            defaults={'uri': asset_name if asset_type == Asset.TYPE_URL else ''},
        )

        fingerprint = build_finding_fingerprint(alert)
        finding, created = Finding.objects.get_or_create(
            target=scan_job.target,
            asset=asset,
            zap_plugin_id=str(alert.get('pluginId', '')).strip() or 'unknown',
            title=str(alert.get('alert', '')).strip() or 'Untitled Alert',
            fingerprint=fingerprint,
            defaults={
                'scan_job': scan_job,
                'severity': normalize_severity(alert.get('risk')),
                'confidence': str(alert.get('confidence') or 'Medium'),
                'description': alert.get('description', '') or '',
                'solution': alert.get('solution', '') or '',
                'reference': alert.get('reference', '') or '',
                'cwe_id': str(alert.get('cweid', '') or ''),
                'wasc_id': str(alert.get('wascid', '') or ''),
                'status': Finding.STATUS_OPEN,
                'raw_result_ref': {
                    'url': alert.get('url'),
                    'instance': alert.get('instance'),
                    'pluginId': alert.get('pluginId'),
                },
                'first_seen': now,
                'last_seen': now,
            },
        )

        if not created:
            finding.scan_job = scan_job
            finding.asset = asset
            finding.severity = normalize_severity(alert.get('risk'))
            finding.confidence = str(alert.get('confidence') or finding.confidence)
            finding.last_seen = now
            finding.raw_result_ref = {
                'url': alert.get('url'),
                'instance': alert.get('instance'),
                'pluginId': alert.get('pluginId'),
            }
            finding.save(update_fields=['scan_job', 'asset', 'severity', 'confidence', 'last_seen', 'raw_result_ref'])

        instance, _ = FindingInstance.objects.get_or_create(
            finding=finding,
            scan_job=scan_job,
            url=alert.get('url', '') or '',
            parameter=alert.get('param', '') or '',
            evidence=alert.get('evidence', '') or '',
            defaults={
                'attack': alert.get('attack', '') or '',
                'other': alert.get('other', '') or '',
                'method': alert.get('method', '') or '',
            },
        )
        touched_asset_ids.add(asset.id)
        finding.instances_count = finding.instances.filter(scan_job=scan_job).count()
        finding.save(update_fields=['instances_count'])

    for asset in Asset.objects.filter(id__in=touched_asset_ids):
        _refresh_asset_aggregates(asset, scan_job)


def _refresh_asset_aggregates(asset: Asset, scan_job: ScanJob) -> None:
    findings_qs = asset.findings.filter(status=Finding.STATUS_OPEN)
    score, counts = compute_risk_score(findings_qs)
    asset.scan_count = ScanJob.objects.filter(target=asset.target, status=ScanJob.STATUS_COMPLETED).count()
    asset.last_scanned_at = scan_job.completed_at or timezone.now()
    asset.last_scan_status = scan_job.status
    asset.current_risk_score = score
    asset.findings_open_count_by_sev = counts
    asset.save(
        update_fields=['scan_count', 'last_scanned_at', 'last_scan_status', 'current_risk_score', 'findings_open_count_by_sev', 'updated_at']
    )


def create_risk_snapshots(scan_job: ScanJob):
    # Asset-level snapshots
    for asset in Asset.objects.filter(target=scan_job.target):
        findings = asset.findings.filter(status=Finding.STATUS_OPEN)
        score, counts = compute_risk_score(findings)
        RiskSnapshot.objects.create(
            asset=asset,
            target=scan_job.target,
            scan_job=scan_job,
            risk_score=score,
            counts_by_severity=counts,
            breakdown={'weights': get_risk_weights()},
        )

    target_findings = Finding.objects.filter(target=scan_job.target, status=Finding.STATUS_OPEN)
    target_score, target_counts = compute_risk_score(target_findings)
    RiskSnapshot.objects.create(
        target=scan_job.target,
        scan_job=scan_job,
        risk_score=target_score,
        counts_by_severity=target_counts,
        breakdown={'weights': get_risk_weights()},
    )

    project_findings = Finding.objects.filter(target__project=scan_job.project, status=Finding.STATUS_OPEN)
    project_score, project_counts = compute_risk_score(project_findings)
    RiskSnapshot.objects.create(
        project=scan_job.project,
        scan_job=scan_job,
        risk_score=project_score,
        counts_by_severity=project_counts,
        breakdown={'weights': get_risk_weights()},
    )


def _finding_map_for_scan(scan_job: ScanJob, asset_id: int | None = None) -> dict[str, Finding]:
    qs = Finding.objects.filter(scan_job=scan_job)
    if asset_id:
        qs = qs.filter(asset_id=asset_id)
    return {item.fingerprint: item for item in qs if item.fingerprint}


def build_scan_comparison(scan_a: ScanJob, scan_b: ScanJob, asset: Asset | None = None) -> ScanComparison:
    a_map = _finding_map_for_scan(scan_a, asset.id if asset else None)
    b_map = _finding_map_for_scan(scan_b, asset.id if asset else None)

    a_keys, b_keys = set(a_map.keys()), set(b_map.keys())
    new_keys = sorted(b_keys - a_keys)
    resolved_keys = sorted(a_keys - b_keys)
    changed_keys = sorted(k for k in (a_keys & b_keys) if (a_map[k].severity != b_map[k].severity or a_map[k].confidence != b_map[k].confidence))

    scope = ScanComparison.SCOPE_ASSET if asset else ScanComparison.SCOPE_TARGET
    comparison, _ = ScanComparison.objects.update_or_create(
        target=scan_b.target,
        asset=asset,
        from_scan_job=scan_a,
        to_scan_job=scan_b,
        defaults={
            'scan_a': scan_a,
            'scan_b': scan_b,
            'scope': scope,
            'new_finding_ids': list(Finding.objects.filter(fingerprint__in=new_keys, scan_job=scan_b).values_list('id', flat=True)),
            'resolved_finding_ids': list(Finding.objects.filter(fingerprint__in=resolved_keys, scan_job=scan_a).values_list('id', flat=True)),
            'summary': {'new': len(new_keys), 'resolved': len(resolved_keys), 'changed': len(changed_keys)},
        },
    )

    snap_a = RiskSnapshot.objects.filter(scan_job=scan_a, asset=asset if asset else None, target=scan_a.target if not asset else scan_a.target).first()
    snap_b = RiskSnapshot.objects.filter(scan_job=scan_b, asset=asset if asset else None, target=scan_b.target if not asset else scan_b.target).first()
    comparison.risk_delta = (snap_b.risk_score if snap_b else Decimal('0')) - (snap_a.risk_score if snap_a else Decimal('0'))
    comparison.save(update_fields=['risk_delta'])

    comparison.items.all().delete()
    batch = []
    for key in new_keys:
        batch.append(ScanComparisonItem(comparison=comparison, finding_fingerprint=key, change_type=ScanComparisonItem.CHANGE_NEW, after=_finding_json(b_map[key])))
    for key in resolved_keys:
        batch.append(ScanComparisonItem(comparison=comparison, finding_fingerprint=key, change_type=ScanComparisonItem.CHANGE_RESOLVED, before=_finding_json(a_map[key])))
    for key in changed_keys:
        batch.append(ScanComparisonItem(comparison=comparison, finding_fingerprint=key, change_type=ScanComparisonItem.CHANGE_CHANGED, before=_finding_json(a_map[key]), after=_finding_json(b_map[key])))
    ScanComparisonItem.objects.bulk_create(batch)
    return comparison


def _finding_json(finding: Finding) -> dict:
    return {
        'id': finding.id,
        'severity': finding.severity,
        'confidence': finding.confidence,
        'title': finding.title,
        'status': finding.status,
        'raw_result_ref': finding.raw_result_ref,
    }


def create_scan_comparison(scan_job: ScanJob):
    previous_job = (
        ScanJob.objects.filter(target=scan_job.target, status=ScanJob.STATUS_COMPLETED, completed_at__isnull=False)
        .exclude(pk=scan_job.pk)
        .order_by('-completed_at', '-id')
        .first()
    )
    if not previous_job:
        return None

    target_comparison = build_scan_comparison(previous_job, scan_job)
    for asset in Asset.objects.filter(target=scan_job.target):
        build_scan_comparison(previous_job, scan_job, asset=asset)
    return target_comparison
