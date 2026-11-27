"""Invitation (activation) emails."""
import secrets
import string

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .signals import profile_for

ALPHABET = string.ascii_letters + string.digits


def temporary_password():
    """12 characters without look-alikes (0/O, 1/l/I), always with a digit."""
    letters = [c for c in ALPHABET if c not in '0O1lI']
    while True:
        password = ''.join(secrets.choice(letters) for _ in range(12))
        if any(c.isdigit() for c in password) and any(c.isalpha() for c in password):
            return password


def email_configured():
    return not settings.EMAIL_BACKEND.endswith(('console.EmailBackend', 'locmem.EmailBackend', 'dummy.EmailBackend'))


def invite(request, user):
    """Give the account a new temporary password, mark it pending, and email the activation link.
    Returns (sent, password, link): the caller shows the password and link only when email is not set up."""
    password = temporary_password()
    user.set_password(password)          # also makes any earlier activation link stop working
    user.is_active = False
    user.save(update_fields=['password', 'is_active'])
    profile = profile_for(user)
    profile.must_change_password = True
    profile.invited_at = timezone.now()
    profile.activated_at = profile.deactivated_at = None
    profile.save(update_fields=['must_change_password', 'invited_at', 'activated_at', 'deactivated_at'])

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    link = request.build_absolute_uri(reverse('activate', args=[uid, default_token_generator.make_token(user)]))
    context = {'user': user, 'password': password, 'link': link, 'login_url': request.build_absolute_uri(reverse('login')),
               'days': settings.PASSWORD_RESET_TIMEOUT // 86400, 'invited_by': request.user}
    send_mail(
        'Your DIMENSION Study account',
        render_to_string('accounts/email/invitation.txt', context),
        None, [user.email],
        html_message=render_to_string('accounts/email/invitation.html', context),
    )
    return email_configured(), password, link
