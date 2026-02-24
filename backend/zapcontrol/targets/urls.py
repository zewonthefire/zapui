from django.urls import path

from . import views

urlpatterns = [
    path('profiles', views.profiles, name='profiles'),
    path('scans', views.scans, name='scans'),
    path('scans/<int:scan_id>', views.scan_detail, name='scan-detail'),
    path('projects/<int:project_id>', views.project_detail, name='project-detail'),
    path('targets/<int:target_id>', views.target_detail, name='target-detail'),
]
