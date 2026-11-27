from django import forms
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import Permission, User

from .models import StudyPeriod

DOCUMENT_PERMISSIONS = ['add_studydocument', 'change_studydocument', 'delete_studydocument']
ROLE_CHOICES = [('staff', 'Study staff'), ('admin', 'Administrator')]


class StudyPeriodForm(forms.ModelForm):
    class Meta:
        model = StudyPeriod
        fields = ['number', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }
        help_texts = {'number': '1 to 8. Each period lasts about 3 months.'}


class UserForm(forms.ModelForm):
    """Add or edit a study user. Everyone here is staff (they can open the study pages); an administrator
    can also manage users and the admin. "Manage documents" lets them upload, replace and delete in Resources.
    A new account gets its password by email (accounts.emails.invite), so there are no password boxes."""

    role = forms.ChoiceField(choices=ROLE_CHOICES, widget=forms.RadioSelect(attrs={'class': 'radio'}))
    manage_documents = forms.BooleanField(required=False, label='Can upload, replace and delete documents in Resources')

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        help_texts = {'username': 'Letters, digits and @ . + - _ only. People can log in with this or their email.'}

    def __init__(self, *args, acting_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.acting_user = acting_user
        for name in ('username', 'first_name', 'last_name', 'email'):
            self.fields[name].required = True
        user = self.instance
        if user.pk:
            self.initial['role'] = 'admin' if user.is_superuser else 'staff'
            self.initial['manage_documents'] = user.is_superuser or user.user_permissions.filter(
                codename__in=DOCUMENT_PERMISSIONS).count() == len(DOCUMENT_PERMISSIONS)
        else:
            self.initial.setdefault('role', 'staff')
            self.fields['email'].help_text = 'The activation link and a temporary password are sent here.'

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if '@' in username:
            raise forms.ValidationError('A username cannot contain @ (that is how an email login is recognised).')
        if User.objects.exclude(pk=self.instance.pk).filter(username__iexact=username).exists():
            raise forms.ValidationError('This username is already taken.')
        return username

    def clean_email(self):
        from accounts.forms import unique_email
        return unique_email(self.cleaned_data['email'], self.instance)

    def clean(self):
        data = super().clean()
        if self.instance.pk and self.instance == self.acting_user and data.get('role') != 'admin':
            raise forms.ValidationError('You cannot remove your own administrator role.')
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = True
        user.is_superuser = self.cleaned_data['role'] == 'admin'
        if not user.pk:
            user.is_active = False          # until the activation link is opened
            user.set_unusable_password()    # the invitation sets a temporary one
        user.save()
        permissions = Permission.objects.filter(content_type__app_label='resources', codename__in=DOCUMENT_PERMISSIONS)
        if self.cleaned_data['manage_documents']:
            user.user_permissions.add(*permissions)
        else:
            user.user_permissions.remove(*permissions)
        return user


class AdminSetPasswordForm(SetPasswordForm):
    """Set a new password for someone else (they should change it after logging in)."""
