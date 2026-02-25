from django.apps import AppConfig


class TargetsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'targets'

    def ready(self):
        from django.contrib.auth.models import Group
        from django.db.models.signals import post_migrate

        def ensure_scan_groups(sender, **kwargs):
            for name in ['scan_admin', 'scan_operator', 'scan_viewer']:
                Group.objects.get_or_create(name=name)

        post_migrate.connect(ensure_scan_groups, sender=self)
