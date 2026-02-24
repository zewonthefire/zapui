from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import ScanJob, ScanProfile
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
