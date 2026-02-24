from django.contrib import admin

from .models import Project, RawZapResult, ScanJob, ScanProfile, Target, ZapNode


@admin.register(ZapNode)
class ZapNodeAdmin(admin.ModelAdmin):
    list_display = ('name', 'base_url', 'managed_type', 'enabled', 'status', 'last_health_check', 'created_at')
    list_filter = ('managed_type', 'enabled', 'status')
    search_fields = ('name', 'base_url', 'docker_container_name')


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'owner', 'risk_level')
    search_fields = ('name', 'slug', 'owner')


@admin.register(Target)
class TargetAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'base_url', 'environment', 'auth_type')
    list_filter = ('environment', 'auth_type')
    search_fields = ('name', 'base_url', 'project__name', 'project__slug')


@admin.register(ScanProfile)
class ScanProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'scan_type', 'spider_enabled', 'max_duration_minutes', 'zap_node')
    list_filter = ('scan_type', 'spider_enabled')
    search_fields = ('name', 'description', 'project__name')


@admin.register(ScanJob)
class ScanJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'project', 'target', 'profile', 'zap_node', 'status', 'created_at', 'completed_at')
    list_filter = ('status', 'profile__scan_type')
    search_fields = ('target__name', 'project__name', 'error_message', 'zap_spider_id', 'zap_ascan_id')


@admin.register(RawZapResult)
class RawZapResultAdmin(admin.ModelAdmin):
    list_display = ('id', 'scan_job', 'fetched_at')
    search_fields = ('scan_job__id',)
