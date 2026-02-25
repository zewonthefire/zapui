from datetime import timedelta

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, pagination, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Asset, Finding, Project, RawZapResult, Report, ScanJob, ScanProfile, ScanRun, Target, ZapNode
from .scan_engine import enqueue_scan
from .serializers import (
    FindingSerializer,
    RawZapResultSerializer,
    ScanJobSerializer,
    ScanRunSerializer,
    ReportSerializer,
)


class DefaultPagination(pagination.PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


def _apply_range(qs, request, field='created_at'):
    range_value = request.GET.get('range')
    if range_value and range_value != 'all':
        since = timezone.now() - timedelta(days=int(range_value))
        return qs.filter(**{f'{field}__gte': since})
    return qs


def _scope_filter(qs, request):
    if request.GET.get('project_id') and request.GET.get('project_id') != 'all':
        qs = qs.filter(project_id=request.GET['project_id'])
    if request.GET.get('target_id') and request.GET.get('target_id') != 'all':
        qs = qs.filter(target_id=request.GET['target_id'])
    if request.GET.get('asset_id') and request.GET.get('asset_id') != 'all':
        qs = qs.filter(findings__asset_id=request.GET['asset_id'])
    return qs


class ContextProjectsApi(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response([{'id': 'all', 'name': 'All projects'}] + list(Project.objects.values('id', 'name')))


class ContextTargetsApi(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        project_id = request.GET.get('project_id')
        qs = Target.objects.filter(enabled=True)
        if project_id and project_id != 'all':
            qs = qs.filter(project_id=project_id)
        return Response([{'id': 'all', 'name': 'All targets'}] + list(qs.values('id', 'name')))


class ContextAssetsApi(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        target_id = request.GET.get('target_id')
        qs = Asset.objects.all()
        if target_id and target_id != 'all':
            qs = qs.filter(target_id=target_id)
        return Response([{'id': 'all', 'name': 'All assets'}] + list(qs.values('id', 'name')))


class ContextNodesApi(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = ZapNode.objects.filter(enabled=True, is_active=True)
        return Response([{'id': 'all', 'name': 'All scanners'}] + list(qs.values('id', 'name')))


class ContextProfilesApi(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = ScanProfile.objects.all()
        project_id = request.GET.get('project_id')
        if project_id and project_id != 'all':
            qs = qs.filter(Q(project_id=project_id) | Q(project_id__isnull=True))
        return Response([{'id': 'all', 'name': 'All profiles'}] + list(qs.values('id', 'name')))


class ContextScansApi(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = ScanRun.objects.select_related('scan_job__target')
        qs = _scope_filter(qs, request)
        qs = _apply_range(qs, request)
        payload = [{'id': 'latest', 'name': 'Latest'}] + [
            {'id': run.id, 'name': f'Run #{run.id} {run.scan_job.target.name} ({run.status})'} for run in qs.order_by('-created_at')[:100]
        ]
        return Response(payload)


class JobsApi(generics.ListAPIView):
    serializer_class = ScanJobSerializer
    pagination_class = DefaultPagination

    def get_queryset(self):
        qs = ScanJob.objects.select_related('project', 'target', 'profile', 'zap_node').annotate(
            last_run_status=Count('runs')
        )
        return _scope_filter(qs, self.request).order_by('-created_at').distinct()


class RunsApi(generics.ListAPIView):
    serializer_class = ScanRunSerializer
    pagination_class = DefaultPagination

    def get_queryset(self):
        qs = ScanRun.objects.select_related('scan_job__project', 'scan_job__target', 'scan_job__profile', 'zap_node')
        params = self.request.GET
        if params.get('status'):
            qs = qs.filter(status=params['status'])
        if params.get('node') and params.get('node') != 'all':
            qs = qs.filter(zap_node_id=params['node'])
        qs = _apply_range(_scope_filter(qs, self.request), self.request)
        return qs.order_by('-created_at')


class RunDetailApi(generics.RetrieveAPIView):
    queryset = ScanRun.objects.select_related('scan_job__project', 'scan_job__target', 'scan_job__profile', 'zap_node')
    serializer_class = ScanRunSerializer


class RunFindingsApi(generics.ListAPIView):
    serializer_class = FindingSerializer
    pagination_class = DefaultPagination

    def get_queryset(self):
        qs = Finding.objects.filter(scan_run_id=self.kwargs['id'])
        if self.request.GET.get('search'):
            s = self.request.GET['search']
            qs = qs.filter(Q(title__icontains=s) | Q(description__icontains=s))
        if self.request.GET.get('severity'):
            qs = qs.filter(severity=self.request.GET['severity'])
        return qs.order_by(self.request.GET.get('ordering', '-last_seen'))


class RunRawApi(generics.ListAPIView):
    serializer_class = RawZapResultSerializer
    pagination_class = DefaultPagination

    def get_queryset(self):
        return RawZapResult.objects.filter(scan_run_id=self.kwargs['id']).order_by('-fetched_at')


class RunReportApi(APIView):
    def get(self, request, id):
        report = get_object_or_404(Report, scan_run_id=id)
        return Response(ReportSerializer(report).data)


class EnqueueApi(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        scan_job_id = request.data.get('scan_job_id')
        run = enqueue_scan(scan_job_id)
        return Response({'run_id': run.id, 'status': run.status}, status=status.HTTP_201_CREATED)
