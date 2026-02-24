import os
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




class OpsOverviewResilienceTests(TestCase):
    def setUp(self):
        SetupState.objects.update_or_create(pk=1, defaults={'is_complete': True})
        User = get_user_model()
        self.admin = User.objects.create_user(email='admin2@example.com', password='Passw0rd!123', role='admin', is_staff=True)

    @patch('core.views.OPS_ENABLED', True)
    @patch('core.views._ops_get')
    def test_ops_overview_handles_ops_api_failure_without_500(self, mock_ops_get):
        mock_ops_get.side_effect = Exception('ops down')

        self.client.login(username='admin2@example.com', password='Passw0rd!123')
        response = self.client.get('/ops/overview', follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ops agent is unavailable: ops down')
        self.assertNotContains(response, 'Unable to list internal ZAP containers')

class SetupWizardStepOneDefaultsTests(TestCase):
    def setUp(self):
        SetupState.objects.update_or_create(pk=1, defaults={'is_complete': False, 'current_step': 1})

    def test_prefills_external_base_url_and_display_ports_from_install_defaults(self):
        with patch.dict(os.environ, {'PUBLIC_HTTP_PORT': '8090', 'PUBLIC_HTTPS_PORT': '4443'}):
            response = self.client.get('/setup', SERVER_NAME='zapui.example.test', SERVER_PORT='8088')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="http://zapui.example.test:8090"')
        self.assertContains(response, 'value="8090"')
        self.assertContains(response, 'value="4443"')

    def test_existing_wizard_values_override_prefilled_defaults(self):
        state = SetupState.objects.get(pk=1)
        state.wizard_data = {
            'instance': {
                'external_base_url': 'https://configured.example.com',
                'display_http_port': '9443',
                'display_https_port': '9444',
            }
        }
        state.save(update_fields=['wizard_data'])

        response = self.client.get('/setup', SERVER_NAME='zapui.example.test', SERVER_PORT='8088')

        self.assertContains(response, 'value="https://configured.example.com"')
        self.assertContains(response, 'value="9443"')
        self.assertContains(response, 'value="9444"')


class ZapNodesInternalSyncTests(TestCase):
    def setUp(self):
        SetupState.objects.update_or_create(pk=1, defaults={'is_complete': True})
        User = get_user_model()
        self.admin = User.objects.create_user(email='admin3@example.com', password='Passw0rd!123', role='admin', is_staff=True)

    @patch('core.views.OPS_ENABLED', True)
    @patch('core.views._discover_internal_zap_containers')
    def test_zapnodes_get_syncs_internal_nodes_and_shows_counts(self, mock_discover):
        mock_discover.return_value = ['zapui-zap-1']
        from core.models import Setting
        Setting.objects.update_or_create(key='internal_zap_api_key', defaults={'value': 'internal-key'})
        ZapNode.objects.create(
            name='internal-zap-legacy',
            base_url='http://old-zap:8090',
            managed_type=ZapNode.MANAGED_INTERNAL,
            docker_container_name='old-zap',
            enabled=True,
        )

        self.client.login(username='admin3@example.com', password='Passw0rd!123')
        response = self.client.get('/zapnodes')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'registered /')
        self.assertContains(response, 'running containers')
        self.assertContains(response, '(sync: +1 created, 1 disabled)')

        node = ZapNode.objects.get(name='internal-zap-1')
        self.assertEqual(node.docker_container_name, 'zapui-zap-1')
        self.assertEqual(node.api_key, 'internal-key')

        legacy = ZapNode.objects.get(name='internal-zap-legacy')
        self.assertFalse(legacy.enabled)
        self.assertEqual(legacy.status, ZapNode.STATUS_DISABLED)


class CsrfTrustedOriginSetupTests(TestCase):
    def setUp(self):
        SetupState.objects.update_or_create(pk=1, defaults={'is_complete': False, 'current_step': 1})

    def test_builds_csrf_origin_using_external_host_and_https_port(self):
        from core.views import _csrf_origin_from_setup_data

        origin = _csrf_origin_from_setup_data(
            {
                'external_base_url': 'http://zapui.example.test:8090',
                'display_https_port': '9443',
            }
        )

        self.assertEqual(origin, 'https://zapui.example.test:9443')

    @patch('core.views.OPS_ENABLED', True)
    @patch('core.views._ops_post')
    def test_step_one_applies_csrf_origin_via_ops_agent(self, mock_ops_post):
        class FakeResp:
            def raise_for_status(self):
                return None

        mock_ops_post.return_value = FakeResp()

        response = self.client.post(
            '/setup',
            {
                'step': '1',
                'action': 'next',
                'instance_name': 'prod',
                'external_base_url': 'https://zapui.example.test',
                'display_http_port': '8090',
                'display_https_port': '443',
                'database_mode': 'integrated',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Updated DJANGO_CSRF_TRUSTED_ORIGINS to https://zapui.example.test:443 and recreated web/nginx.')
        mock_ops_post.assert_called_with('/compose/env/upsert-csrf-origin', json={'origin': 'https://zapui.example.test:443'})

        state = SetupState.objects.get(pk=1)
        self.assertEqual(state.current_step, 2)
        self.assertEqual(state.wizard_data['instance']['csrf_trusted_origin'], 'https://zapui.example.test:443')
        self.assertTrue(state.wizard_data['instance']['csrf_trusted_origin_applied'])


class SetupWizardZapKeyTests(TestCase):
    def setUp(self):
        SetupState.objects.update_or_create(pk=1, defaults={'is_complete': False, 'current_step': 4})

    @patch('core.views.OPS_ENABLED', True)
    @patch('core.views._ops_post')
    def test_step_four_generates_internal_key_and_registers_compose_node(self, mock_ops_post):
        class FakeResp:
            def raise_for_status(self):
                return None

        mock_ops_post.return_value = FakeResp()

        response = self.client.post(
            '/setup',
            {
                'step': '4',
                'action': 'next',
                'zap_pool_size': '1',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Internal ZAP API key generated and applied to compose.')

        internal_node = ZapNode.objects.get(name='internal-zap-compose')
        self.assertEqual(internal_node.base_url, 'http://zap:8090')
        self.assertTrue(internal_node.api_key)

        state = SetupState.objects.get(pk=1)
        self.assertEqual(state.current_step, 5)
        self.assertEqual(state.wizard_data['zap']['internal_api_key'], internal_node.api_key)

        self.assertEqual(mock_ops_post.call_args_list[0].args[0], '/compose/env/upsert-zap-api-key')
        self.assertEqual(mock_ops_post.call_args_list[1].args[0], '/compose/scale')

    @patch('core.views.OPS_ENABLED', True)
    @patch('core.views._ops_post')
    def test_step_four_existing_key_failure_message_is_non_blocking(self, mock_ops_post):
        from core.models import Setting

        class FakeResp:
            status_code = 500

        import requests

        mock_ops_post.side_effect = requests.HTTPError(response=FakeResp())
        Setting.objects.update_or_create(key='internal_zap_api_key', defaults={'value': 'already-there'})

        response = self.client.post(
            '/setup',
            {
                'step': '4',
                'action': 'next',
                'zap_pool_size': '1',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Unable to re-apply internal ZAP API key automatically (HTTP 500). Existing key is kept; setup can continue if internal ZAP is reachable.')


class SetupWizardFinalizeRestartTests(TestCase):
    def setUp(self):
        SetupState.objects.update_or_create(
            pk=1,
            defaults={
                'is_complete': False,
                'current_step': 5,
                'wizard_data': {'database': {'mode': 'integrated'}, 'instance': {'external_base_url': 'http://zapui.example.test:8090'}},
            },
        )

    @patch('core.views._validate_existing_certs', return_value=(True, 'ok cert'))
    @patch('core.views.connectivity_checks', return_value=[])
    @patch('core.views._internal_zap_started_state', return_value=(True, 'state=running'))
    @patch('core.views.OPS_ENABLED', True)
    @patch('core.views._ops_post')
    def test_finalize_restarts_zap_container(self, mock_ops_post, _ops_state, _mock_checks, _mock_certs):
        class FakeResp:
            def raise_for_status(self):
                return None

        mock_ops_post.return_value = FakeResp()

        response = self.client.post(
            '/setup',
            {
                'step': '5',
                'action': 'finalize',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ZAP container restarted after setup finalization.')

        state = SetupState.objects.get(pk=1)
        self.assertTrue(state.is_complete)
        self.assertEqual(state.wizard_data['zap_restart_after_setup']['applied'], True)
        self.assertEqual(mock_ops_post.call_args.args[0], '/compose/restart/zap')


class SetupWizardZapLiveStatusTests(TestCase):
    def setUp(self):
        SetupState.objects.update_or_create(
            pk=1,
            defaults={
                'is_complete': False,
                'current_step': 5,
                'wizard_data': {'database': {'mode': 'integrated'}, 'instance': {'external_base_url': 'http://zapui.example.test:8090'}},
            },
        )

    @patch('core.views.OPS_ENABLED', True)
    @patch('core.views._ops_get')
    def test_setup_zap_status_endpoint_returns_started(self, mock_ops_get):
        class FakeResp:
            def raise_for_status(self):
                return None

            def json(self):
                return {'services': [{'Service': 'zap', 'State': 'running'}]}

        mock_ops_get.return_value = FakeResp()

        response = self.client.get('/setup/zap-status')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['started'], True)

    @patch('core.views.OPS_ENABLED', True)
    @patch('core.views._ops_get')
    def test_finalize_is_blocked_when_zap_not_started(self, mock_ops_get):
        class FakeResp:
            def raise_for_status(self):
                return None

            def json(self):
                return {'services': [{'Service': 'zap', 'State': 'created'}]}

        mock_ops_get.return_value = FakeResp()

        response = self.client.post(
            '/setup',
            {
                'step': '5',
                'action': 'finalize',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Finalize blocked: internal ZAP is not started')

        state = SetupState.objects.get(pk=1)
        self.assertFalse(state.is_complete)


class InternalZapStartedFallbackTests(TestCase):
    @patch('core.views.OPS_ENABLED', True)
    @patch('core.views._ops_get', side_effect=Exception('ops down'))
    @patch('core.views._test_node_connectivity')
    def test_internal_zap_started_uses_internal_node_fallback(self, mock_connectivity, _mock_ops_get):
        from core.views import _internal_zap_started_state

        node = ZapNode.objects.create(
            name='internal-zap-compose',
            base_url='http://zap:8090',
            api_key='secret',
            managed_type=ZapNode.MANAGED_INTERNAL,
            enabled=True,
        )

        started, hint = _internal_zap_started_state()

        self.assertTrue(started)
        self.assertIn(node.name, hint)
        mock_connectivity.assert_called_once_with(node)


class DeepZapCheckApiKeyHintTests(TestCase):
    @patch('core.views.requests.get')
    def test_deep_zap_check_does_not_probe_with_invalid_key(self, mock_get):
        from core.views import _deep_zap_check

        class FakeResp:
            def __init__(self, payload):
                self._payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        mock_get.side_effect = [
            FakeResp({'version': '2.17.0'}),
            FakeResp({'numberOfAlerts': '0'}),
        ]

        node = ZapNode.objects.create(
            name='internal-zap-compose',
            base_url='http://zap:8090',
            api_key='secret',
            managed_type=ZapNode.MANAGED_INTERNAL,
            enabled=True,
        )

        result = _deep_zap_check(node)

        self.assertEqual(result['status'], 'ok')
        self.assertIn('api_key=configured', result['hint'])
        self.assertEqual(mock_get.call_count, 2)
