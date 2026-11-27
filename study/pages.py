"""Clinics, study periods and users, inside the study system rather than the Django admin."""
from datetime import date
from functools import wraps

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from capture.ingest import refresh_periods

from . import design
from .access import staff_required
from .forms import AdminSetPasswordForm, StudyPeriodForm, UserForm
from .models import Facility, StudyPeriod


def administrator_required(view):
    @wraps(view)
    @staff_required
    def wrapped(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


# ── Clinics (read only: they come from the data dictionary, and the allocation is fixed once loaded) ──

@staff_required
def clinics(request):
    qs = Facility.objects.annotate(submissions=Count('formsubmission')).order_by('region', 'code')
    region, kind, q = request.GET.get('region', ''), request.GET.get('type', ''), request.GET.get('q', '').strip()
    if region:
        qs = qs.filter(region=region)
    if kind:
        qs = qs.filter(facility_type=kind)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q) | Q(district__icontains=q) | Q(ward__icontains=q))
    rows = [{'f': f, 'start': design.first_intervention_period(f.sequence) if f.sequence else None} for f in qs]
    return render(request, 'study/clinics.html', {
        'rows': rows, 'region': region, 'kind': kind, 'q': q,
        'regions': Facility.objects.order_by('region').values_list('region', flat=True).distinct(),
        'kinds': Facility.objects.order_by('facility_type').values_list('facility_type', flat=True).distinct(),
        'total': Facility.objects.count(),
    })


# ── Study periods ──

@staff_required
def periods(request):
    defined = {p.number: p for p in StudyPeriod.objects.all()}
    current = StudyPeriod.number_for(date.today())
    rows = []
    for n in design.PERIODS:
        rows.append({
            'number': n, 'period': defined.get(n), 'current': n == current,
            'intervention': [s for s in design.SEQUENCES if design.exposure(s, n) == design.INTERVENTION],
        })
    return render(request, 'study/periods.html', {
        'rows': rows, 'defined': len(defined), 'can_edit': request.user.has_perm('study.change_studyperiod'),
    })


@staff_required
def period_edit(request, number=None):
    period = get_object_or_404(StudyPeriod, number=number) if number else None
    if not request.user.has_perm('study.change_studyperiod' if period else 'study.add_studyperiod'):
        raise PermissionDenied
    initial = {'number': request.GET.get('number')} if not period else None
    form = StudyPeriodForm(request.POST or None, instance=period, initial=initial)
    if period:
        form.fields['number'].disabled = True
    if request.method == 'POST' and form.is_valid():
        form.save()
        changed = refresh_periods()
        messages.success(request, f'Period {form.instance.number} saved. {changed} record{"s" if changed != 1 else ""} '
                                  'had their period or control/intervention status updated.')
        return redirect('periods')
    return render(request, 'study/period_form.html', {'form': form, 'period': period})


# ── Users (administrators only) ──

@administrator_required
def users(request):
    people = User.objects.order_by('-is_active', 'username').prefetch_related('user_permissions')
    rows = [{'u': u, 'documents': u.is_superuser or u.has_perm('resources.add_studydocument')} for u in people]
    return render(request, 'study/users.html', {'rows': rows})


@administrator_required
def user_edit(request, pk=None):
    person = get_object_or_404(User, pk=pk) if pk else None
    form = UserForm(request.POST or None, instance=person, acting_user=request.user)
    if request.method == 'POST' and form.is_valid():
        saved = form.save()
        messages.success(request, f'{"Saved" if person else "Created"} the account “{saved.username}”.')
        return redirect('users')
    return render(request, 'study/user_form.html', {'form': form, 'person': person})


@administrator_required
def user_password(request, pk):
    person = get_object_or_404(User, pk=pk)
    form = AdminSetPasswordForm(person, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        if person == request.user:
            update_session_auth_hash(request, person)   # stay logged in after changing your own password
        messages.success(request, f'New password set for “{person.username}”. Ask them to change it after logging in.')
        return redirect('users')
    return render(request, 'study/user_password.html', {'form': form, 'person': person})


@staff_required
def password_change(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        update_session_auth_hash(request, form.save())   # stay logged in with the new password
        messages.success(request, 'Your password was changed.')
        return redirect('dashboard')
    return render(request, 'study/password_change.html', {'form': form})
