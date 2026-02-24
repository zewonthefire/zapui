from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import SetupState
from targets.models import ZapNode


class SetupWizardGatingTests(TestCase):
    def setUp(self):
        SetupState.objects.update_or_create(pk=1, defaults={'is_complete': False, 'current_step': 1})

    def test_redirects_non_exempt_routes_when_setup_incomplete(self):
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/setup')

    def test_allows_exempt_health_route_when_setup_incomplete(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})


class LoginAndRolesTests(TestCase):
    def setUp(self):
        SetupState.objects.update_or_create(pk=1, defaults={'is_complete': True})
        User = get_user_model()
        self.admin = User.objects.create_user(email='admin@example.com', password='Passw0rd!123', role='admin', is_staff=True)
        self.readonly = User.objects.create_user(email='readonly@example.com', password='Passw0rd!123', role='readonly')

    def test_login_works_for_email_user(self):
        response = self.client.post(reverse('login'), {'username': 'admin@example.com', 'password': 'Passw0rd!123'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/dashboard')

    def test_readonly_cannot_access_admin_only_zapnodes(self):
        self.client.login(username='readonly@example.com', password='Passw0rd!123')
        response = self.client.get('/zapnodes', follow=True)
        self.assertContains(response, 'Admin role required for operations pages.')

    @patch('core.views.requests.get')
    def test_admin_can_add_external_node_and_test_connectivity(self, mock_get):
        class FakeResp:
            def raise_for_status(self):
                return None

            def json(self):
                return {'version': '2.15.0'}

        mock_get.return_value = FakeResp()

        self.client.login(username='admin@example.com', password='Passw0rd!123')

        add_response = self.client.post(
            '/zapnodes',
            {
                'action': 'add_external',
                'name': 'external-lab',
                'base_url': 'http://zap-ext:8090',
                'api_key': 'secret',
                'password': 'Passw0rd!123',
            },
            follow=True,
        )
        self.assertContains(add_response, 'Added external node external-lab.')
        node = ZapNode.objects.get(name='external-lab')

        test_response = self.client.post(
            '/zapnodes',
            {
                'action': 'test_node',
                'node_id': node.id,
                'password': 'Passw0rd!123',
            },
            follow=True,
        )
        self.assertContains(test_response, 'healthy (version 2.15.0')
        node.refresh_from_db()
        self.assertEqual(node.status, ZapNode.STATUS_HEALTHY)


class SetupWizardStepOneDefaultsTests(TestCase):
    def setUp(self):
        SetupState.objects.update_or_create(pk=1, defaults={'is_complete': False, 'current_step': 1})

    def test_prefills_external_base_url_and_display_port_from_request_host(self):
        response = self.client.get('/setup', SERVER_NAME='zapui.example.test', SERVER_PORT='8088')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="http://zapui.example.test:8088"')
        self.assertContains(response, 'value="8088"')

    def test_existing_wizard_values_override_prefilled_defaults(self):
        state = SetupState.objects.get(pk=1)
        state.wizard_data = {
            'instance': {
                'external_base_url': 'https://configured.example.com',
                'display_http_port': '9443',
            }
        }
        state.save(update_fields=['wizard_data'])

        response = self.client.get('/setup', SERVER_NAME='zapui.example.test', SERVER_PORT='8088')

        self.assertContains(response, 'value="https://configured.example.com"')
        self.assertContains(response, 'value="9443"')
