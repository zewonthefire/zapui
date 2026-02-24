from django.contrib import admin

from .models import AppSetting, SetupState


@admin.register(AppSetting)
class AppSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'updated_at')
    search_fields = ('key',)


@admin.register(SetupState)
class SetupStateAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_complete', 'updated_at')
