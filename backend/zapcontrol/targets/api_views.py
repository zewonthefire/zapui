from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, pagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Asset, Finding, Project, RawZapResult, ScanComparison, ScanJob, ScanProfile, Target, ZapNode
from .serializers import (
    AssetSerializer,
    FindingSerializer,
    RawZapResultSerializer,
    ScanComparisonSerializer,
    ScanJobSerializer,
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


class ContextProjectsApi(APIView):
    def get(self, request):
        return Response([{'id': 'all', 'name': 'All projects'}] + list(Project.objects.values('id', 'name')))


class ContextTargetsApi(APIView):
    def get(self, request):
        project_id = request.GET.get('project_id')
        qs = Target.objects.all()
        if project_id and project_id != 'all':
            qs = qs.filter(project_id=project_id)
        return Response([{'id': 'all', 'name': 'All targets'}] + list(qs.values('id', 'name')))


class ContextAssetsApi(APIView):
    def get(self, request):
        target_id = request.GET.get('target_id')
        qs = Asset.objects.all()
        if target_id and target_id != 'all':
            qs = qs.filter(target_id=target_id)
        return Response([{'id': 'all', 'name': 'All assets'}] + list(qs.values('id', 'name')))


class ContextNodesApi(APIView):
    def get(self, request):
        qs = ZapNode.objects.filter(enabled=True)
        return Response([{'id': 'all', 'name': 'All scanners'}] + list(qs.values('id', 'name')))


class ContextProfilesApi(APIView):
    def get(self, request):
        qs = ScanProfile.objects.all()
        project_id = request.GET.get('project_id')
        if project_id and project_id != 'all':
            qs = qs.filter(Q(project_id=project_id) | Q(project_id__isnull=True))
        return Response([{'id': 'all', 'name': 'All profiles'}] + list(qs.values('id', 'name')))


class ContextScansApi(APIView):
    def get(self, request):
        qs = ScanJob.objects.select_related('target').all()
        target_id = request.GET.get('target_id')
        if target_id and target_id != 'all':
            qs = qs.filter(target_id=target_id)
        qs = _apply_range(qs, request)
        payload = [{'id': 'latest', 'name': 'Latest'}] + [
            {'id': scan.id, 'name': f'#{scan.id} {scan.target.name} ({scan.status})'} for scan in qs.order_by('-created_at')[:100]
        ]
        return Response(payload)


class AssetListApi(generics.ListAPIView):
    serializer_class = AssetSerializer
    pagination_class = DefaultPagination
    ordering_fields = ['name', 'last_scanned_at', 'scan_count', 'current_risk_score']

    def get_queryset(self):
        qs = Asset.objects.select_related('target__project').all()
        params = self.request.GET
        if params.get('project'):
            qs = qs.filter(target__project_id=params['project'])
        if params.get('target'):
            qs = qs.filter(target_id=params['target'])
        if params.get('node'):
            qs = qs.filter(findings__scan_job__zap_node_id=params['node'])
        if params.get('profile'):
            qs = qs.filter(findings__scan_job__profile_id=params['profile'])
        qs = _apply_range(qs, self.request, field='last_scanned_at').distinct()
        return qs


class AssetFindingsApi(generics.ListAPIView):
    serializer_class = FindingSerializer
    pagination_class = DefaultPagination

    def get_queryset(self):
        qs = Finding.objects.filter(asset_id=self.kwargs['asset_id']).select_related('scan_job')
        params = self.request.GET
        for key in ['status', 'severity', 'confidence']:
            if params.get(key):
                qs = qs.filter(**{key: params[key]})
        if params.get('search'):
            qs = qs.filter(Q(title__icontains=params['search']) | Q(description__icontains=params['search']))
        return qs.order_by(params.get('ordering', '-last_seen'))


class ScanListApi(generics.ListAPIView):
    serializer_class = ScanJobSerializer
    pagination_class = DefaultPagination

    def get_queryset(self):
        qs = ScanJob.objects.select_related('project', 'target', 'profile', 'zap_node').all()
        params = self.request.GET
        if params.get('project'):
            qs = qs.filter(project_id=params['project'])
        if params.get('target'):
            qs = qs.filter(target_id=params['target'])
        if params.get('asset'):
            qs = qs.filter(findings__asset_id=params['asset'])
        return _apply_range(qs, self.request).order_by('-created_at').distinct()


class RawResultsApi(generics.ListAPIView):
    serializer_class = RawZapResultSerializer
    pagination_class = DefaultPagination

    def get_queryset(self):
        qs = RawZapResult.objects.select_related('scan_job').order_by('-fetched_at')
        if self.request.GET.get('scan_job_id'):
            qs = qs.filter(scan_job_id=self.request.GET['scan_job_id'])
        return qs


class ComparisonsApi(generics.ListAPIView):
    serializer_class = ScanComparisonSerializer
    pagination_class = DefaultPagination

    def get_queryset(self):
        qs = ScanComparison.objects.select_related('target', 'asset', 'scan_a', 'scan_b').prefetch_related('items').all()
        params = self.request.GET
        if params.get('scan_a'):
            qs = qs.filter(scan_a_id=params['scan_a'])
        if params.get('scan_b'):
            qs = qs.filter(scan_b_id=params['scan_b'])
        if params.get('scope'):
            qs = qs.filter(scope=params['scope'])
        return qs.order_by('-created_at')
