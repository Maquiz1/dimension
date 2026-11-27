"""Accounts that existed before invitations count as activated; inactive ones as deactivated."""
from django.db import migrations
from django.utils import timezone


def add_profiles(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Profile = apps.get_model('accounts', 'Profile')
    now = timezone.now()
    for user in User.objects.filter(profile__isnull=True):
        Profile.objects.create(user=user, activated_at=user.date_joined,
                               deactivated_at=None if user.is_active else now)


class Migration(migrations.Migration):
    dependencies = [('accounts', '0001_initial')]
    operations = [migrations.RunPython(add_profiles, migrations.RunPython.noop)]
