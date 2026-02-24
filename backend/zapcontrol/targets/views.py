import json
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import OuterRef, Subquery
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from .models import Finding, FindingInstance, Report, RiskSnapshot, ScanComparison, ScanJob, ScanProfile, Target, Project
from .reports import generate_scan_report
from .tasks import start_scan_job


class ScanProfileForm(forms.ModelForm):
    class Meta:
        model = ScanProfile
        fields = [
            'name',
            'description',
            'project',
            'zap_node',
            'scan_type',
            'spider_enabled',
            'max_duration_minutes',
            'extra_zap_options',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'extra_zap_options': forms.Textarea(attrs={'rows': 3}),
        }


class ScanJobForm(forms.ModelForm):
    class Meta:
        model = ScanJob
        fields = ['project', 'target', 'profile']


@login_required
def profiles(request):
    if request.method == 'POST':
        profile_id = request.POST.get('profile_id')
        if 'delete' in request.POST and profile_id:
            profile = get_object_or_404(ScanProfile, pk=profile_id)
            profile.delete()
            messages.success(request, 'Profile deleted.')
            return redirect('profiles')

        instance = get_object_or_404(ScanProfile, pk=profile_id) if profile_id else None
        form = ScanProfileForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile saved.')
            return redirect('profiles')
        profiles_qs = ScanProfile.objects.select_related('project', 'zap_node').all()
        return render(request, 'targets/profiles.html', {'form': form, 'profiles': profiles_qs})

    edit_profile = None
    if request.GET.get('edit'):
        edit_profile = get_object_or_404(ScanProfile, pk=request.GET['edit'])
    form = ScanProfileForm(instance=edit_profile)
    profiles_qs = ScanProfile.objects.select_related('project', 'zap_node').all()
    return render(request, 'targets/profiles.html', {'form': form, 'profiles': profiles_qs})


@login_required
def scans(request):
    if request.method == 'POST':
        form = ScanJobForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.initiated_by = request.user
            job.save()
            start_scan_job.delay(job.id)
            messages.success(request, f'Scan job #{job.id} queued.')
            return redirect('scan-detail', scan_id=job.id)
    else:
        form = ScanJobForm()

    jobs = ScanJob.objects.select_related('project', 'target', 'profile', 'zap_node', 'initiated_by').all()
    return render(request, 'targets/scans.html', {'form': form, 'jobs': jobs})


@login_required
def scan_detail(request, scan_id: int):
    job = get_object_or_404(
        ScanJob.objects.select_related('project', 'target', 'profile', 'zap_node', 'initiated_by').prefetch_related('raw_results'),
        pk=scan_id,
    )
    latest_raw = job.raw_results.first()
    return render(request, 'targets/scan_detail.html', {'job': job, 'latest_raw': latest_raw})


@login_required
def project_detail(request, project_id: int):
    project = get_object_or_404(Project, pk=project_id)
    latest_project_risk = project.risk_snapshots.filter(target__isnull=True).first()
    latest_target_snapshot = RiskSnapshot.objects.filter(target=OuterRef('pk'), project__isnull=True).order_by('-created_at')
    top_targets = (
        Target.objects.filter(project=project)
        .annotate(latest_risk=Subquery(latest_target_snapshot.values('risk_score')[:1]))
        .order_by('-latest_risk', 'name')[:10]
    )
    return render(
        request,
        'targets/project_detail.html',
        {'project': project, 'latest_project_risk': latest_project_risk, 'top_targets': top_targets},
    )


@login_required
def target_evolution(request, target_id: int):
    target = get_object_or_404(Target.objects.select_related('project'), pk=target_id)
    comparisons = ScanComparison.objects.filter(target=target).select_related('from_scan_job', 'to_scan_job').order_by('-created_at')
    target_snapshots = target.risk_snapshots.filter(project__isnull=True).select_related('scan_job').order_by('created_at')

    timeline_points = [
        {
            'label': snapshot.created_at.strftime('%Y-%m-%d %H:%M'),
            'score': float(snapshot.risk_score),
            'scan_id': snapshot.scan_job_id,
        }
        for snapshot in target_snapshots
    ]

    return render(
        request,
        'targets/target_evolution.html',
        {
            'target': target,
            'comparisons': comparisons,
            'timeline_points_json': json.dumps(timeline_points),
        },
    )


@login_required
def target_diff_detail(request, target_id: int, comparison_id: int):
    target = get_object_or_404(Target.objects.select_related('project'), pk=target_id)
    comparison = get_object_or_404(
        ScanComparison.objects.select_related('from_scan_job', 'to_scan_job').filter(target=target),
        pk=comparison_id,
    )

    from_ids = set(FindingInstance.objects.filter(scan_job=comparison.from_scan_job).values_list('finding_id', flat=True).distinct())
    to_ids = set(FindingInstance.objects.filter(scan_job=comparison.to_scan_job).values_list('finding_id', flat=True).distinct())

    new_findings = Finding.objects.filter(id__in=comparison.new_finding_ids).order_by('-severity', 'title')
    resolved_findings = Finding.objects.filter(id__in=comparison.resolved_finding_ids).order_by('-severity', 'title')

    stale_new_ids = sorted(set(comparison.new_finding_ids) - to_ids)
    stale_resolved_ids = sorted(set(comparison.resolved_finding_ids) - from_ids)
    if stale_new_ids or stale_resolved_ids:
        raise Http404('Comparison details are out of sync with scan data.')

    return render(
        request,
        'targets/target_diff_detail.html',
        {
            'target': target,
            'comparison': comparison,
            'new_findings': new_findings,
            'resolved_findings': resolved_findings,
        },
    )


@login_required
def target_detail(request, target_id: int):
    target = get_object_or_404(Target.objects.select_related('project'), pk=target_id)
    latest_target_risk = target.risk_snapshots.filter(project__isnull=True).first()
    open_findings = Finding.objects.filter(target=target).order_by('-severity', '-last_seen')
    return render(
        request,
        'targets/target_detail.html',
        {'target': target, 'latest_target_risk': latest_target_risk, 'open_findings': open_findings},
    )


@login_required
def report_download(request, scan_id: int, report_format: str):
    job = get_object_or_404(ScanJob.objects.select_related('project', 'target', 'profile'), pk=scan_id)
    if job.status != ScanJob.STATUS_COMPLETED:
        raise Http404('Reports are only available for completed scans.')

    report = Report.objects.filter(scan_job=job).first()
    if not report or not report.html_file or not report.json_file or not report.pdf_file:
        report = generate_scan_report(job)

    mapping = {
        'html': (report.html_file, 'text/html'),
        'json': (report.json_file, 'application/json'),
        'pdf': (report.pdf_file, 'application/pdf'),
    }
    if report_format not in mapping:
        raise Http404('Unsupported report format.')

    file_field, content_type = mapping[report_format]
    return FileResponse(file_field.open('rb'), content_type=content_type, as_attachment=True, filename=file_field.name.split('/')[-1])


@login_required
def reports_list(request):
    reports = Report.objects.select_related('scan_job__project', 'scan_job__target').all()
    return render(request, 'targets/reports.html', {'reports': reports})
