from django.core.management.base import BaseCommand

from administration.services import bootstrap_roles


class Command(BaseCommand):
    help = 'Create baseline administration groups and permissions.'

    def handle(self, *args, **options):
        bootstrap_roles()
        self.stdout.write(self.style.SUCCESS('Baseline roles created/updated.'))
