import csv
import io

import requests
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, Permission
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from targets.models import ZapNode

from .models import AppSetting, AuditEvent, ZapPool
from .permissions import IsAuditReader, IsScanAdmin, IsSystemAdmin, is_audit_reader, is_scan_admin, is_system_admin
from .serializers import (
    AppSettingSerializer,
    AppSettingUpdateSerializer,
    AuditEventSerializer,
    GroupPermissionSerializer,
    GroupSerializer,
    UserCreateSerializer,
    UserSerializer,
    ZapNodeSerializer,
    ZapPoolSerializer,
)
from .services import audit_log, db_connection_sanity, decrypt_api_key, encrypt_api_key, setting_int


def _page(request, qs, per_page=20):
    paginator = Paginator(qs, per_page)
    return paginator.get_page(request.GET.get('page') or 1)


def _order_param(request, allowed, default='id'):
    order = request.GET.get('ordering') or default
    if order.lstrip('-') not in allowed:
        return default
    return order


@login_required
@require_http_methods(['GET', 'POST'])
def users_list(request):
    if not is_system_admin(request.user):
        return HttpResponse(status=403)
    if request.method == 'POST':
        password = request.POST.get('password') or get_user_model().objects.make_random_password()
        user = get_user_model().objects.create_user(email=request.POST['email'], password=password, is_active=True)
        group_ids = request.POST.getlist('groups')
        user.groups.set(Group.objects.filter(pk__in=group_ids))
        audit_log(request.user, AuditEvent.ACTION_CREATE, user, request=request, message='Created user')
        messages.success(request, 'User created')
        return redirect('administration:users')

    qs = get_user_model().objects.prefetch_related('groups').all()
    search = request.GET.get('search', '').strip()
    if search:
        qs = qs.filter(Q(email__icontains=search))
    is_active = request.GET.get('is_active', '')
    if is_active in {'true', 'false'}:
        qs = qs.filter(is_active=(is_active == 'true'))
    group_id = request.GET.get('group', '')
    if group_id:
        qs = qs.filter(groups__id=group_id)
    qs = qs.order_by(_order_param(request, {'email', 'last_login', 'date_joined', 'is_active'}, 'email')).distinct()
    return render(request, 'administration/users_list.html', {'page_obj': _page(request, qs), 'groups': Group.objects.all()})


@login_required
def user_detail(request, user_id):
    if not is_system_admin(request.user):
        return HttpResponse(status=403)
    user_obj = get_object_or_404(get_user_model(), pk=user_id)
    if request.method == 'POST':
        user_obj.email = request.POST.get('email', user_obj.email)
        user_obj.is_active = request.POST.get('is_active') == 'on'
        user_obj.save(update_fields=['email', 'is_active'])
        user_obj.groups.set(Group.objects.filter(pk__in=request.POST.getlist('groups')))
        new_password = request.POST.get('new_password', '').strip()
        if new_password:
            user_obj.set_password(new_password)
            user_obj.save(update_fields=['password'])
        audit_log(request.user, AuditEvent.ACTION_UPDATE, user_obj, request=request, extra={'groups': list(user_obj.groups.values_list('name', flat=True))})
        messages.success(request, 'User updated')
        return redirect('administration:user-detail', user_id=user_obj.id)
    return render(request, 'administration/user_detail.html', {'managed_user': user_obj, 'groups': Group.objects.all()})


@login_required
@require_http_methods(['POST'])
def user_toggle_active(request, user_id):
    if not is_system_admin(request.user):
        return HttpResponse(status=403)
    user_obj = get_object_or_404(get_user_model(), pk=user_id)
    user_obj.is_active = request.POST.get('active') == 'true'
    user_obj.save(update_fields=['is_active'])
    audit_log(request.user, AuditEvent.ACTION_UPDATE, user_obj, request=request, message='Toggled user active')
    return JsonResponse({'ok': True})


@login_required
@require_http_methods(['GET', 'POST'])
def groups_list(request):
    if not is_system_admin(request.user):
        return HttpResponse(status=403)
    if request.method == 'POST':
        group, _ = Group.objects.get_or_create(name=request.POST['name'].strip())
        audit_log(request.user, AuditEvent.ACTION_CREATE, group, request=request)
        return redirect('administration:groups')
    groups = Group.objects.annotate(members_count=Count('user')).order_by('name')
    return render(request, 'administration/groups_list.html', {'groups': groups, 'permissions': Permission.objects.order_by('content_type__app_label', 'codename')})


@login_required
@require_http_methods(['POST'])
def group_permissions(request, group_id):
    if not is_system_admin(request.user):
        return HttpResponse(status=403)
    group = get_object_or_404(Group, pk=group_id)
    perm_ids = request.POST.getlist('permission_ids')
    group.permissions.set(Permission.objects.filter(id__in=perm_ids))
    audit_log(request.user, AuditEvent.ACTION_UPDATE, group, request=request, message='Updated group permissions')
    return redirect('administration:groups')


def _node_queryset(request):
    qs = ZapNode.objects.all()
    search = request.GET.get('search', '').strip()
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(base_url__icontains=search))
    if request.GET.get('is_active') in {'true', 'false'}:
        qs = qs.filter(is_active=request.GET['is_active'] == 'true')
    if request.GET.get('health_status'):
        qs = qs.filter(health_status=request.GET['health_status'])
    if request.GET.get('tags'):
        qs = qs.filter(tags__contains=[request.GET['tags']])
    return qs


@login_required
@require_http_methods(['GET', 'POST'])
def nodes_list(request):
    if not is_scan_admin(request.user):
        return HttpResponse(status=403)
    if request.method == 'POST':
        node = ZapNode(
            name=request.POST['name'],
            base_url=request.POST['base_url'],
            api_key=encrypt_api_key(request.POST.get('api_key', '')),
            is_active=request.POST.get('is_active') == 'on',
            max_concurrent=int(request.POST.get('max_concurrent') or 1),
            tags=[t.strip() for t in request.POST.get('tags', '').split(',') if t.strip()],
        )
        node.save()
        audit_log(request.user, AuditEvent.ACTION_CREATE, node, request=request)
        return redirect('administration:nodes')
    qs = _node_queryset(request).order_by(_order_param(request, {'name', 'base_url', 'is_active', 'health_status', 'updated_at'}, 'name'))
    return render(request, 'administration/nodes_list.html', {'page_obj': _page(request, qs)})


@login_required
@require_http_methods(['POST'])
def node_healthcheck(request, node_id):
    if not is_scan_admin(request.user):
        return HttpResponse(status=403)
    node = get_object_or_404(ZapNode, pk=node_id)
    timeout_seconds = setting_int('node_healthcheck_timeout_seconds', 8)
    try:
        params = {'apikey': decrypt_api_key(node.api_key)} if node.api_key else None
        response = requests.get(f"{node.base_url.rstrip('/')}/JSON/core/view/version/", params=params, timeout=timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        node.health_status = 'healthy'
        node.last_seen_at = timezone.now()
        node.last_error = ''
        node.version = payload.get('version', '')
        node.save(update_fields=['health_status', 'last_seen_at', 'last_error', 'version', 'updated_at'])
        audit_log(request.user, AuditEvent.ACTION_HEALTHCHECK, node, request=request, message='Node healthy')
        return JsonResponse({'status': 'healthy', 'version': node.version})
    except Exception as exc:
        node.health_status = 'unhealthy'
        node.last_error = str(exc)[:500]
        node.save(update_fields=['health_status', 'last_error', 'updated_at'])
        audit_log(
            request.user,
            AuditEvent.ACTION_HEALTHCHECK,
            node,
            status=AuditEvent.STATUS_FAILURE,
            request=request,
            message='Node healthcheck failed',
            extra={'error': str(exc)},
        )
        return JsonResponse({'status': 'unhealthy', 'error': str(exc)}, status=400)


@login_required
@require_http_methods(['GET', 'POST'])
def pools_list(request):
    if not is_scan_admin(request.user):
        return HttpResponse(status=403)
    if request.method == 'POST':
        pool = ZapPool.objects.create(
            name=request.POST['name'],
            description=request.POST.get('description', ''),
            selection_strategy=request.POST.get('selection_strategy', ZapPool.STRATEGY_LEAST_LOADED),
            is_active=request.POST.get('is_active') == 'on',
        )
        pool.nodes.set(ZapNode.objects.filter(pk__in=request.POST.getlist('nodes')))
        audit_log(request.user, AuditEvent.ACTION_CREATE, pool, request=request)
        return redirect('administration:pools')
    pools = ZapPool.objects.prefetch_related('nodes').order_by('name')
    return render(request, 'administration/pools_list.html', {'pools': pools, 'nodes': ZapNode.objects.order_by('name')})


@login_required
@require_http_methods(['GET', 'POST'])
def settings_page(request):
    if not is_system_admin(request.user):
        return HttpResponse(status=403)
    if request.method == 'POST':
        setting = get_object_or_404(AppSetting, pk=request.POST['setting_id'])
        before = setting.value
        setting.value = request.POST.get('value', '')
        setting.updated_by = request.user
        setting.save(update_fields=['value', 'updated_by', 'updated_at'])
        audit_log(request.user, AuditEvent.ACTION_UPDATE, setting, request=request, extra={'before': before, 'after': setting.value})
        return redirect('administration:settings')
    return render(request, 'administration/settings.html', {'settings': AppSetting.objects.order_by('key')})


@login_required
def db_sanity(request):
    if not is_system_admin(request.user):
        return HttpResponse(status=403)
    ok = db_connection_sanity()
    return JsonResponse({'ok': ok})


@login_required
def run_purge_retention(request):
    if not is_system_admin(request.user):
        return HttpResponse(status=403)
    from django.core.management import call_command

    call_command('purge_retention')
    audit_log(request.user, AuditEvent.ACTION_PURGE_RETENTION, status=AuditEvent.STATUS_SUCCESS, request=request, message='Triggered retention purge')
    messages.success(request, 'Retention purge executed')
    return redirect('administration:settings')


@login_required
def audit_list(request):
    if not is_audit_reader(request.user):
        return HttpResponse(status=403)
    qs = AuditEvent.objects.select_related('actor').all()
    if request.GET.get('actor'):
        qs = qs.filter(actor_id=request.GET['actor'])
    if request.GET.get('action'):
        qs = qs.filter(action=request.GET['action'])
    if request.GET.get('status'):
        qs = qs.filter(status=request.GET['status'])
    if request.GET.get('object_type'):
        qs = qs.filter(object_type=request.GET['object_type'])
    if request.GET.get('q'):
        q = request.GET['q']
        qs = qs.filter(Q(message__icontains=q) | Q(object_repr__icontains=q))
    if request.GET.get('start'):
        qs = qs.filter(created_at__date__gte=request.GET['start'])
    if request.GET.get('end'):
        qs = qs.filter(created_at__date__lte=request.GET['end'])
    return render(
        request,
        'administration/audit_list.html',
        {
            'page_obj': _page(request, qs.order_by(_order_param(request, {'created_at', 'action', 'status'}, '-created_at'))),
            'actors': get_user_model().objects.order_by('email'),
        },
    )


@login_required
def audit_export_csv(request):
    if not is_audit_reader(request.user):
        return HttpResponse(status=403)

    def _rows():
        pseudo = io.StringIO()
        writer = csv.writer(pseudo)
        writer.writerow(['created_at', 'actor', 'action', 'status', 'object_type', 'object_id', 'message'])
        yield pseudo.getvalue()
        pseudo.seek(0)
        pseudo.truncate(0)
        for event in AuditEvent.objects.select_related('actor').order_by('-created_at').iterator(chunk_size=500):
            writer.writerow([
                event.created_at.isoformat(),
                event.actor.email if event.actor else '',
                event.action,
                event.status,
                event.object_type,
                event.object_id,
                event.message,
            ])
            yield pseudo.getvalue()
            pseudo.seek(0)
            pseudo.truncate(0)

    response = StreamingHttpResponse(_rows(), content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="audit_events.csv"'
    return response


class UserViewSet(viewsets.ModelViewSet):
    queryset = get_user_model().objects.prefetch_related('groups').all()
    permission_classes = [IsAuthenticated, IsSystemAdmin]

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.GET.get('search'):
            qs = qs.filter(email__icontains=self.request.GET['search'])
        if self.request.GET.get('is_active') in {'true', 'false'}:
            qs = qs.filter(is_active=self.request.GET['is_active'] == 'true')
        if self.request.GET.get('group'):
            qs = qs.filter(groups__id=self.request.GET['group'])
        ordering = _order_param(self.request, {'email', 'last_login', 'date_joined', 'is_active'}, 'email')
        return qs.order_by(ordering).distinct()

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        user = self.get_object()
        user.is_active = True
        user.save(update_fields=['is_active'])
        audit_log(request.user, AuditEvent.ACTION_UPDATE, user, request=request, message='User activated')
        return Response({'status': 'ok'})

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        user = self.get_object()
        user.is_active = False
        user.save(update_fields=['is_active'])
        audit_log(request.user, AuditEvent.ACTION_UPDATE, user, request=request, message='User deactivated')
        return Response({'status': 'ok'})

    @action(detail=True, methods=['post'], url_path='set-password')
    def set_password(self, request, pk=None):
        user = self.get_object()
        password = request.data.get('password', '')
        if not password:
            return Response({'detail': 'password required'}, status=400)
        user.set_password(password)
        user.save(update_fields=['password'])
        audit_log(request.user, AuditEvent.ACTION_UPDATE, user, request=request, message='Password changed')
        return Response({'status': 'ok'})


class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all().order_by('name')
    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated, IsSystemAdmin]

    @action(detail=True, methods=['put'])
    def permissions(self, request, pk=None):
        group = self.get_object()
        serializer = GroupPermissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        group.permissions.set(Permission.objects.filter(id__in=serializer.validated_data['permission_ids']))
        audit_log(request.user, AuditEvent.ACTION_UPDATE, group, request=request, message='Updated permissions')
        return Response({'status': 'ok'})


class ZapNodeViewSet(viewsets.ModelViewSet):
    queryset = ZapNode.objects.all()
    serializer_class = ZapNodeSerializer
    permission_classes = [IsAuthenticated, IsScanAdmin]

    def get_queryset(self):
        return _node_queryset(self.request).order_by(_order_param(self.request, {'name', 'base_url', 'health_status', 'updated_at'}, 'name'))

    @action(detail=True, methods=['post'])
    def healthcheck(self, request, pk=None):
        dj_response = node_healthcheck(request._request, pk)
        import json

        data = json.loads(dj_response.content.decode('utf-8'))
        return Response(data, status=dj_response.status_code)


class ZapPoolViewSet(viewsets.ModelViewSet):
    queryset = ZapPool.objects.all().order_by('name')
    serializer_class = ZapPoolSerializer
    permission_classes = [IsAuthenticated, IsScanAdmin]

    @action(detail=True, methods=['put'])
    def nodes(self, request, pk=None):
        pool = self.get_object()
        ids = request.data.get('node_ids', [])
        pool.nodes.set(ZapNode.objects.filter(id__in=ids))
        audit_log(request.user, AuditEvent.ACTION_UPDATE, pool, request=request)
        return Response({'status': 'ok'})


class AuditEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditEvent.objects.select_related('actor').all()
    serializer_class = AuditEventSerializer
    permission_classes = [IsAuthenticated, IsAuditReader]

    def get_queryset(self):
        qs = super().get_queryset()
        for key in ['actor', 'action', 'status', 'object_type']:
            if self.request.GET.get(key):
                qs = qs.filter(**{key: self.request.GET[key]})
        if self.request.GET.get('search'):
            qs = qs.filter(Q(message__icontains=self.request.GET['search']) | Q(object_repr__icontains=self.request.GET['search']))
        return qs.order_by(_order_param(self.request, {'created_at', 'action', 'status'}, '-created_at'))


class AppSettingViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AppSetting.objects.all().order_by('key')
    serializer_class = AppSettingSerializer
    permission_classes = [IsAuthenticated, IsSystemAdmin]

    @action(detail=True, methods=['put'])
    def value(self, request, pk=None):
        setting = self.get_object()
        serializer = AppSettingUpdateSerializer(setting, data=request.data)
        serializer.is_valid(raise_exception=True)
        before = setting.value
        serializer.save(updated_by=request.user)
        audit_log(request.user, AuditEvent.ACTION_UPDATE, setting, request=request, extra={'before': before, 'after': setting.value})
        return Response(AppSettingSerializer(setting).data)
