from .summary import alert_counts


def navigation(request):
    """Counts for the navbar bell, on every page a staff member sees."""
    user = getattr(request, 'user', None)
    if not (user and user.is_authenticated and user.is_staff):
        return {}
    counts = alert_counts()
    return {'nav_alerts': counts, 'nav_alert_total': counts['item9_alerts'] + counts['review_count']}
