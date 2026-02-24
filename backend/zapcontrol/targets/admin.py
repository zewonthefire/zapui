from django.contrib import admin

from .models import ZapNode


@admin.register(ZapNode)
class ZapNodeAdmin(admin.ModelAdmin):
    list_display = ('base_url', 'is_internal', 'is_active', 'created_at')
