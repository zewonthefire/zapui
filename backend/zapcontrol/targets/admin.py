from django.contrib import admin

from .models import Project, Target, ZapNode


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
