from django.urls import path

from . import views

urlpatterns = [
    path('dashboard/overview/', views.overview_page, name='dashboard-overview'),
    path('dashboard/risk/', views.risk_page, name='dashboard-risk'),
    path('dashboard/findings/', views.findings_page, name='dashboard-findings'),
    path('dashboard/coverage/', views.coverage_page, name='dashboard-coverage'),
    path('dashboard/changes/', views.changes_page, name='dashboard-changes'),
    path('dashboard/operations/', views.operations_page, name='dashboard-operations'),
    path('api/dashboard/overview/', views.overview_api, name='api-dashboard-overview'),
    path('api/dashboard/risk/', views.risk_api, name='api-dashboard-risk'),
    path('api/dashboard/findings/', views.findings_api, name='api-dashboard-findings'),
    path('api/dashboard/coverage/', views.coverage_api, name='api-dashboard-coverage'),
    path('api/dashboard/changes/', views.changes_api, name='api-dashboard-changes'),
    path('api/dashboard/operations/', views.operations_api, name='api-dashboard-operations'),
    path('api/context/options/', views.context_options_api, name='api-context-options'),
]
