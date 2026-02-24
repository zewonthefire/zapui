from decimal import Decimal

from django.db import models
from django.utils import timezone

from core.models import Setting

from .models import Finding, FindingInstance, RiskSnapshot, ScanComparison, ScanJob

DEFAULT_RISK_WEIGHTS = {
    'High': 10,
    'Medium': 5,
    'Low': 2,
    'Info': 1,
}

SEVERITY_ALIASES = {
    'high': 'High',
    'medium': 'Medium',
    'low': 'Low',
    'informational': 'Info',
    'info': 'Info',
}


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


def normalize_severity(value: str | None) -> str:
    if not value:
        return 'Info'
    return SEVERITY_ALIASES.get(str(value).strip().lower(), 'Info')


def normalize_alerts_to_findings(scan_job, alerts: list[dict]) -> None:
    now = timezone.now()
    finding_ids = set()
    for alert in alerts:
        plugin_id = str(alert.get('pluginId', '')).strip() or 'unknown'
        title = str(alert.get('alert', '')).strip() or 'Untitled Alert'
        severity = normalize_severity(alert.get('risk'))

        finding, created = Finding.objects.get_or_create(
            target=scan_job.target,
            zap_plugin_id=plugin_id,
            title=title,
            defaults={
                'scan_job': scan_job,
                'severity': severity,
                'description': alert.get('description', '') or '',
                'solution': alert.get('solution', '') or '',
                'reference': alert.get('reference', '') or '',
                'cwe_id': str(alert.get('cweid', '') or ''),
                'wasc_id': str(alert.get('wascid', '') or ''),
                'first_seen': now,
                'last_seen': now,
            },
        )
        if not created:
            finding.scan_job = scan_job
            finding.severity = severity
            finding.description = alert.get('description', '') or finding.description
            finding.solution = alert.get('solution', '') or finding.solution
            finding.reference = alert.get('reference', '') or finding.reference
            finding.cwe_id = str(alert.get('cweid', '') or finding.cwe_id)
            finding.wasc_id = str(alert.get('wascid', '') or finding.wasc_id)
            finding.last_seen = now
            finding.save(
                update_fields=['scan_job', 'severity', 'description', 'solution', 'reference', 'cwe_id', 'wasc_id', 'last_seen']
            )
        finding_ids.add(finding.id)

        FindingInstance.objects.get_or_create(
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

    for finding in Finding.objects.filter(id__in=finding_ids):
        instance_count = finding.instances.count()
        if finding.instances_count != instance_count:
            finding.instances_count = instance_count
            finding.save(update_fields=['instances_count'])


def _score_from_counts(counts: dict[str, int], weights: dict[str, int]) -> Decimal:
    total = sum(counts.get(level, 0) * weights.get(level, 0) for level in DEFAULT_RISK_WEIGHTS)
    return Decimal(total)


def severity_counts(queryset) -> dict[str, int]:
    base = {level: 0 for level in DEFAULT_RISK_WEIGHTS}
    for row in queryset.values('severity').order_by().annotate(total=models.Count('id')):
        sev = normalize_severity(row['severity'])
        base[sev] = row['total']
    return base


def create_risk_snapshots(scan_job):
    weights = get_risk_weights()

    target_findings = Finding.objects.filter(target=scan_job.target)
    target_counts = severity_counts(target_findings)
    RiskSnapshot.objects.create(
        target=scan_job.target,
        scan_job=scan_job,
        risk_score=_score_from_counts(target_counts, weights),
        counts_by_severity=target_counts,
    )

    project_findings = Finding.objects.filter(target__project=scan_job.project)
    project_counts = severity_counts(project_findings)
    RiskSnapshot.objects.create(
        project=scan_job.project,
        scan_job=scan_job,
        risk_score=_score_from_counts(project_counts, weights),
        counts_by_severity=project_counts,
    )

    global_findings = Finding.objects.all()
    global_counts = severity_counts(global_findings)
    RiskSnapshot.objects.create(
        scan_job=scan_job,
        risk_score=_score_from_counts(global_counts, weights),
        counts_by_severity=global_counts,
    )


def create_scan_comparison(scan_job):
    previous_job = (
        ScanJob.objects.filter(target=scan_job.target, status=ScanJob.STATUS_COMPLETED, completed_at__isnull=False)
        .exclude(pk=scan_job.pk)
        .order_by('-completed_at', '-id')
        .first()
    )
    if not previous_job:
        return None

    current_instances = FindingInstance.objects.filter(scan_job=scan_job).values_list('finding_id', flat=True).distinct()
    previous_instances = FindingInstance.objects.filter(scan_job=previous_job).values_list('finding_id', flat=True).distinct()

    current_ids = set(current_instances)
    previous_ids = set(previous_instances)

    current_target_snapshot = (
        RiskSnapshot.objects.filter(target=scan_job.target, project__isnull=True, scan_job=scan_job).first()
    )
    previous_target_snapshot = (
        RiskSnapshot.objects.filter(target=scan_job.target, project__isnull=True, scan_job=previous_job).first()
    )
    current_risk = current_target_snapshot.risk_score if current_target_snapshot else Decimal('0')
    previous_risk = previous_target_snapshot.risk_score if previous_target_snapshot else Decimal('0')

    comparison, _ = ScanComparison.objects.update_or_create(
        target=scan_job.target,
        from_scan_job=previous_job,
        to_scan_job=scan_job,
        defaults={
            'new_finding_ids': sorted(current_ids - previous_ids),
            'resolved_finding_ids': sorted(previous_ids - current_ids),
            'risk_delta': current_risk - previous_risk,
        },
    )
    return comparison
