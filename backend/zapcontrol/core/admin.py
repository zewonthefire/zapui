from django.contrib import admin

from .models import Setting, SetupState


@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'updated_at')
    search_fields = ('key',)


@admin.register(SetupState)
class SetupStateAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_complete', 'current_step', 'pool_applied', 'updated_at')
