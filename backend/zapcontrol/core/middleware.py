from django.shortcuts import redirect

from .models import SetupState


class SetupWizardMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        state = SetupState.objects.filter(pk=1).first()
        is_complete = bool(state and state.is_complete)
        path = request.path
        exempt = (
            path.startswith('/setup')
            or path.startswith('/health')
            or path.startswith('/static/')
            or path.startswith('/media/')
            or path.startswith('/api/version')
        )
        if not is_complete and not exempt:
            return redirect('setup')
        return self.get_response(request)
