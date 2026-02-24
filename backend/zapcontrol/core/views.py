from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


def health(request):
    return JsonResponse({'status': 'ok'})


def setup(request):
    return JsonResponse({'status': 'pending', 'message': 'Wizard not implemented yet'})


@login_required
def dashboard(request):
    return render(request, 'core/dashboard.html')


@api_view(['GET'])
@permission_classes([AllowAny])
def api_version(request):
    return Response({'name': 'zapcontrol', 'version': settings.APP_VERSION})
