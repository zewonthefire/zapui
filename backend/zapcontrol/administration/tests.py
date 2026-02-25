from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from administration.models import AppSetting, AuditEvent
from core.models import SetupState
from administration.services import ROLE_AUDIT_VIEWER, ROLE_SCAN_ADMIN, ROLE_SYSTEM_ADMIN, bootstrap_roles, encrypt_api_key
from targets.models import ZapNode


class AdministrationRBACTests(TestCase):
    def setUp(self):
        bootstrap_roles()
        User = get_user_model()
        self.system_user = User.objects.create_user(email='sys@example.com', password='Pass123!')
        SetupState.objects.update_or_create(pk=1, defaults={'is_complete': True})
        self.scan_user = User.objects.create_user(email='scan@example.com', password='Pass123!')
        self.audit_user = User.objects.create_user(email='audit@example.com', password='Pass123!')
        self.system_user.groups.add(Group.objects.get(name=ROLE_SYSTEM_ADMIN))
        self.scan_user.groups.add(Group.objects.get(name=ROLE_SCAN_ADMIN))
        self.audit_user.groups.add(Group.objects.get(name=ROLE_AUDIT_VIEWER))
        SetupState.objects.update_or_create(pk=1, defaults={'is_complete': True})
        self.client = Client()

    def test_users_page_requires_system_admin(self):
        self.client.force_login(self.scan_user)
        response = self.client.get(reverse('administration:users'))
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.system_user)
        response = self.client.get(reverse('administration:users'))
        self.assertEqual(response.status_code, 200)

    def test_nodes_page_allows_scan_admin(self):
        self.client.force_login(self.scan_user)
        response = self.client.get(reverse('administration:nodes'))
        self.assertEqual(response.status_code, 200)

    def test_audit_page_allows_audit_viewer(self):
        self.client.force_login(self.audit_user)
        response = self.client.get(reverse('administration:audit'))
        self.assertEqual(response.status_code, 200)


class AdministrationAuditMiddlewareTests(TestCase):
    def setUp(self):
        bootstrap_roles()
        User = get_user_model()
        self.system_user = User.objects.create_user(email='sys@example.com', password='Pass123!')
        self.system_user.groups.add(Group.objects.get(name=ROLE_SYSTEM_ADMIN))
        SetupState.objects.update_or_create(pk=1, defaults={'is_complete': True})
        self.client = Client()
        self.client.force_login(self.system_user)

    def test_mutating_request_creates_audit_event(self):
        self.client.post(reverse('administration:groups'), {'name': 'tmp-group'})
        self.assertTrue(AuditEvent.objects.filter(action='create').exists())


class AdministrationMaskingTests(TestCase):
    def setUp(self):
        bootstrap_roles()
        User = get_user_model()
        self.system_user = User.objects.create_user(email='sys@example.com', password='Pass123!')
        self.system_user.groups.add(Group.objects.get(name=ROLE_SYSTEM_ADMIN))
        SetupState.objects.update_or_create(pk=1, defaults={'is_complete': True})
        self.client = Client()
        self.client.force_login(self.system_user)

    def test_secret_setting_masked(self):
        AppSetting.objects.create(key='secret_token', value='super-secret', value_type=AppSetting.TYPE_SECRET, is_secret=True)
        response = self.client.get(reverse('administration:settings'))
        self.assertNotContains(response, 'super-secret')

    def test_node_api_key_masked(self):
        ZapNode.objects.create(name='node1', base_url='http://zap:8090', api_key=encrypt_api_key('test123'), is_active=True)
        response = self.client.get(reverse('administration:nodes'))
        self.assertNotContains(response, 'test123')


class HealthcheckAndPurgeTests(TestCase):
    def setUp(self):
        bootstrap_roles()
        User = get_user_model()
        SetupState.objects.update_or_create(pk=1, defaults={'is_complete': True})
        self.scan_user = User.objects.create_user(email='scan@example.com', password='Pass123!')
        self.scan_user.groups.add(Group.objects.get(name=ROLE_SCAN_ADMIN))
        self.system_user = User.objects.create_user(email='sys@example.com', password='Pass123!')
        self.system_user.groups.add(Group.objects.get(name=ROLE_SYSTEM_ADMIN))

    @patch('administration.views.requests.get')
    def test_healthcheck_updates_and_logs(self, mock_get):
        class R:
            def raise_for_status(self):
                return None

            def json(self):
                return {'version': '2.15.0'}

        mock_get.return_value = R()
        node = ZapNode.objects.create(name='node1', base_url='http://zap:8090', is_active=True)
        c = Client()
        c.force_login(self.scan_user)
        response = c.post(reverse('administration:node-healthcheck', kwargs={'node_id': node.id}))
        self.assertEqual(response.status_code, 200)
        node.refresh_from_db()
        self.assertEqual(node.health_status, 'healthy')
        self.assertTrue(AuditEvent.objects.filter(action=AuditEvent.ACTION_HEALTHCHECK).exists())

    def test_purge_retention(self):
        old = timezone.now() - timedelta(days=500)
        AppSetting.objects.update_or_create(key='retention_days_audit', defaults={'value': '365', 'value_type': AppSetting.TYPE_INT})
        ae = AuditEvent.objects.create(action=AuditEvent.ACTION_CREATE, created_at=timezone.now())
        AuditEvent.objects.filter(pk=ae.pk).update(created_at=old)
        call_command('purge_retention')
        self.assertFalse(AuditEvent.objects.filter(pk=ae.pk).exists())
        self.assertTrue(AuditEvent.objects.filter(action=AuditEvent.ACTION_PURGE_RETENTION).exists())
