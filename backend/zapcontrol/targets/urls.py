from django.urls import path

from . import views

urlpatterns = [
    path('profiles', views.profiles, name='profiles'),
    path('scans', views.scans, name='scans'),
    path('scans/<int:scan_id>', views.scan_detail, name='scan-detail'),
    path('scans/<int:scan_id>/report/<str:report_format>', views.report_download, name='report-download'),
    path('reports', views.reports_list, name='reports-list'),
    path('projects/<int:project_id>', views.project_detail, name='project-detail'),
    path('targets/<int:target_id>', views.target_detail, name='target-detail'),
    path('targets/<int:target_id>/evolution', views.target_evolution, name='target-evolution'),
    path('targets/<int:target_id>/evolution/<int:comparison_id>', views.target_diff_detail, name='target-diff-detail'),
]
