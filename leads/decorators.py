from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from functools import wraps
from django.http import JsonResponse
from django.contrib import messages


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

def check_subscription_limits(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        user = getattr(request, 'user', None)

        if user and hasattr(user, 'is_authenticated') and user.is_authenticated:
            profile = getattr(user, 'profile', None)
            if profile and profile.lead_filter_quota > 0 and profile.lead_filter_count >= profile.lead_filter_quota:
                if request.path.startswith('/facebook/webhook'):
                    return JsonResponse({
                        'error': 'Lead quota exceeded',
                        'message': 'You have reached your monthly lead limit. Please upgrade your plan to continue.'
                    }, status=403)
                messages.warning(request, 'You have reached your monthly lead limit. Please upgrade your plan to continue.')
                return redirect('leads:pricing')
        return view_func(request, *args, **kwargs)
    return _wrapped_view 