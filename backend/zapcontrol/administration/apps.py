from django.apps import AppConfig
from django.db.models.signals import post_migrate


class AdministrationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'administration'

    def ready(self):
        post_migrate.connect(_seed_settings, sender=self)


def _seed_settings(sender, **kwargs):
    from .services import ensure_default_settings

    ensure_default_settings()
