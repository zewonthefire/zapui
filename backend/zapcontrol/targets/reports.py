import json
from collections import Counter
from decimal import Decimal

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.template.loader import render_to_string

from .models import Finding, FindingInstance, Report, RiskSnapshot, ScanJob


def _scan_findings(scan_job: ScanJob):
    finding_ids = (
        FindingInstance.objects.filter(scan_job=scan_job)
        .values_list('finding_id', flat=True)
        .distinct()
    )
    return Finding.objects.filter(id__in=finding_ids).order_by('-severity', 'title').prefetch_related('instances')


def _severity_breakdown(findings):
    counts = Counter({'High': 0, 'Medium': 0, 'Low': 0, 'Info': 0})
    for finding in findings:
        counts[str(finding.severity)] += 1
    return dict(counts)


def _risk_score(scan_job: ScanJob):
    snap = RiskSnapshot.objects.filter(scan_job=scan_job, target=scan_job.target, project__isnull=True).first()
    return str(snap.risk_score if snap else Decimal('0'))


def build_report_payload(scan_job: ScanJob):
    findings = list(_scan_findings(scan_job))
    sev = _severity_breakdown(findings)
    findings_payload = []
    for finding in findings:
        scan_instances = finding.instances.filter(scan_job=scan_job).order_by('-created_at')
        findings_payload.append(
            {
                'id': finding.id,
                'plugin_id': finding.zap_plugin_id,
                'title': finding.title,
                'severity': finding.severity,
                'description': finding.description,
                'solution': finding.solution,
                'reference': finding.reference,
                'cwe_id': finding.cwe_id,
                'wasc_id': finding.wasc_id,
                'instances_count': scan_instances.count(),
                'instances': [
                    {
                        'url': item.url,
                        'parameter': item.parameter,
                        'method': item.method,
                        'evidence': item.evidence,
                        'attack': item.attack,
                        'other': item.other,
                    }
                    for item in scan_instances
                ],
            }
        )

    return {
        'scan': {
            'id': scan_job.id,
            'status': scan_job.status,
            'created_at': scan_job.created_at.isoformat(),
            'started_at': scan_job.started_at.isoformat() if scan_job.started_at else None,
            'completed_at': scan_job.completed_at.isoformat() if scan_job.completed_at else None,
            'project': scan_job.project.name,
            'target': scan_job.target.name,
            'target_url': scan_job.target.base_url,
            'profile': scan_job.profile.name,
            'risk_score': _risk_score(scan_job),
            'severity_breakdown': sev,
            'findings_count': len(findings_payload),
            'instances_count': sum(item['instances_count'] for item in findings_payload),
        },
        'findings': findings_payload,
    }


def render_scan_html_report(scan_job: ScanJob, payload: dict):
    return render_to_string('targets/report_scan.html', {'job': scan_job, 'report': payload})


def _request_pdf_bytes(html: str) -> bytes:
    service_url = getattr(settings, 'PDF_SERVICE_URL', 'http://pdf:8092').rstrip('/') + '/render'
    resp = requests.post(
        service_url,
        json={'html': html, 'options': {'encoding': 'UTF-8', 'quiet': True}},
        timeout=90,
    )
    resp.raise_for_status()
    return resp.content


def generate_scan_report(scan_job: ScanJob) -> Report:
    payload = build_report_payload(scan_job)
    html_content = render_scan_html_report(scan_job, payload)
    json_content = json.dumps(payload, indent=2)
    pdf_content = _request_pdf_bytes(html_content)

    report = Report.objects.filter(scan_job=scan_job).first() or Report(scan_job=scan_job)
    report.html_file.save(f'scan-{scan_job.id}.html', ContentFile(html_content.encode('utf-8')), save=False)
    report.json_file.save(f'scan-{scan_job.id}.json', ContentFile(json_content.encode('utf-8')), save=False)
    report.pdf_file.save(f'scan-{scan_job.id}.pdf', ContentFile(pdf_content), save=False)
    report.save()
    return report
