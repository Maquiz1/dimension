import re
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import PhoneCode
from .sms import to_msisdn

SMTP = 'django.core.mail.backends.locmem.EmailBackend'


def link_and_password(message):
    link = re.search(r'https?://\S+/activate/\S+/', message.body).group(0)
    password = re.search(r'Temporary password: (\S+)', message.body).group(1)
    return link, password


class LoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('asha', 'Asha@Example.org', 'pass-1234-x', is_staff=True,
                                             first_name='Asha', last_name='M')

    def test_login_with_username_or_email(self):
        for login in ('asha', 'ASHA', 'asha@example.org'):
            response = self.client.post('/login/', {'username': login, 'password': 'pass-1234-x'})
            self.assertRedirects(response, '/', fetch_redirect_response=False, msg_prefix=login)
            self.client.logout()
        response = self.client.post('/login/', {'username': 'asha@example.org', 'password': 'wrong'})
        self.assertContains(response, 'correct username and password')

    def test_login_page_has_show_password_and_forgot_link(self):
        html = self.client.get('/login/').content.decode()
        self.assertIn('password.js', html)
        self.assertIn('href="/password/forgot/"', html)
        self.assertIn('Username or email', html)

    def test_deactivated_account_is_told_why(self):
        self.user.is_active = False
        self.user.save()
        self.user.profile.deactivated_at = timezone.now()
        self.user.profile.save()
        response = self.client.post('/login/', {'username': 'asha', 'password': 'pass-1234-x'})
        self.assertContains(response, 'has been deactivated')


@override_settings(EMAIL_BACKEND=SMTP)
class InvitationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('boss', 'boss@x.org', 'pass-1234-x', first_name='B', last_name='S')
        self.client.force_login(self.admin)

    def register(self, **extra):
        data = {'username': 'ra1', 'first_name': 'Neema', 'last_name': 'K', 'email': 'neema@x.org', 'role': 'staff'}
        data.update(extra)
        return self.client.post('/users/add/', data)

    def test_all_four_fields_are_required(self):
        response = self.register(first_name='', last_name='', email='')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['form'].errors), 3)
        self.assertFalse(User.objects.filter(username='ra1').exists())

    def test_email_must_be_unique(self):
        response = self.register(email='BOSS@x.org')
        self.assertContains(response, 'already uses this email')

    def test_invitation_activation_and_forced_password_change(self):
        self.register()
        user = User.objects.get(username='ra1')
        self.assertFalse(user.is_active)
        self.assertEqual(len(mail.outbox), 1)
        link, password = link_and_password(mail.outbox[0])
        self.client.logout()

        # Not activated yet: the right password is refused with an explanation.
        response = self.client.post('/login/', {'username': 'neema@x.org', 'password': password})
        self.assertContains(response, 'not activated yet')

        response = self.client.get(link)
        self.assertRedirects(response, '/login/', fetch_redirect_response=False)
        user.refresh_from_db()
        self.assertTrue(user.is_active and user.profile.activated_at)

        self.client.post('/login/', {'username': 'ra1', 'password': password})
        self.assertRedirects(self.client.get('/'), '/password/', fetch_redirect_response=False)
        self.assertRedirects(self.client.get('/submissions/'), '/password/', fetch_redirect_response=False)
        response = self.client.post('/password/', {'old_password': password, 'new_password1': 'Mine-pass-2026',
                                                   'new_password2': 'Mine-pass-2026'})
        self.assertRedirects(response, '/profile/', fetch_redirect_response=False)
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_deactivated_account_cannot_be_reactivated_by_old_link(self):
        self.register()
        user = User.objects.get(username='ra1')
        link, _ = link_and_password(mail.outbox[0])
        self.client.post(f'/users/{user.pk}/deactivate/')
        self.client.logout()
        self.assertEqual(self.client.get(link).status_code, 400)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_resend_invitation_replaces_the_old_link(self):
        self.register()
        user = User.objects.get(username='ra1')
        old_link, _ = link_and_password(mail.outbox[0])
        self.client.post(f'/users/{user.pk}/invite/')
        self.assertEqual(len(mail.outbox), 2)
        new_link, _ = link_and_password(mail.outbox[1])
        self.client.logout()
        self.assertEqual(self.client.get(old_link).status_code, 400)
        self.assertRedirects(self.client.get(new_link), '/login/', fetch_redirect_response=False)

    def test_deactivate_and_reactivate(self):
        staff = User.objects.create_user('st', 'st@x.org', 'pass-1234-x', is_staff=True)
        self.client.post(f'/users/{staff.pk}/deactivate/')
        staff.refresh_from_db()
        self.assertFalse(staff.is_active)
        self.assertContains(self.client.get('/users/'), 'Deactivated')
        self.client.post(f'/users/{staff.pk}/reactivate/')
        staff.refresh_from_db()
        self.assertTrue(staff.is_active)

    def test_cannot_deactivate_yourself(self):
        self.client.post(f'/users/{self.admin.pk}/deactivate/')
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_users_page_shows_last_login(self):
        self.client.logout()
        self.client.post('/login/', {'username': 'boss', 'password': 'pass-1234-x'})
        self.assertContains(self.client.get('/users/'), 'ago')

    def test_staff_cannot_change_status(self):
        staff = User.objects.create_user('st', 'st@x.org', 'pass-1234-x', is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.post(f'/users/{self.admin.pk}/deactivate/').status_code, 403)


@override_settings(EMAIL_BACKEND=SMTP)
class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('asha', 'asha@x.org', 'pass-1234-x', is_staff=True)

    def test_reset_by_username_or_email(self):
        for login in ('asha', 'asha@x.org'):
            response = self.client.post('/password/forgot/', {'email': login})
            self.assertRedirects(response, '/password/forgot/sent/', fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, ['asha@x.org'])
        link = re.search(r'https?://\S+/password/reset/\S+/', mail.outbox[0].body).group(0)
        response = self.client.get(link, follow=True)
        response = self.client.post(response.redirect_chain[-1][0], {'new_password1': 'Reset-pass-2026', 'new_password2': 'Reset-pass-2026'})
        self.assertRedirects(response, '/password/reset/done/', fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Reset-pass-2026'))

    def test_unknown_account_gets_same_page_and_no_email(self):
        response = self.client.post('/password/forgot/', {'email': 'nobody@x.org'})
        self.assertRedirects(response, '/password/forgot/sent/', fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 0)


class PhoneTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('asha', 'asha@x.org', 'pass-1234-x', is_staff=True)
        self.client.force_login(self.user)

    def test_numbers(self):
        self.assertEqual(to_msisdn('0712 345 678'), '255712345678')
        self.assertEqual(to_msisdn('+255 612 345 678'), '255612345678')
        self.assertIsNone(to_msisdn('0222 123 456'))

    def test_verify_with_code(self):
        with mock.patch('accounts.phone.send_sms') as send, mock.patch('accounts.phone.secrets.randbelow', return_value=123456):
            self.client.post('/profile/phone/send/', {'phone': '0712345678'})
        send.assert_called_once()
        self.assertIn('123456', send.call_args[0][1])
        response = self.client.post('/profile/phone/verify/', {'code': '000000'}, follow=True)
        self.assertContains(response, 'not right')
        response = self.client.post('/profile/phone/verify/', {'code': '123456'}, follow=True)
        self.assertContains(response, 'is verified')
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.phone_number, '255712345678')
        self.assertFalse(PhoneCode.objects.exists())

    def test_expired_code(self):
        with mock.patch('accounts.phone.send_sms'), mock.patch('accounts.phone.secrets.randbelow', return_value=111111):
            self.client.post('/profile/phone/send/', {'phone': '0712345678'})
        PhoneCode.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
        response = self.client.post('/profile/phone/verify/', {'code': '111111'}, follow=True)
        self.assertContains(response, 'expired')

    def test_profile_page_and_details(self):
        self.assertContains(self.client.get('/profile/'), 'Mobile number')
        response = self.client.post('/profile/', {'action': 'details', 'first_name': '', 'last_name': 'M', 'email': 'asha@x.org'})
        self.assertContains(response, 'This field is required')
        self.client.post('/profile/', {'action': 'details', 'first_name': 'Asha', 'last_name': 'M', 'email': 'asha@x.org'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Asha')
