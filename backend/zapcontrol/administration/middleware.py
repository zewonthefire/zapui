import uuid

from django.utils.deprecation import MiddlewareMixin

from .models import AuditEvent
from .services import audit_log


class RequestAuditMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.request_id = uuid.uuid4()
        request.audit_ip = request.META.get('REMOTE_ADDR')
        request.audit_user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]

    def process_response(self, request, response):
        if (
            request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}
            and request.path.startswith('/administration')
            and getattr(request, 'user', None)
            and request.user.is_authenticated
        ):
            action = {
                'POST': AuditEvent.ACTION_CREATE,
                'PUT': AuditEvent.ACTION_UPDATE,
                'PATCH': AuditEvent.ACTION_UPDATE,
                'DELETE': AuditEvent.ACTION_DELETE,
            }.get(request.method, AuditEvent.ACTION_UPDATE)
            status = AuditEvent.STATUS_SUCCESS if response.status_code < 400 else AuditEvent.STATUS_FAILURE
            audit_log(
                request.user,
                action,
                status=status,
                request=request,
                message=f'{request.method} {request.path}',
                extra={'status_code': response.status_code},
            )
        return response
