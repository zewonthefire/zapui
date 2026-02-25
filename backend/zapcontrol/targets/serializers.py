from rest_framework import serializers

from .models import Asset, Finding, RawZapResult, ScanComparison, ScanComparisonItem, ScanJob


class AssetSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='target.project.name', read_only=True)
    target_name = serializers.CharField(source='target.name', read_only=True)

    class Meta:
        model = Asset
        fields = [
            'id',
            'name',
            'asset_type',
            'uri',
            'project_name',
            'target_name',
            'scan_count',
            'last_scanned_at',
            'last_scan_status',
            'current_risk_score',
            'findings_open_count_by_sev',
        ]


class FindingSerializer(serializers.ModelSerializer):
    scan_job_id = serializers.IntegerField(source='scan_job.id', read_only=True)

    class Meta:
        model = Finding
        fields = [
            'id',
            'title',
            'severity',
            'confidence',
            'status',
            'fingerprint',
            'first_seen',
            'last_seen',
            'raw_result_ref',
            'scan_job_id',
        ]


class ScanJobSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    target_name = serializers.CharField(source='target.name', read_only=True)
    profile_name = serializers.CharField(source='profile.name', read_only=True)
    node_name = serializers.CharField(source='zap_node.name', read_only=True)

    class Meta:
        model = ScanJob
        fields = [
            'id', 'project_name', 'target_name', 'profile_name', 'node_name',
            'status', 'created_at', 'started_at', 'completed_at', 'duration_seconds'
        ]


class RawZapResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawZapResult
        fields = ['id', 'scan_job', 'metadata', 'size_bytes', 'checksum', 'payload', 'fetched_at']


class ScanComparisonItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScanComparisonItem
        fields = ['finding_fingerprint', 'change_type', 'before', 'after']


class ScanComparisonSerializer(serializers.ModelSerializer):
    items = ScanComparisonItemSerializer(many=True, read_only=True)

    class Meta:
        model = ScanComparison
        fields = ['id', 'target', 'asset', 'scan_a', 'scan_b', 'scope', 'summary', 'risk_delta', 'created_at', 'items']
