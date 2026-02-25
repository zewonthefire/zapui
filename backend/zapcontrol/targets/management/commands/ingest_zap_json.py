import hashlib
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from targets.models import Project, RawZapResult, ScanJob, ScanProfile, Target, ZapNode
from targets.risk import create_risk_snapshots, create_scan_comparison, normalize_alerts_to_findings


class Command(BaseCommand):
    help = 'Ingest a ZAP JSON report and normalize findings/snapshots/comparisons.'

    def add_arguments(self, parser):
        parser.add_argument('--project', required=True)
        parser.add_argument('--target', required=True)
        parser.add_argument('--profile', required=True)
        parser.add_argument('--node', required=True)
        parser.add_argument('--file', required=True)

    def handle(self, *args, **options):
        path = Path(options['file'])
        if not path.exists():
            raise CommandError(f'File not found: {path}')

        project = Project.objects.filter(slug=options['project']).first() or Project.objects.filter(name=options['project']).first()
        if not project:
            raise CommandError('Project not found (match slug or name).')

        target = Target.objects.filter(project=project, name=options['target']).first()
        if not target:
            raise CommandError('Target not found for project.')

        profile = ScanProfile.objects.filter(name=options['profile']).first()
        if not profile:
            raise CommandError('Scan profile not found.')

        node = ZapNode.objects.filter(name=options['node']).first()
        if not node:
            raise CommandError('Zap node not found.')

        raw_payload = json.loads(path.read_text())
        alerts = raw_payload.get('alerts') if isinstance(raw_payload, dict) else raw_payload
        if not isinstance(alerts, list):
            raise CommandError('JSON must be list of alerts or object with "alerts" list.')

        started_at = timezone.now()
        job = ScanJob.objects.create(
            project=project,
            target=target,
            profile=profile,
            zap_node=node,
            status=ScanJob.STATUS_RUNNING,
            started_at=started_at,
        )

        encoded = json.dumps(raw_payload, sort_keys=True).encode('utf-8')
        RawZapResult.objects.create(
            scan_job=job,
            payload=raw_payload,
            raw_alerts=alerts,
            metadata={'ingest_file': str(path), 'ingest_mode': 'management_command'},
            size_bytes=len(encoded),
            checksum=hashlib.sha256(encoded).hexdigest(),
        )

        normalize_alerts_to_findings(job, alerts)

        completed_at = timezone.now()
        job.status = ScanJob.STATUS_COMPLETED
        job.completed_at = completed_at
        job.duration_seconds = int((completed_at - started_at).total_seconds())
        job.save(update_fields=['status', 'completed_at', 'duration_seconds'])

        create_risk_snapshots(job)
        create_scan_comparison(job)

        self.stdout.write(self.style.SUCCESS(f'Ingested {len(alerts)} alerts into scan job #{job.id}'))
