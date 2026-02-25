from django.urls import path

from . import views

app_name = 'administration'

urlpatterns = [
    path('users/', views.users_list, name='users'),
    path('users/<int:user_id>/', views.user_detail, name='user-detail'),
    path('users/<int:user_id>/toggle-active/', views.user_toggle_active, name='user-toggle-active'),
    path('groups/', views.groups_list, name='groups'),
    path('groups/<int:group_id>/permissions/', views.group_permissions, name='group-permissions'),
    path('nodes/', views.nodes_list, name='nodes'),
    path('nodes/<int:node_id>/healthcheck/', views.node_healthcheck, name='node-healthcheck'),
    path('pools/', views.pools_list, name='pools'),
    path('settings/', views.settings_page, name='settings'),
    path('settings/db-sanity/', views.db_sanity, name='db-sanity'),
    path('settings/purge-retention/', views.run_purge_retention, name='purge-retention'),
    path('audit/', views.audit_list, name='audit'),
    path('audit/export.csv', views.audit_export_csv, name='audit-export'),
]
