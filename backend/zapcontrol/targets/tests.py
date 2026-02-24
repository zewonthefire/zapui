from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import SetupState
from targets.models import (
    Finding,
    FindingInstance,
    Project,
    RawZapResult,
    RiskSnapshot,
    ScanJob,
    ScanProfile,
    Target,
    ZapNode,
)
from targets.risk import create_scan_comparison
from targets.tasks import start_scan_job


class ScanLifecycleMockTests(TestCase):
    def setUp(self):
        SetupState.objects.update_or_create(pk=1, defaults={'is_complete': True})
        User = get_user_model()
        self.user = User.objects.create_user(email='sec@example.com', password='Passw0rd!123', role='security_engineer')
        self.project = Project.objects.create(name='App', slug='app')
        self.target = Target.objects.create(project=self.project, name='API', base_url='https://example.test')
        self.node = ZapNode.objects.create(
            name='node-1',
            base_url='http://zap:8090',
            status=ZapNode.STATUS_HEALTHY,
            enabled=True,
        )
        self.profile = ScanProfile.objects.create(
            name='Default',
            project=self.project,
            zap_node=self.node,
            scan_type=ScanProfile.TYPE_BASELINE_LIKE,
            spider_enabled=True,
            max_duration_minutes=5,
        )
        self.job = ScanJob.objects.create(project=self.project, target=self.target, profile=self.profile, initiated_by=self.user)

    @patch('targets.tasks.generate_scan_report')
    @patch('targets.tasks.ZapApiClient')
    def test_scan_job_moves_to_completed_and_persists_results(self, mock_client_cls, _mock_report):
        mock_client = mock_client_cls.return_value
        mock_client.version.return_value = {'version': '2.15.0'}
        mock_client.start_spider.return_value = '10'
        mock_client.spider_status.return_value = 100
        mock_client.start_active_scan.return_value = '22'
        mock_client.active_status.return_value = 100
        mock_client.alerts.return_value = [
            {
                'pluginId': '10001',
                'alert': 'XSS',
                'risk': 'High',
                'url': 'https://example.test',
                'param': 'q',
                'evidence': '<script>',
            }
        ]

        start_scan_job(self.job.id)

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ScanJob.STATUS_COMPLETED)
        self.assertEqual(self.job.zap_spider_id, '10')
        self.assertEqual(self.job.zap_ascan_id, '22')
        self.assertTrue(RawZapResult.objects.filter(scan_job=self.job).exists())


class EvolutionDiffComputationTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name='Proj', slug='proj')
        self.target = Target.objects.create(project=self.project, name='Web', base_url='https://web.test')
        self.node = ZapNode.objects.create(name='node-1', base_url='http://zap:8090', enabled=True)
        self.profile = ScanProfile.objects.create(name='prof', project=self.project, zap_node=self.node)

    def _completed_job(self):
        return ScanJob.objects.create(
            project=self.project,
            target=self.target,
            profile=self.profile,
            status=ScanJob.STATUS_COMPLETED,
            completed_at=timezone.now(),
        )

    def test_comparison_computes_new_resolved_and_risk_delta(self):
        old_job = self._completed_job()
        new_job = self._completed_job()

        old_finding = Finding.objects.create(
            target=self.target,
            scan_job=old_job,
            zap_plugin_id='10001',
            title='Old only',
            severity='Low',
            first_seen=timezone.now(),
            last_seen=timezone.now(),
        )
        shared_finding = Finding.objects.create(
            target=self.target,
            scan_job=old_job,
            zap_plugin_id='10002',
            title='Shared',
            severity='Medium',
            first_seen=timezone.now(),
            last_seen=timezone.now(),
        )
        new_finding = Finding.objects.create(
            target=self.target,
            scan_job=new_job,
            zap_plugin_id='10003',
            title='New only',
            severity='High',
            first_seen=timezone.now(),
            last_seen=timezone.now(),
        )

        FindingInstance.objects.create(finding=old_finding, scan_job=old_job)
        FindingInstance.objects.create(finding=shared_finding, scan_job=old_job)
        FindingInstance.objects.create(finding=shared_finding, scan_job=new_job)
        FindingInstance.objects.create(finding=new_finding, scan_job=new_job)

        RiskSnapshot.objects.create(target=self.target, scan_job=old_job, risk_score=Decimal('5.00'))
        RiskSnapshot.objects.create(target=self.target, scan_job=new_job, risk_score=Decimal('12.00'))

        comparison = create_scan_comparison(new_job)

        self.assertIsNotNone(comparison)
        self.assertEqual(comparison.new_finding_ids, [new_finding.id])
        self.assertEqual(comparison.resolved_finding_ids, [old_finding.id])
        self.assertEqual(comparison.risk_delta, Decimal('7.00'))
