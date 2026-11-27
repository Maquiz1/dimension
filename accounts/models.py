"""Account state the built-in User does not hold: invitation, forced password change and phone.

An account is in one of three states:
- invitation pending: not active, never activated, not deactivated (the person has not used the link yet);
- active;
- deactivated by an administrator (an old activation link can then no longer switch it back on).
"""
from django.conf import settings
from django.db import models


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=20, blank=True, help_text='255XXXXXXXXX')
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    must_change_password = models.BooleanField(default=False)
    invited_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'Profile of {self.user}'

    @property
    def status(self):
        if self.user.is_active:
            return 'active'
        if self.deactivated_at or self.activated_at:
            return 'deactivated'
        return 'pending'

    @property
    def phone_display(self):
        n = self.phone_number
        return f'+{n[:3]} {n[3:6]} {n[6:9]} {n[9:]}' if len(n) == 12 else n


class PhoneCode(models.Model):
    """The current SMS verification code for a user, stored hashed so every web worker sees it."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='phone_code')
    phone = models.CharField(max_length=20)
    code_hash = models.CharField(max_length=128)
    tries = models.PositiveSmallIntegerField(default=0)
    sent_at = models.DateTimeField()
    expires_at = models.DateTimeField()
