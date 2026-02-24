from django.db import models


class AppSetting(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'App setting'
        verbose_name_plural = 'App settings'

    def __str__(self):
        return self.key


class SetupState(models.Model):
    is_complete = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Setup state'
        verbose_name_plural = 'Setup states'

    def __str__(self):
        return f'Setup complete: {self.is_complete}'
