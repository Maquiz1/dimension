"""Phone verification: the system texts a 6-digit code, the person types it on their profile."""
import logging
import secrets
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone

from .models import PhoneCode, Profile
from .signals import profile_for
from .sms import SmsError, send_sms, to_msisdn

logger = logging.getLogger(__name__)
CODE_MINUTES = 10
MAX_TRIES = 5
RESEND_SECONDS = 60


def send_code(user, phone):
    """Text a new code. Returns (ok, message)."""
    msisdn = to_msisdn(phone)
    if not msisdn:
        return False, 'Enter a valid Tanzanian mobile number, for example 0712 345 678.'
    if Profile.objects.filter(phone_number=msisdn, phone_verified_at__isnull=False).exclude(user=user).exists():
        return False, "This number is already verified on another person's account."
    now = timezone.now()
    last = PhoneCode.objects.filter(user=user).first()
    if last and (now - last.sent_at).total_seconds() < RESEND_SECONDS:
        return False, 'A code was just sent. Wait a minute before asking for another.'
    code = f'{secrets.randbelow(10 ** 6):06d}'
    PhoneCode.objects.update_or_create(user=user, defaults={
        'phone': msisdn, 'code_hash': make_password(code), 'tries': 0,
        'sent_at': now, 'expires_at': now + timedelta(minutes=CODE_MINUTES)})
    try:
        send_sms(msisdn, f'DIMENSION: your verification code is {code}. It expires in {CODE_MINUTES} minutes. '
                         'Do not share it.')
    except SmsError as error:
        logger.error('Phone verification SMS failed for %s: %s', user.username, error)
        PhoneCode.objects.filter(user=user).delete()
        return False, 'The SMS could not be sent. Check the number, or try again later.'
    return True, f'A code was sent to {phone}. Enter it below within {CODE_MINUTES} minutes.'


def pending_phone(user):
    code = PhoneCode.objects.filter(user=user, expires_at__gt=timezone.now()).first()
    return code.phone if code else None


def check_code(user, typed):
    """Check the typed code. Returns (ok, message); on success the number is saved as verified."""
    code = PhoneCode.objects.filter(user=user).first()
    if not code or code.expires_at <= timezone.now():
        return False, 'The code has expired. Ask for a new one.'
    if code.tries >= MAX_TRIES:
        code.delete()
        return False, 'Too many wrong codes. Ask for a new one.'
    if not check_password((typed or '').strip(), code.code_hash):
        code.tries += 1
        code.save(update_fields=['tries'])
        left = MAX_TRIES - code.tries
        return False, f"That code is not right. {left} tr{'y' if left == 1 else 'ies'} left."
    phone = code.phone
    code.delete()
    profile = profile_for(user)
    profile.phone_number, profile.phone_verified_at = phone, timezone.now()
    profile.save(update_fields=['phone_number', 'phone_verified_at'])
    return True, 'Your phone number is verified.'
