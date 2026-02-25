from django.core.management.base import BaseCommand, CommandError

from targets.scan_engine import enqueue_scan


class Command(BaseCommand):
    help = 'Submit a manual scan run for an existing scan job.'

    def add_arguments(self, parser):
        parser.add_argument('--scan_job_id', type=int, required=True)

    def handle(self, *args, **options):
        try:
            run = enqueue_scan(options['scan_job_id'])
        except Exception as exc:
            raise CommandError(str(exc))
        self.stdout.write(self.style.SUCCESS(f'Enqueued run #{run.id}'))
