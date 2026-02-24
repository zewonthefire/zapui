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


class ScanProfile(models.Model):
    TYPE_BASELINE_LIKE = 'baseline_like'
    TYPE_FULL_ACTIVE = 'full_active'
    TYPE_API_SCAN = 'api_scan'
    SCAN_TYPE_CHOICES = [
        (TYPE_BASELINE_LIKE, 'Baseline-like'),
        (TYPE_FULL_ACTIVE, 'Full active'),
        (TYPE_API_SCAN, 'API scan'),
    ]

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='scan_profiles', blank=True, null=True)
    zap_node = models.ForeignKey(ZapNode, on_delete=models.SET_NULL, related_name='scan_profiles', blank=True, null=True)
    scan_type = models.CharField(max_length=32, choices=SCAN_TYPE_CHOICES, default=TYPE_BASELINE_LIKE)
    spider_enabled = models.BooleanField(default=True)
    max_duration_minutes = models.PositiveIntegerField(default=30)
    extra_zap_options = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('name',)
        unique_together = ('project', 'name')

    def __str__(self):
        return self.name


class ScanJob(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='scan_jobs')
    target = models.ForeignKey(Target, on_delete=models.CASCADE, related_name='scan_jobs')
    profile = models.ForeignKey(ScanProfile, on_delete=models.PROTECT, related_name='scan_jobs')
    initiated_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, related_name='initiated_scan_jobs', blank=True, null=True)
    zap_node = models.ForeignKey(ZapNode, on_delete=models.SET_NULL, related_name='scan_jobs', blank=True, null=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    error_message = models.TextField(blank=True)
    zap_spider_id = models.CharField(max_length=64, blank=True)
    zap_ascan_id = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'Job #{self.id} {self.target}'


class RawZapResult(models.Model):
    scan_job = models.ForeignKey(ScanJob, on_delete=models.CASCADE, related_name='raw_results')
    raw_alerts = models.JSONField(default=list, blank=True)
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-fetched_at',)

    def __str__(self):
        return f'Raw alerts for job #{self.scan_job_id}'


class Finding(models.Model):
    target = models.ForeignKey(Target, on_delete=models.CASCADE, related_name='findings')
    scan_job = models.ForeignKey(ScanJob, on_delete=models.SET_NULL, related_name='findings', blank=True, null=True)
    zap_plugin_id = models.CharField(max_length=64)
    title = models.CharField(max_length=255)
    severity = models.CharField(max_length=16, default='Info')
    description = models.TextField(blank=True)
    solution = models.TextField(blank=True)
    reference = models.TextField(blank=True)
    cwe_id = models.CharField(max_length=32, blank=True)
    wasc_id = models.CharField(max_length=32, blank=True)
    first_seen = models.DateTimeField()
    last_seen = models.DateTimeField()
    instances_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('target', 'zap_plugin_id', 'title')
        ordering = ('-last_seen',)

    def __str__(self):
        return f'{self.target_id}:{self.title}'


class FindingInstance(models.Model):
    finding = models.ForeignKey(Finding, on_delete=models.CASCADE, related_name='instances')
    scan_job = models.ForeignKey(ScanJob, on_delete=models.CASCADE, related_name='finding_instances')
    url = models.URLField(max_length=2048, blank=True)
    parameter = models.CharField(max_length=255, blank=True)
    evidence = models.TextField(blank=True)
    attack = models.TextField(blank=True)
    other = models.TextField(blank=True)
    method = models.CharField(max_length=16, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('finding', 'scan_job', 'url', 'parameter', 'evidence')
        ordering = ('-created_at',)


class RiskSnapshot(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='risk_snapshots', blank=True, null=True)
    target = models.ForeignKey(Target, on_delete=models.CASCADE, related_name='risk_snapshots', blank=True, null=True)
    scan_job = models.ForeignKey(ScanJob, on_delete=models.CASCADE, related_name='risk_snapshots')
    risk_score = models.DecimalField(max_digits=12, decimal_places=2)
    counts_by_severity = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
