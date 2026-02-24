from django.db import models


class ZapNode(models.Model):
    base_url = models.URLField(unique=True)
    api_key = models.CharField(max_length=255, blank=True)
    is_internal = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.base_url
