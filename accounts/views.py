from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import views as auth_views
from django.contrib.auth.tokens import default_token_generator
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.http import require_POST

from study.access import staff_required

from . import phone
from .forms import CodeForm, PhoneForm, ProfileForm, StudyPasswordResetForm
from .signals import profile_for
from .sms import sms_configured


def activate(request, uidb64, token):
    """The link in the invitation email. Works once, and never on an account an administrator deactivated."""
    try:
        user = get_user_model()._default_manager.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (TypeError, ValueError, OverflowError, get_user_model().DoesNotExist):
        user = None
    profile = profile_for(user) if user else None
    if profile and profile.status == 'active':
        messages.info(request, 'Your account is already active. Log in below.')
        return redirect('login')
    if profile and profile.status == 'pending' and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save(update_fields=['is_active'])
        profile.activated_at = timezone.now()
        profile.save(update_fields=['activated_at'])
        messages.success(request, 'Your account is active. Log in with the temporary password from the email; '
                                  'you will then choose your own password.')
        return redirect('login')
    return render(request, 'accounts/activation_invalid.html', status=400)


class PasswordResetView(auth_views.PasswordResetView):
    form_class = StudyPasswordResetForm
    template_name = 'accounts/password_reset_form.html'
    email_template_name = 'accounts/email/password_reset.txt'
    html_email_template_name = 'accounts/email/password_reset.html'
    subject_template_name = 'accounts/email/password_reset_subject.txt'
    success_url = reverse_lazy('password-reset-done')


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = 'accounts/password_reset_done.html'


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    success_url = reverse_lazy('password-reset-complete')

    def form_valid(self, form):
        response = super().form_valid(form)
        profile = profile_for(form.user)
        if profile.must_change_password:
            profile.must_change_password = False
            profile.save(update_fields=['must_change_password'])
        return response


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = 'accounts/password_reset_complete.html'


@staff_required
def profile(request):
    user, prof = request.user, profile_for(request.user)
    form = ProfileForm(request.POST if request.POST.get('action') == 'details' else None, instance=user)
    if form.is_bound and form.is_valid():
        form.save()
        messages.success(request, 'Your details were saved.')
        return redirect('profile')
    return render(request, 'accounts/profile.html', {
        'form': form, 'profile': prof, 'phone_form': PhoneForm(initial={'phone': prof.phone_number and '0' + prof.phone_number[3:]}),
        'code_form': CodeForm(), 'pending': phone.pending_phone(user), 'sms_ready': sms_configured(),
    })


@require_POST
@staff_required
def phone_send(request):
    form = PhoneForm(request.POST)
    if form.is_valid():
        ok, message = phone.send_code(request.user, form.cleaned_data['phone'])
        (messages.success if ok else messages.error)(request, message)
    else:
        messages.error(request, 'Enter your mobile number.')
    return redirect('profile')


@require_POST
@staff_required
def phone_verify(request):
    ok, message = phone.check_code(request.user, request.POST.get('code'))
    (messages.success if ok else messages.error)(request, message)
    return redirect('profile')
