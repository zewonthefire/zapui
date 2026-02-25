import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class AuditEvent(models.Model):
    ACTION_CREATE = 'create'
    ACTION_UPDATE = 'update'
    ACTION_DELETE = 'delete'
    ACTION_LOGIN = 'login'
    ACTION_LOGOUT = 'logout'
    ACTION_RUN_SCAN = 'run_scan'
    ACTION_HEALTHCHECK = 'healthcheck'
    ACTION_PURGE_RETENTION = 'purge_retention'
    ACTION_CHOICES = [
        (ACTION_CREATE, 'Create'),
        (ACTION_UPDATE, 'Update'),
        (ACTION_DELETE, 'Delete'),
        (ACTION_LOGIN, 'Login'),
        (ACTION_LOGOUT, 'Logout'),
        (ACTION_RUN_SCAN, 'Run scan'),
        (ACTION_HEALTHCHECK, 'Healthcheck'),
        (ACTION_PURGE_RETENTION, 'Purge retention'),
    ]

    STATUS_SUCCESS = 'success'
    STATUS_FAILURE = 'failure'
    STATUS_CHOICES = [
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILURE, 'Failure'),
    ]

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=64, choices=ACTION_CHOICES)
    object_type = models.CharField(max_length=128, blank=True)
    object_id = models.CharField(max_length=128, blank=True)
    object_repr = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    request_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_SUCCESS)
    message = models.CharField(max_length=255, blank=True)
    extra = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ('-created_at',)


class AppSetting(models.Model):
    TYPE_STRING = 'string'
    TYPE_INT = 'int'
    TYPE_BOOL = 'bool'
    TYPE_JSON = 'json'
    TYPE_SECRET = 'secret'
    TYPE_CHOICES = [
        (TYPE_STRING, 'String'),
        (TYPE_INT, 'Integer'),
        (TYPE_BOOL, 'Boolean'),
        (TYPE_JSON, 'JSON'),
        (TYPE_SECRET, 'Secret'),
    ]

    key = models.CharField(max_length=128, unique=True)
    value = models.TextField(blank=True)
    value_type = models.CharField(max_length=16, choices=TYPE_CHOICES, default=TYPE_STRING)
    description = models.CharField(max_length=255, blank=True)
    is_secret = models.BooleanField(default=False)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('key',)

    @property
    def masked_value(self):
        if self.is_secret or self.value_type == self.TYPE_SECRET:
            if not self.value:
                return ''
            return '********'
        return self.value

    def parsed_value(self):
        if self.value_type == self.TYPE_INT:
            return int(self.value)
        if self.value_type == self.TYPE_BOOL:
            return self.value.lower() in {'1', 'true', 'yes', 'on'}
        if self.value_type == self.TYPE_JSON:
            import json

            return json.loads(self.value or '{}')
        return self.value


class ZapPool(models.Model):
    STRATEGY_LEAST_LOADED = 'least_loaded'
    STRATEGY_ROUND_ROBIN = 'round_robin'
    STRATEGIES = [
        (STRATEGY_LEAST_LOADED, 'Least loaded'),
        (STRATEGY_ROUND_ROBIN, 'Round robin'),
    ]

    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    nodes = models.ManyToManyField('targets.ZapNode', related_name='zap_pools', blank=True)
    selection_strategy = models.CharField(max_length=32, choices=STRATEGIES, default=STRATEGY_LEAST_LOADED)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('name',)


def default_settings_definitions():
    return [
        ('retention_days_raw_results', '30', AppSetting.TYPE_INT, 'Retention for raw ZAP result payloads.'),
        ('retention_days_findings', '180', AppSetting.TYPE_INT, 'Retention for findings/reports where applicable.'),
        ('retention_days_audit', '365', AppSetting.TYPE_INT, 'Retention for audit records.'),
        ('risk_weight_high', '10', AppSetting.TYPE_INT, 'Risk weight for high findings.'),
        ('risk_weight_medium', '5', AppSetting.TYPE_INT, 'Risk weight for medium findings.'),
        ('risk_weight_low', '2', AppSetting.TYPE_INT, 'Risk weight for low findings.'),
        ('risk_weight_info', '1', AppSetting.TYPE_INT, 'Risk weight for informational findings.'),
        ('scan_timeout_minutes', '60', AppSetting.TYPE_INT, 'Default scan timeout in minutes.'),
        ('node_healthcheck_timeout_seconds', '8', AppSetting.TYPE_INT, 'ZAP node healthcheck timeout in seconds.'),
    ]


def retention_cutoff(days: int):
    return timezone.now() - timedelta(days=days)
