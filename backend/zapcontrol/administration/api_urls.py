from rest_framework.routers import DefaultRouter

from .views import AppSettingViewSet, AuditEventViewSet, GroupViewSet, UserViewSet, ZapNodeViewSet, ZapPoolViewSet

router = DefaultRouter()
router.register('users', UserViewSet, basename='admin-users')
router.register('groups', GroupViewSet, basename='admin-groups')
router.register('nodes', ZapNodeViewSet, basename='admin-nodes')
router.register('pools', ZapPoolViewSet, basename='admin-pools')
router.register('audit', AuditEventViewSet, basename='admin-audit')
router.register('settings', AppSettingViewSet, basename='admin-settings')

urlpatterns = router.urls
