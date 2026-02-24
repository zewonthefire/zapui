from django.urls import path

from . import views

urlpatterns = [
    path('profiles', views.profiles, name='profiles'),
    path('scans', views.scans, name='scans'),
    path('scans/<int:scan_id>', views.scan_detail, name='scan-detail'),
]
