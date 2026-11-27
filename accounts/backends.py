from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


def find_user(login):
    """The account a login name refers to: an email address when it contains @, otherwise a username.
    Both ignore case. Returns None when nothing (or more than one account) matches."""
    login = (login or '').strip()
    if not login:
        return None
    field = 'email__iexact' if '@' in login else 'username__iexact'
    matches = list(get_user_model()._default_manager.filter(**{field: login})[:2])
    return matches[0] if len(matches) == 1 else None


class EmailOrUsernameBackend(ModelBackend):
    """Log in with either the username or the email address."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(get_user_model().USERNAME_FIELD)
        if username is None or password is None:
            return None
        user = find_user(username)
        if user is None:
            get_user_model()().set_password(password)   # same time cost as a real check
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
