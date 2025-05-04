import os
import requests
from django.conf import settings
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from .models import UserProfile
from django.contrib import messages

@login_required
def pipedrive_connect(request):
    client_id = settings.PIPEDRIVE_CLIENT_ID
    redirect_uri = settings.PIPEDRIVE_REDIRECT_URI
    oauth_url = (
        f"https://oauth.pipedrive.com/oauth/authorize?"
        f"client_id={client_id}&redirect_uri={redirect_uri}&response_type=code"
    )
    return redirect(oauth_url)

@login_required
def pipedrive_callback(request):
    code = request.GET.get('code')
    if not code:
        return JsonResponse({'error': 'Missing authorization code'}, status=400)

    token_url = 'https://oauth.pipedrive.com/oauth/token'
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': settings.PIPEDRIVE_REDIRECT_URI,
        'client_id': settings.PIPEDRIVE_CLIENT_ID,
        'client_secret': settings.PIPEDRIVE_CLIENT_SECRET,
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post(token_url, data=data, headers=headers)

    if response.status_code == 200:
        tokens = response.json()
        access_token = tokens.get('access_token')
        refresh_token = tokens.get('refresh_token')
        expires_in = tokens.get('expires_in')  # seconds
        expires_at = timezone.now() + timezone.timedelta(seconds=expires_in) if expires_in else None

        # Get or create user profile
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.pipedrive_access_token = access_token
        profile.pipedrive_refresh_token = refresh_token
        profile.pipedrive_token_expires_at = expires_at
        profile.save()

        messages.success(request, 'Successfully connected to Pipedrive!')
        return redirect('leads:integrations')
    else:
        return JsonResponse({'error': 'Failed to get access token', 'details': response.text}, status=400)

@login_required
def pipedrive_disconnect(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.pipedrive_access_token = None
    profile.save()
    return redirect('leads:integrations') 