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
    """Only staff accounts can sign in here, as in the admin. The username box also takes the email address."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Username or email'
        self.fields['username'].max_length = 254
        self.fields['username'].widget.attrs['maxlength'] = 254

    def clean(self):
        try:
            return super().clean()
        except forms.ValidationError as error:
            if error.code == 'invalid_login':
                self._explain_inactive()
            raise

    def _explain_inactive(self):
        """Say why the right password is refused, rather than "wrong password", for accounts that cannot log in yet."""
        from accounts.backends import find_user
        from accounts.signals import profile_for

        user = find_user(self.cleaned_data.get('username'))
        if user and not user.is_active and user.check_password(self.cleaned_data.get('password') or ''):
            if profile_for(user).status == 'pending':
                raise forms.ValidationError('Your account is not activated yet. Open the activation link in the '
                                            'invitation email first, or ask an administrator to send a new one.',
                                            code='not_activated')
            raise forms.ValidationError('This account has been deactivated. Ask an administrator.', code='inactive')

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
