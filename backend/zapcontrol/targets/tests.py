from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import SetupState
from targets.models import Asset, Finding, Project, RawZapResult, RiskSnapshot, ScanComparisonItem, ScanJob, ScanProfile, Target, ZapNode
from targets.risk import build_finding_fingerprint, build_scan_comparison, compute_risk_score


class RiskAndFingerprintTests(TestCase):
    def test_compute_risk_score_uses_default_weights_and_confidence(self):
        score, breakdown = compute_risk_score([
            {'severity': 'High', 'confidence': 'High'},
            {'severity': 'Medium', 'confidence': 'Medium'},
            {'severity': 'Low', 'confidence': 'Low'},
        ])
        self.assertEqual(score, Decimal('14.60'))
        self.assertEqual(breakdown['High'], 1)
        self.assertEqual(breakdown['Medium'], 1)
        self.assertEqual(breakdown['Low'], 1)

    def test_fingerprint_stable_for_identical_alert(self):
        alert = {
            'pluginId': '10001',
            'url': 'https://example.test/a',
            'param': 'id',
            'method': 'GET',
            'evidence': 'x',
        }
        self.assertEqual(build_finding_fingerprint(alert), build_finding_fingerprint(dict(alert)))


class ComparisonLogicTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name='Proj', slug='proj')
        self.target = Target.objects.create(project=self.project, name='Web', base_url='https://web.test')
        self.asset = Asset.objects.create(target=self.target, name='https://web.test', asset_type=Asset.TYPE_URL, uri='https://web.test')
        self.node = ZapNode.objects.create(name='node-1', base_url='http://zap:8090', enabled=True)
        self.profile = ScanProfile.objects.create(name='default', project=self.project, zap_node=self.node)

    def _job(self):
        return ScanJob.objects.create(
            project=self.project,
            target=self.target,
            profile=self.profile,
            status=ScanJob.STATUS_COMPLETED,
            completed_at=timezone.now(),
        )

    def test_new_resolved_changed_items_created(self):
        scan_a = self._job()
        scan_b = self._job()
        RiskSnapshot.objects.create(target=self.target, scan_job=scan_a, asset=self.asset, risk_score=Decimal('5.0'))
        RiskSnapshot.objects.create(target=self.target, scan_job=scan_b, asset=self.asset, risk_score=Decimal('8.0'))

        Finding.objects.create(
            target=self.target, asset=self.asset, scan_job=scan_a, zap_plugin_id='1', title='Old', severity='Low', confidence='Low',
            fingerprint='old', first_seen=timezone.now(), last_seen=timezone.now(),
        )
        Finding.objects.create(
            target=self.target, asset=self.asset, scan_job=scan_a, zap_plugin_id='2', title='Changed', severity='Low', confidence='Medium',
            fingerprint='changed', first_seen=timezone.now(), last_seen=timezone.now(),
        )
        Finding.objects.create(
            target=self.target, asset=self.asset, scan_job=scan_b, zap_plugin_id='2', title='Changed', severity='High', confidence='High',
            fingerprint='changed', first_seen=timezone.now(), last_seen=timezone.now(),
        )
        Finding.objects.create(
            target=self.target, asset=self.asset, scan_job=scan_b, zap_plugin_id='3', title='New', severity='Medium', confidence='Medium',
            fingerprint='new', first_seen=timezone.now(), last_seen=timezone.now(),
        )

        comparison = build_scan_comparison(scan_a, scan_b, asset=self.asset)
        self.assertEqual(comparison.summary, {'new': 1, 'resolved': 1, 'changed': 1})
        self.assertEqual(comparison.risk_delta, Decimal('3.0'))
        self.assertEqual(comparison.items.filter(change_type=ScanComparisonItem.CHANGE_NEW).count(), 1)
        self.assertEqual(comparison.items.filter(change_type=ScanComparisonItem.CHANGE_RESOLVED).count(), 1)
        self.assertEqual(comparison.items.filter(change_type=ScanComparisonItem.CHANGE_CHANGED).count(), 1)


class ContextApiTests(TestCase):
    def setUp(self):
        SetupState.objects.update_or_create(pk=1, defaults={'is_complete': True})
        User = get_user_model()
        self.user = User.objects.create_user(email='sec@example.com', password='Passw0rd!123', role='security_engineer')
        self.client.force_login(self.user)
        self.project = Project.objects.create(name='App', slug='app')
        self.target = Target.objects.create(project=self.project, name='API', base_url='https://example.test')
        Asset.objects.create(target=self.target, name='https://example.test', asset_type=Asset.TYPE_URL, uri='https://example.test')

    def test_context_cascading_endpoints(self):
        projects = self.client.get('/api/context/projects').json()
        self.assertTrue(any(p['name'] == 'App' for p in projects))

        targets = self.client.get(f'/api/context/targets?project_id={self.project.id}').json()
        self.assertTrue(any(t['name'] == 'API' for t in targets))

        assets = self.client.get(f'/api/context/assets?target_id={self.target.id}').json()
        self.assertTrue(any(a['name'] == 'https://example.test' for a in assets))


class AssetsPagesTests(TestCase):
    def setUp(self):
        SetupState.objects.update_or_create(pk=1, defaults={'is_complete': True})
        User = get_user_model()
        self.user = User.objects.create_user(email='assets@example.com', password='Passw0rd!123', role='security_engineer')
        self.client.force_login(self.user)

        self.project = Project.objects.create(name='Assets', slug='assets')
        self.target = Target.objects.create(project=self.project, name='Main', base_url='https://main.test')
        self.node = ZapNode.objects.create(name='node-assets', base_url='http://zap-assets:8090', enabled=True)
        self.profile = ScanProfile.objects.create(name='assets-prof', project=self.project, zap_node=self.node)
        self.job = ScanJob.objects.create(project=self.project, target=self.target, profile=self.profile, status=ScanJob.STATUS_COMPLETED)

    def test_inventory_bootstraps_asset_from_existing_targets(self):
        self.assertEqual(Asset.objects.count(), 0)
        response = self.client.get('/assets/')
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(Asset.objects.count(), 1)
        self.assertContains(response, 'main.test')

    def test_raw_results_page_uses_raw_alerts_when_payload_empty(self):
        RawZapResult.objects.create(
            scan_job=self.job,
            payload={},
            raw_alerts=[{'alert': 'XSS', 'risk': 'High', 'url': 'https://main.test', 'param': 'q'}],
            metadata={'source': 'test'},
            size_bytes=12,
            checksum='abc',
        )
        response = self.client.get('/assets/raw/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alerts summary (human-readable)')
        self.assertContains(response, 'XSS')
        self.assertContains(response, 'Pretty JSON')
