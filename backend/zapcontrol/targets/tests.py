from datetime import time
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import SetupState
from targets.models import Asset, Project, ScanJob, ScanProfile, ScanRun, Target, ZapNode
from targets.risk import build_finding_fingerprint, compute_risk_score, normalize_alerts_to_findings
from targets.scan_engine import claim_queued_run, schedule_due_jobs


class ScanSchedulingTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name='P', slug='p')
        self.target = Target.objects.create(project=self.project, name='T', base_url='https://t.test')
        self.node = ZapNode.objects.create(name='n1', base_url='http://zap:8090', enabled=True, is_active=True, max_concurrent=2)
        self.profile = ScanProfile.objects.create(name='prof', project=self.project)

    def test_schedule_scans_creates_runs(self):
        job = ScanJob.objects.create(
            project=self.project,
            target=self.target,
            profile=self.profile,
            schedule_type=ScanJob.SCHEDULE_INTERVAL,
            schedule_interval_minutes=1,
            enabled=True,
        )
        created = schedule_due_jobs(now=timezone.now())
        self.assertEqual(created, 1)
        self.assertEqual(ScanRun.objects.filter(scan_job=job).count(), 1)


class WorkerClaimTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name='P', slug='p')
        self.target = Target.objects.create(project=self.project, name='T', base_url='https://t.test')
        self.node = ZapNode.objects.create(name='n1', base_url='http://zap:8090', enabled=True, is_active=True, max_concurrent=2)
        self.profile = ScanProfile.objects.create(name='prof', project=self.project)
        self.job = ScanJob.objects.create(project=self.project, target=self.target, profile=self.profile)

    def test_claim_queued_run_skip_locked_path(self):
        run = ScanRun.objects.create(scan_job=self.job, status=ScanRun.STATUS_QUEUED)
        claimed = claim_queued_run()
        self.assertEqual(claimed.id, run.id)
        self.assertEqual(claimed.status, ScanRun.STATUS_RUNNING)


class FingerprintAndRiskTests(TestCase):
    def test_fingerprint_stability(self):
        alert = {'pluginId': '1', 'url': 'https://a', 'param': 'q', 'method': 'GET', 'evidence': 'abc'}
        self.assertEqual(build_finding_fingerprint(alert), build_finding_fingerprint(dict(alert)))

    def test_risk_scoring(self):
        score, breakdown = compute_risk_score([
            {'risk': 'High', 'confidence': 'High'},
            {'risk': 'Medium', 'confidence': 'Medium'},
            {'risk': 'Low', 'confidence': 'Low'},
        ])
        self.assertEqual(score, Decimal('14.60'))
        self.assertEqual(breakdown['High'], 1)


class IncludeExcludeFilteringTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name='P', slug='p')
        self.target = Target.objects.create(
            project=self.project,
            name='T',
            base_url='https://t.test',
            include_regex=r't\.test',
            exclude_regex=r'/logout',
        )
        self.profile = ScanProfile.objects.create(name='prof', project=self.project)
        self.job = ScanJob.objects.create(project=self.project, target=self.target, profile=self.profile)

    def test_include_exclude_regex_filtering(self):
        alerts = [
            {'pluginId': '1', 'alert': 'A', 'risk': 'High', 'url': 'https://t.test/home'},
            {'pluginId': '2', 'alert': 'B', 'risk': 'Low', 'url': 'https://t.test/logout'},
            {'pluginId': '3', 'alert': 'C', 'risk': 'Low', 'url': 'https://other.test/'},
        ]
        normalize_alerts_to_findings(self.job, alerts)
        self.assertEqual(self.job.findings.count(), 1)


class ContextCascadeApiTests(TestCase):
    def setUp(self):
        SetupState.objects.update_or_create(pk=1, defaults={'is_complete': True})
        User = get_user_model()
        self.user = User.objects.create_user(email='u@example.com', password='Passw0rd!123', role='security_engineer')
        self.client.force_login(self.user)
        self.project = Project.objects.create(name='App', slug='app')
        self.target = Target.objects.create(project=self.project, name='API', base_url='https://example.test')
        Asset.objects.create(target=self.target, name='asset', asset_type=Asset.TYPE_URL, uri='https://example.test')

    def test_context_endpoints_cascade(self):
        self.assertEqual(self.client.get('/api/context/projects').status_code, 200)
        self.assertEqual(self.client.get(f'/api/context/targets?project_id={self.project.id}').status_code, 200)
        self.assertEqual(self.client.get(f'/api/context/assets?target_id={self.target.id}').status_code, 200)
