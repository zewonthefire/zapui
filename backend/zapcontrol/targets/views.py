import json
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Project, Report, ScanJob, ScanProfile, ScanRun, Target, ZapNode
from .scan_engine import enqueue_scan


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'slug', 'description', 'owner', 'risk_level', 'tags']


class TargetForm(forms.ModelForm):
    class Meta:
        model = Target
        fields = ['project', 'name', 'base_url', 'include_regex', 'exclude_regex', 'enabled', 'environment', 'auth_type', 'auth_config', 'notes']


class ScanProfileForm(forms.ModelForm):
    class Meta:
        model = ScanProfile
        fields = ['name', 'description', 'project', 'zap_node', 'scan_type', 'spider_enabled', 'max_duration_minutes', 'config', 'zap_policy_name']


class ScanJobForm(forms.ModelForm):
    class Meta:
        model = ScanJob
        fields = [
            'project', 'target', 'profile', 'node_strategy', 'zap_node',
            'schedule_type', 'schedule_interval_minutes', 'schedule_weekday', 'schedule_time', 'enabled'
        ]


def _has_group(user, group_name: str) -> bool:
    return user.is_superuser or user.groups.filter(name=group_name).exists()


def _require_operator(request):
    return _has_group(request.user, 'scan_operator') or _has_group(request.user, 'scan_admin')


def _require_admin(request):
    return _has_group(request.user, 'scan_admin')


@login_required
def scans_context_bar(request):
    return render(request, 'targets/scans/_context_bar.html', {
        'projects': Project.objects.order_by('name'),
        'targets': Target.objects.order_by('name')[:100],
        'profiles': ScanProfile.objects.order_by('name')[:100],
        'nodes': ZapNode.objects.filter(enabled=True).order_by('name'),
    })


@login_required
def scans_projects(request):
    if not _require_admin(request):
        raise Http404
    form = ProjectForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('scans-config-projects')
    return render(request, 'targets/scans/projects.html', {'form': form, 'items': Project.objects.order_by('name')})


@login_required
def scans_targets(request):
    if not _require_admin(request):
        raise Http404
    form = TargetForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('scans-config-targets')
    return render(request, 'targets/scans/targets.html', {'form': form, 'items': Target.objects.select_related('project').order_by('project__name', 'name')})


@login_required
def scans_profiles(request):
    if not _require_admin(request):
        raise Http404
    form = ScanProfileForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('scans-config-profiles')
    return render(request, 'targets/scans/profiles.html', {'form': form, 'items': ScanProfile.objects.select_related('project', 'zap_node').order_by('name')})


@login_required
def scans_jobs(request):
    if request.method == 'POST':
        if 'run_now' in request.POST and _require_operator(request):
            enqueue_scan(int(request.POST['run_now']))
            messages.success(request, 'Scan run queued.')
            return redirect('scans-jobs')
        if 'toggle' in request.POST and _require_admin(request):
            job = get_object_or_404(ScanJob, pk=request.POST['toggle'])
            job.enabled = not job.enabled
            job.save(update_fields=['enabled'])
            return redirect('scans-jobs')
        if _require_admin(request):
            form = ScanJobForm(request.POST)
            if form.is_valid():
                job = form.save(commit=False)
                job.initiated_by = request.user
                job.save()
                return redirect('scans-jobs')
    form = ScanJobForm()
    jobs = ScanJob.objects.select_related('project', 'target', 'profile', 'zap_node').prefetch_related('runs').order_by('-created_at')
    return render(request, 'targets/scans/jobs.html', {'form': form, 'jobs': jobs})


@login_required
def scans_runs(request):
    qs = ScanRun.objects.select_related('scan_job__project', 'scan_job__target', 'scan_job__profile', 'zap_node').order_by('-created_at')
    if request.GET.get('status'):
        qs = qs.filter(status=request.GET['status'])
    return render(request, 'targets/scans/runs.html', {'runs': qs[:200]})


@login_required
def scans_run_detail(request, id: int):
    run = get_object_or_404(ScanRun.objects.select_related('scan_job__target', 'scan_job__project', 'scan_job__profile', 'zap_node'), pk=id)
    tab = request.GET.get('tab', 'summary')
    latest_raw = run.raw_results.order_by('-fetched_at').first()
    findings = run.findings.order_by('-severity', '-last_seen')
    report = run.reports.order_by('-created_at').first()
    return render(
        request,
        'targets/scans/run_detail.html',
        {'run': run, 'tab': tab, 'latest_raw': latest_raw, 'findings': findings, 'report': report, 'raw_json': json.dumps((latest_raw.payload if latest_raw else {}), indent=2)},
    )


@login_required
def scans_reports(request):
    reports = Report.objects.select_related('scan_run__scan_job__project', 'scan_run__scan_job__target').order_by('-created_at')
    return render(request, 'targets/scans/reports.html', {'reports': reports})


@login_required
def scan_report_download(request, id: int, report_format: str):
    run = get_object_or_404(ScanRun, pk=id)
    report = run.reports.order_by('-created_at').first()
    if not report:
        raise Http404
    mapping = {'html': report.html_file, 'json': report.json_file, 'pdf': report.pdf_file}
    file_field = mapping.get(report_format)
    if not file_field:
        raise Http404
    return FileResponse(file_field.open('rb'), as_attachment=True, filename=file_field.name.split('/')[-1])
