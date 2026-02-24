from django.http import JsonResponse, HttpResponse


def health(request):
    return JsonResponse({'status': 'ok'})


def setup(request):
    return HttpResponse('Wizard not implemented yet', content_type='text/plain')


def index(request):
    return HttpResponse('Not configured', content_type='text/plain')
