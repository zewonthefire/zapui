from django.urls import path

from . import api_views, assets_views, views

urlpatterns = [
    path('scans/context-bar/', views.scans_context_bar, name='scans-context-bar'),
    path('scans/config/projects/', views.scans_projects, name='scans-config-projects'),
    path('scans/config/targets/', views.scans_targets, name='scans-config-targets'),
    path('scans/config/profiles/', views.scans_profiles, name='scans-config-profiles'),
    path('scans/jobs/', views.scans_jobs, name='scans-jobs'),
    path('scans/runs/', views.scans_runs, name='scans-runs'),
    path('scans/runs/<int:id>/', views.scans_run_detail, name='scans-run-detail'),
    path('scans/runs/<int:id>/report/<str:report_format>/', views.scan_report_download, name='scans-run-report-download'),
    path('scans/reports/', views.scans_reports, name='scans-reports'),

    path('assets/', assets_views.assets_inventory, name='assets-inventory'),

    path('api/context/projects', api_views.ContextProjectsApi.as_view()),
    path('api/context/targets', api_views.ContextTargetsApi.as_view()),
    path('api/context/assets', api_views.ContextAssetsApi.as_view()),
    path('api/context/nodes', api_views.ContextNodesApi.as_view()),
    path('api/context/profiles', api_views.ContextProfilesApi.as_view()),
    path('api/context/scans', api_views.ContextScansApi.as_view()),

    path('api/scans/jobs', api_views.JobsApi.as_view()),
    path('api/scans/runs', api_views.RunsApi.as_view()),
    path('api/scans/runs/<int:pk>', api_views.RunDetailApi.as_view()),
    path('api/scans/runs/<int:id>/findings', api_views.RunFindingsApi.as_view()),
    path('api/scans/runs/<int:id>/raw', api_views.RunRawApi.as_view()),
    path('api/scans/runs/<int:id>/report', api_views.RunReportApi.as_view()),
    path('api/scans/enqueue', api_views.EnqueueApi.as_view()),
]
