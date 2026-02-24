from django.db import models


class Setting(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Setting'
        verbose_name_plural = 'Settings'

    def __str__(self):
        return self.key


class SetupState(models.Model):
    is_complete = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    wizard_data = models.JSONField(default=dict, blank=True)
    current_step = models.PositiveSmallIntegerField(default=1)
    pool_applied = models.BooleanField(default=True)
    pool_warning = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Setup state'
        verbose_name_plural = 'Setup states'

    def __str__(self):
        return f'Setup complete: {self.is_complete}'


class OpsAuditLog(models.Model):
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_DENIED = 'denied'
    STATUS_CHOICES = [
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_DENIED, 'Denied'),
    ]

    user = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, blank=True, null=True)
    action = models.CharField(max_length=120)
    target = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_SUCCESS)
    result = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.created_at:%Y-%m-%d %H:%M:%S} {self.action} ({self.status})'
