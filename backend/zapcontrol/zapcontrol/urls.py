from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from core import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(pattern_name='dashboard', permanent=False)),
    path('', include('accounts.urls')),
    path('', include('targets.urls')),
    path('health', views.health, name='health'),
    path('setup', views.setup, name='setup'),
    path('setup/zap-status', views.setup_zap_status, name='setup-zap-status'),
    path('dashboard', views.dashboard, name='dashboard'),
    path('management', views.management_center, name='management-center'),
    path('ops/overview', views.ops_overview, name='ops-overview'),
    path('zapnodes', views.zapnodes, name='zapnodes'),
    path('ops/logs/<str:service>', views.ops_logs, name='ops-logs'),
    path('ops/actions', views.ops_actions, name='ops-actions'),
    path('api/version', views.api_version, name='api-version'),
]
