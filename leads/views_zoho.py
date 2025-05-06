import requests
from django.conf import settings
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import UserProfile
from django.utils import timezone

@login_required
def zoho_connect(request):
    auth_url = (
        f"https://accounts.zoho.com/oauth/v2/auth"
        f"?scope=ZohoCRM.modules.ALL,ZohoCRM.settings.ALL"
        f"&client_id={settings.ZOHO_CLIENT_ID}"
        f"&response_type=code"
        f"&access_type=offline"
        f"&redirect_uri={settings.ZOHO_REDIRECT_URI}"
        f"&prompt=consent"
    )
    return redirect(auth_url)

@login_required
def zoho_callback(request):
    code = request.GET.get('code')
    if not code:
        return JsonResponse({'error': 'Missing authorization code'}, status=400)
    data = {
        'client_id': settings.ZOHO_CLIENT_ID,
        'client_secret': settings.ZOHO_CLIENT_SECRET,
        'redirect_uri': settings.ZOHO_REDIRECT_URI,
        'grant_type': 'authorization_code',
        'code': code,
    }
    response = requests.post('https://accounts.zoho.com/oauth/v2/token', data=data)
    if response.status_code != 200:
        return JsonResponse({'error': 'Failed to get access token', 'details': response.text}, status=400)
    token_data = response.json()
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.zoho_access_token = token_data['access_token']
    profile.zoho_refresh_token = token_data.get('refresh_token')
    expires_in = token_data.get('expires_in')
    if expires_in:
        profile.zoho_token_expires_at = timezone.now() + timezone.timedelta(seconds=int(expires_in))
    profile.save()
    return redirect('leads:integrations')

@login_required
def zoho_disconnect(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.zoho_access_token = None
    profile.zoho_refresh_token = None
    profile.zoho_token_expires_at = None
    profile.save()
    return redirect('leads:integrations') 