from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from core import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(pattern_name='dashboard', permanent=False)),
    path('', include('accounts.urls')),
    path('health', views.health, name='health'),
    path('setup', views.setup, name='setup'),
    path('dashboard', views.dashboard, name='dashboard'),
    path('api/version', views.api_version, name='api-version'),
]
