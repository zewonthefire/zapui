from django.core.management.base import BaseCommand
from django.utils import timezone

from targets.models import ZapNode
from targets.zap_client import ZapClient


class Command(BaseCommand):
    help = 'Checks health for active ZAP nodes and updates status fields.'

    def handle(self, *args, **options):
        for node in ZapNode.objects.filter(enabled=True):
            client = ZapClient(node.base_url, api_key=node.api_key)
            try:
                client.version()
                node.health_status = ZapNode.STATUS_HEALTHY
                node.status = ZapNode.STATUS_HEALTHY
            except Exception:
                node.health_status = ZapNode.STATUS_UNREACHABLE
                node.status = ZapNode.STATUS_UNREACHABLE
            node.last_seen_at = timezone.now()
            node.last_health_check = node.last_seen_at
            node.save(update_fields=['health_status', 'status', 'last_seen_at', 'last_health_check'])
        self.stdout.write(self.style.SUCCESS('Node health check completed'))
