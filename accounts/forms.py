from django import forms
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User

from .backends import find_user


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.fields:
            self.fields[name].required = True

    def clean_email(self):
        return unique_email(self.cleaned_data['email'], self.instance)


def unique_email(email, instance):
    email = email.strip()
    if User.objects.exclude(pk=instance.pk).filter(email__iexact=email).exists():
        raise forms.ValidationError('Another account already uses this email address.')
    return email


class PhoneForm(forms.Form):
    phone = forms.CharField(label='Mobile number', max_length=20,
                            widget=forms.TextInput(attrs={'inputmode': 'tel', 'autocomplete': 'tel', 'placeholder': '0712 345 678'}))


class CodeForm(forms.Form):
    code = forms.CharField(label='Code from the SMS', max_length=6, min_length=6,
                           widget=forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'one-time-code', 'placeholder': '6 digits'}))


class StudyPasswordResetForm(PasswordResetForm):
    """Accepts the username or the email address, so people who forget which one they use still get the link."""
    email = forms.CharField(label='Username or email address', max_length=254,
                            widget=forms.TextInput(attrs={'autocomplete': 'username', 'autofocus': True}))

    def get_users(self, email):
        user = find_user(email)
        if user and user.is_active and user.is_staff and user.has_usable_password() and user.email:
            yield user
