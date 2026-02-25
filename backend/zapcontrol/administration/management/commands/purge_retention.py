from django.core.management.base import BaseCommand

from administration.models import AuditEvent, retention_cutoff
from administration.services import audit_log, setting_int
from targets.models import RawZapResult, Report


class Command(BaseCommand):
    help = 'Delete records older than retention settings.'

    def handle(self, *args, **options):
        deleted = {}

        audit_days = setting_int('retention_days_audit', 365)
        audit_qs = AuditEvent.objects.filter(created_at__lt=retention_cutoff(audit_days))
        deleted['audit_events'] = audit_qs.count()
        audit_qs.delete()

        raw_days = setting_int('retention_days_raw_results', 30)
        raw_qs = RawZapResult.objects.filter(fetched_at__lt=retention_cutoff(raw_days))
        deleted['raw_results'] = raw_qs.count()
        raw_qs.delete()

        finding_days = setting_int('retention_days_findings', 180)
        report_qs = Report.objects.filter(created_at__lt=retention_cutoff(finding_days))
        deleted['reports'] = report_qs.count()
        report_qs.delete()

        audit_log(None, AuditEvent.ACTION_PURGE_RETENTION, status=AuditEvent.STATUS_SUCCESS, message='Retention purge', extra=deleted)
        self.stdout.write(self.style.SUCCESS(f'Purged: {deleted}'))
