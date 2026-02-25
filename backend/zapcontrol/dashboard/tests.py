from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import SetupState
from targets.models import Project, RiskSnapshot, ScanComparison, ScanJob, ScanProfile, Target


class DashboardApiTests(TestCase):
    def setUp(self):
        SetupState.objects.update_or_create(pk=1, defaults={'is_complete': True})
        self.user = get_user_model().objects.create_user(email='test@example.com', password='pass1234')
        self.client.login(email='test@example.com', password='pass1234')

        self.project_a = Project.objects.create(name='Project A', slug='project-a')
        self.project_b = Project.objects.create(name='Project B', slug='project-b')
        self.target_a = Target.objects.create(project=self.project_a, name='Target A', base_url='https://a.example.com')
        self.target_b = Target.objects.create(project=self.project_b, name='Target B', base_url='https://b.example.com')
        self.profile = ScanProfile.objects.create(name='Baseline', project=self.project_a)

        self.scan_a = ScanJob.objects.create(project=self.project_a, target=self.target_a, profile=self.profile, status=ScanJob.STATUS_COMPLETED)
        self.scan_b = ScanJob.objects.create(project=self.project_b, target=self.target_b, profile=self.profile, status=ScanJob.STATUS_FAILED)

        RiskSnapshot.objects.create(project=self.project_a, target=self.target_a, scan_job=self.scan_a, risk_score=55)
        RiskSnapshot.objects.create(project=self.project_b, target=self.target_b, scan_job=self.scan_b, risk_score=15)
        ScanComparison.objects.create(target=self.target_a, from_scan_job=self.scan_a, to_scan_job=self.scan_a, risk_delta=0)

    def test_dashboard_endpoints_respond(self):
        urls = [
            '/api/dashboard/overview/',
            '/api/dashboard/risk/',
            '/api/dashboard/findings/',
            '/api/dashboard/coverage/',
            '/api/dashboard/changes/',
            '/api/dashboard/operations/',
            '/api/context/options/',
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_context_options_cascade_filters_targets_by_project(self):
        response = self.client.get('/api/context/options/', {'project_id': self.project_a.id})
        self.assertEqual(response.status_code, 200)
        target_ids = {item['id'] for item in response.json()['targets']}
        self.assertEqual(target_ids, {self.target_a.id})

    def test_overview_filter_limits_scope(self):
        response = self.client.get('/api/dashboard/overview/', {'project_id': self.project_a.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['kpis']['current_risk_score'], 55.0)


class DashboardPageTests(TestCase):
    def setUp(self):
        SetupState.objects.update_or_create(pk=1, defaults={'is_complete': True})
        self.user = get_user_model().objects.create_user(email='page@example.com', password='pass1234')
        self.client.login(email='page@example.com', password='pass1234')

    def test_pages_render(self):
        for url in [
            '/dashboard/overview/',
            '/dashboard/risk/',
            '/dashboard/findings/',
            '/dashboard/coverage/',
            '/dashboard/changes/',
            '/dashboard/operations/',
        ]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
