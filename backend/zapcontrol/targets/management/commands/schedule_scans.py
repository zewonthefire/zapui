from django.core.management.base import BaseCommand

from targets.scan_engine import schedule_due_jobs


class Command(BaseCommand):
    help = 'Create ScanRun entries for due scheduled ScanJobs.'

    def handle(self, *args, **options):
        created = schedule_due_jobs()
        self.stdout.write(self.style.SUCCESS(f'Created {created} queued runs'))
