from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from functools import wraps


def login_required_and_subscribed(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        profile = getattr(request.user, 'profile', None)
        is_subscribed = getattr(profile, 'is_subscribed', None)
        if is_subscribed is not None:
            subscribed = is_subscribed
        else:
            subscribed = getattr(profile, 'subscription_status', '') != 'inactive'
        if not subscribed:
            return redirect('leads:pricing')
        return view_func(request, *args, **kwargs)
    return _wrapped_view 