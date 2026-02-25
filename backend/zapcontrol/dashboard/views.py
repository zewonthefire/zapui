from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from .services import (
    get_changes_data,
    get_context_options,
    get_coverage_data,
    get_findings_data,
    get_operations_data,
    get_overview_data,
    get_risk_data,
    parse_filters,
)


def _with_common_context(request, page_title: str, data: dict):
    filters = parse_filters(request.GET)
    context = {
        'page_title': page_title,
        'filters': filters,
        'context_options': get_context_options(filters),
        'data': data,
    }
    return context


@login_required
def overview_page(request):
    filters = parse_filters(request.GET)
    data = get_overview_data(filters)
    return render(request, 'dashboard/overview.html', _with_common_context(request, 'Dashboard Overview', data))


@login_required
def risk_page(request):
    filters = parse_filters(request.GET)
    data = get_risk_data(filters)
    return render(request, 'dashboard/risk.html', _with_common_context(request, 'Dashboard Risk', data))


@login_required
def findings_page(request):
    filters = parse_filters(request.GET)
    data = get_findings_data(filters)
    return render(request, 'dashboard/findings.html', _with_common_context(request, 'Dashboard Findings', data))


@login_required
def coverage_page(request):
    filters = parse_filters(request.GET)
    data = get_coverage_data(filters)
    return render(request, 'dashboard/coverage.html', _with_common_context(request, 'Dashboard Coverage', data))


@login_required
def changes_page(request):
    filters = parse_filters(request.GET)
    data = get_changes_data(filters)
    return render(request, 'dashboard/changes.html', _with_common_context(request, 'Dashboard Changes', data))


@login_required
def operations_page(request):
    filters = parse_filters(request.GET)
    data = get_operations_data(filters)
    return render(request, 'dashboard/operations.html', _with_common_context(request, 'Dashboard Operations', data))


@login_required
def context_options_api(request):
    filters = parse_filters(request.GET)
    return JsonResponse(get_context_options(filters))


@login_required
def overview_api(request):
    return JsonResponse(get_overview_data(parse_filters(request.GET)))


@login_required
def risk_api(request):
    return JsonResponse(get_risk_data(parse_filters(request.GET)))


@login_required
def findings_api(request):
    return JsonResponse(get_findings_data(parse_filters(request.GET)))


@login_required
def coverage_api(request):
    return JsonResponse(get_coverage_data(parse_filters(request.GET)))


@login_required
def changes_api(request):
    return JsonResponse(get_changes_data(parse_filters(request.GET)))


@login_required
def operations_api(request):
    return JsonResponse(get_operations_data(parse_filters(request.GET)))
