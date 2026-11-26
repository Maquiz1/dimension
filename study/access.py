"""Login and access for the study pages (the dashboard and Resources).

The study pages are for staff accounts only. They use the study's own login page rather than the
Django admin's, so signing in always lands on the dashboard (or the page that was asked for).
"""
from functools import wraps

from django import forms
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def staff_required(view):
    """Send people who are not logged in to the study login page; refuse logged-in non-staff."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not (request.user.is_active and request.user.is_staff):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


class StaffAuthenticationForm(AuthenticationForm):
    """Only staff accounts can sign in here, as in the admin."""

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise forms.ValidationError(
                'This account does not have access to the study system. Ask the data manager.',
                code='no_access',
            )


class StudyLoginView(auth_views.LoginView):
    template_name = 'dimension/login.html'
    authentication_form = StaffAuthenticationForm
    redirect_authenticated_user = True
