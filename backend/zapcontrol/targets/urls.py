from django.urls import path

from . import api_views, assets_views, views

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

    path('assets/', assets_views.assets_inventory, name='assets-inventory'),
    path('assets/<int:asset_id>/', assets_views.asset_detail, name='asset-detail'),
    path('assets/raw/', assets_views.raw_results_page, name='assets-raw-results'),
    path('assets/comparisons/', assets_views.comparisons_page, name='assets-comparisons'),

    path('api/context/projects', api_views.ContextProjectsApi.as_view()),
    path('api/context/targets', api_views.ContextTargetsApi.as_view()),
    path('api/context/assets', api_views.ContextAssetsApi.as_view()),
    path('api/context/nodes', api_views.ContextNodesApi.as_view()),
    path('api/context/profiles', api_views.ContextProfilesApi.as_view()),
    path('api/context/scans', api_views.ContextScansApi.as_view()),

    path('api/assets', api_views.AssetListApi.as_view()),
    path('api/assets/<int:asset_id>/findings', api_views.AssetFindingsApi.as_view()),
    path('api/scans', api_views.ScanListApi.as_view()),
    path('api/raw-results', api_views.RawResultsApi.as_view()),
    path('api/comparisons', api_views.ComparisonsApi.as_view()),
]
