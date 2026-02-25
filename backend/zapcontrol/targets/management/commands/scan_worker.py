from django.core.management.base import BaseCommand

from targets.scan_engine import claim_queued_run, execute_run


class Command(BaseCommand):
    help = 'Process queued scan runs using DB-backed queue.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true')

    def handle(self, *args, **options):
        while True:
            run = claim_queued_run()
            if not run:
                self.stdout.write('No queued runs.')
                break
            self.stdout.write(f'Processing run #{run.id}')
            execute_run(run)
            if options['once']:
                break
