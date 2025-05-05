from django.shortcuts import redirect
from django.urls import reverse

class SubscriptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.allowed_paths = [
            '/subscribe',
            '/logout',
            '/admin',
        ]

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            profile = getattr(user, 'profile', None)
            # Use is_subscribed if it exists, otherwise fall back to subscription_status
            is_subscribed = getattr(profile, 'is_subscribed', None)
            if is_subscribed is not None:
                subscribed = is_subscribed
            else:
                subscribed = getattr(profile, 'subscription_status', '') == 'active'
            if not subscribed:
                # Allow access to allowed paths
                if not any(request.path.startswith(path) for path in self.allowed_paths):
                    return redirect(reverse('subscribe'))
        return self.get_response(request) 