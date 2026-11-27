"""Sending SMS (phone verification). Set in .env with SMS_BACKEND:
  console        - write the message to the log only (default; nothing is sent)
  nextsms        - NextSMS (NEXTSMS_API_TOKEN, or NEXTSMS_USERNAME and NEXTSMS_PASSWORD; NEXTSMS_SENDER_ID)
  africastalking - Africa's Talking (AT_USERNAME, AT_API_KEY, AT_SENDER_ID)
SMS_TEST_MODE=1 uses the provider's test endpoint or sandbox: nothing is delivered.
"""
import logging
import re

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

NEXTSMS_URLS = {
    ('v2', False): 'https://messaging-service.co.tz/api/sms/v2/text/single',
    ('v2', True): 'https://messaging-service.co.tz/api/sms/v2/test/text/single',
    ('v1', False): 'https://messaging-service.co.tz/api/sms/v1/text/single',
    ('v1', True): 'https://messaging-service.co.tz/api/sms/v1/test/text/single',
}
NEXTSMS_FAILED = {'REJECTED', 'FAILED', 'UNDELIVERABLE', 'EXPIRED'}
AT_URLS = {False: 'https://api.africastalking.com/version1/messaging',
           True: 'https://api.sandbox.africastalking.com/version1/messaging'}
AT_ACCEPTED = {100, 101, 102}


class SmsError(Exception):
    pass


def to_msisdn(phone):
    """A Tanzanian mobile number as 255XXXXXXXXX, or None if it is not one."""
    digits = re.sub(r'\D', '', str(phone or ''))
    if digits.startswith('0') and len(digits) == 10:
        digits = '255' + digits[1:]
    elif len(digits) == 9:
        digits = '255' + digits
    return digits if re.fullmatch(r'255[67]\d{8}', digits) else None


def _post(provider, url, **kwargs):
    try:
        return requests.post(url, timeout=20, **kwargs)
    except requests.RequestException as error:
        raise SmsError(f'Could not reach {provider}: {error}')


def _nextsms(msisdn, text):
    headers = {'Accept': 'application/json'}
    if settings.NEXTSMS_API_TOKEN:
        version, auth = 'v2', None
        headers['Authorization'] = f'Bearer {settings.NEXTSMS_API_TOKEN}'
    elif settings.NEXTSMS_USERNAME and settings.NEXTSMS_PASSWORD:
        version, auth = 'v1', (settings.NEXTSMS_USERNAME, settings.NEXTSMS_PASSWORD)
    else:
        raise SmsError('NextSMS is not configured.')
    response = _post('NextSMS', NEXTSMS_URLS[(version, settings.SMS_TEST_MODE)], auth=auth, headers=headers,
                     json={'from': settings.NEXTSMS_SENDER_ID, 'to': msisdn, 'text': text})
    if response.status_code >= 400:
        raise SmsError(f'NextSMS HTTP {response.status_code}: {response.text[:200]}')
    try:
        status = ((response.json().get('messages') or [{}])[0]).get('status') or {}
    except ValueError:
        raise SmsError('NextSMS returned an unexpected reply.')
    if status.get('groupName') in NEXTSMS_FAILED:
        raise SmsError(f"NextSMS: {status.get('description') or status.get('groupName')}")


def _africastalking(msisdn, text):
    username = 'sandbox' if settings.SMS_TEST_MODE else settings.AT_USERNAME
    if not (username and settings.AT_API_KEY):
        raise SmsError("Africa's Talking is not configured.")
    data = {'username': username, 'to': f'+{msisdn}', 'message': text}
    if settings.AT_SENDER_ID:
        data['from'] = settings.AT_SENDER_ID
    response = _post("Africa's Talking", AT_URLS[settings.SMS_TEST_MODE], data=data,
                     headers={'apiKey': settings.AT_API_KEY, 'Accept': 'application/json'})
    if response.status_code >= 400:
        raise SmsError(f"Africa's Talking HTTP {response.status_code}")
    try:
        recipients = (response.json().get('SMSMessageData') or {}).get('Recipients') or []
    except ValueError:
        raise SmsError("Africa's Talking returned an unexpected reply.")
    if not recipients or recipients[0].get('statusCode') not in AT_ACCEPTED:
        raise SmsError(f"Africa's Talking did not accept the message ({recipients[0].get('status') if recipients else 'no recipient'}).")


def send_sms(msisdn, text):
    """Send one SMS. Raises SmsError if the provider refused it."""
    backend = settings.SMS_BACKEND
    if backend == 'nextsms':
        _nextsms(msisdn, text)
    elif backend == 'africastalking':
        _africastalking(msisdn, text)
    else:
        logger.warning('SMS (console, not sent) to %s: %s', msisdn, text)


def sms_configured():
    return settings.SMS_BACKEND in ('nextsms', 'africastalking')
