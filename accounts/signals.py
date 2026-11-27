from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, raw=False, **kwargs):
    """Every account has a profile. One made outside the invitation flow (createsuperuser) counts as activated."""
    if created and not raw:
        Profile.objects.get_or_create(user=instance, defaults={
            'activated_at': timezone.now() if instance.is_active else None})


def profile_for(user):
    profile, _ = Profile.objects.get_or_create(
        user=user, defaults={'activated_at': timezone.now() if user.is_active else None})
    return profile
