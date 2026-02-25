from rest_framework import serializers

from .models import Finding, RawZapResult, Report, ScanJob, ScanRun


class FindingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Finding
        fields = [
            'id', 'title', 'severity', 'confidence', 'status', 'fingerprint',
            'first_seen', 'last_seen', 'raw_result_ref',
        ]


class ScanJobSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    target_name = serializers.CharField(source='target.name', read_only=True)
    profile_name = serializers.CharField(source='profile.name', read_only=True)
    node_name = serializers.CharField(source='zap_node.name', read_only=True)
    last_run_status = serializers.SerializerMethodField()
    last_run_time = serializers.SerializerMethodField()

    class Meta:
        model = ScanJob
        fields = [
            'id', 'project', 'target', 'profile', 'project_name', 'target_name', 'profile_name', 'node_name',
            'node_strategy', 'schedule_type', 'enabled', 'created_at', 'last_run_status', 'last_run_time'
        ]

    def get_last_run_status(self, obj):
        run = obj.runs.order_by('-created_at').first()
        return run.status if run else None

    def get_last_run_time(self, obj):
        run = obj.runs.order_by('-created_at').first()
        return run.created_at if run else None


class ScanRunSerializer(serializers.ModelSerializer):
    job_id = serializers.IntegerField(source='scan_job.id', read_only=True)
    project_name = serializers.CharField(source='scan_job.project.name', read_only=True)
    target_name = serializers.CharField(source='scan_job.target.name', read_only=True)
    profile_name = serializers.CharField(source='scan_job.profile.name', read_only=True)
    node_name = serializers.CharField(source='zap_node.name', read_only=True)
    findings_high = serializers.SerializerMethodField()
    findings_medium = serializers.SerializerMethodField()
    findings_low = serializers.SerializerMethodField()
    risk_score = serializers.SerializerMethodField()

    class Meta:
        model = ScanRun
        fields = [
            'id', 'job_id', 'project_name', 'target_name', 'profile_name', 'node_name', 'status',
            'started_at', 'finished_at', 'duration_ms', 'spider_progress', 'ascan_progress',
            'error_message', 'logs', 'findings_high', 'findings_medium', 'findings_low', 'risk_score'
        ]

    def get_findings_high(self, obj):
        return obj.findings.filter(severity='High').count()

    def get_findings_medium(self, obj):
        return obj.findings.filter(severity='Medium').count()

    def get_findings_low(self, obj):
        return obj.findings.filter(severity='Low').count()

    def get_risk_score(self, obj):
        snap = obj.risk_snapshots.order_by('-created_at').first()
        return str(snap.risk_score) if snap else '0'


class RawZapResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawZapResult
        fields = ['id', 'scan_job', 'scan_run', 'metadata', 'size_bytes', 'checksum', 'payload', 'fetched_at']


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ['id', 'scan_run', 'scan_job', 'html_file', 'json_file', 'pdf_file', 'created_at']
