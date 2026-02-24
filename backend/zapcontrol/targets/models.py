from django.db import models


class ZapNode(models.Model):
    MANAGED_INTERNAL = 'internal_managed'
    MANAGED_EXTERNAL = 'external'
    MANAGED_TYPE_CHOICES = [
        (MANAGED_INTERNAL, 'Internal managed'),
        (MANAGED_EXTERNAL, 'External'),
    ]

    STATUS_UNKNOWN = 'unknown'
    STATUS_HEALTHY = 'healthy'
    STATUS_UNREACHABLE = 'unreachable'
    STATUS_DISABLED = 'disabled'
    STATUS_CHOICES = [
        (STATUS_UNKNOWN, 'Unknown'),
        (STATUS_HEALTHY, 'Healthy'),
        (STATUS_UNREACHABLE, 'Unreachable'),
        (STATUS_DISABLED, 'Disabled'),
    ]

    name = models.CharField(max_length=120, unique=True)
    base_url = models.URLField(unique=True)
    api_key = models.CharField(max_length=255, blank=True)
    enabled = models.BooleanField(default=True)
    managed_type = models.CharField(max_length=32, choices=MANAGED_TYPE_CHOICES, default=MANAGED_EXTERNAL)
    docker_container_name = models.CharField(max_length=255, blank=True, null=True)
    version = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_health_check = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_UNKNOWN)
    last_latency_ms = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class Project(models.Model):
    RISK_LOW = 'low'
    RISK_MEDIUM = 'medium'
    RISK_HIGH = 'high'
    RISK_CHOICES = [
        (RISK_LOW, 'Low'),
        (RISK_MEDIUM, 'Medium'),
        (RISK_HIGH, 'High'),
    ]

    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    owner = models.CharField(max_length=255, blank=True)
    risk_level = models.CharField(max_length=16, choices=RISK_CHOICES, default=RISK_MEDIUM)
    tags = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class Target(models.Model):
    ENV_DEV = 'dev'
    ENV_STAGE = 'stage'
    ENV_PROD = 'prod'
    ENV_CHOICES = [
        (ENV_DEV, 'Development'),
        (ENV_STAGE, 'Staging'),
        (ENV_PROD, 'Production'),
    ]

    AUTH_NONE = 'none'
    AUTH_BASIC = 'basic'
    AUTH_BEARER = 'bearer'
    AUTH_COOKIE = 'cookie'
    AUTH_TYPE_CHOICES = [
        (AUTH_NONE, 'None'),
        (AUTH_BASIC, 'Basic'),
        (AUTH_BEARER, 'Bearer'),
        (AUTH_COOKIE, 'Cookie'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='targets')
    name = models.CharField(max_length=120)
    base_url = models.URLField()
    environment = models.CharField(max_length=16, choices=ENV_CHOICES, default=ENV_DEV)
    auth_type = models.CharField(max_length=16, choices=AUTH_TYPE_CHOICES, default=AUTH_NONE)
    auth_config = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('project', 'name')
        ordering = ('project__name', 'name')

    def __str__(self):
        return f'{self.project.slug}:{self.name}'
