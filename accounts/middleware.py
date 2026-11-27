from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

ALLOWED = ('password-change', 'logout')


class ForcePasswordChangeMiddleware:
    """After logging in with a temporary password, the only page open is "change your password"."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            profile = getattr(user, 'profile', None)
            if profile is not None and profile.must_change_password:
                allowed = {reverse(name) for name in ALLOWED}
                if request.path not in allowed and not request.path.startswith(('/static/', '/media/')):
                    if request.method == 'GET':
                        messages.info(request, 'Choose your own password to continue. The one you were given was temporary.')
                    return redirect('password-change')
        return self.get_response(request)
