import requests
from django.conf import settings
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import UserProfile

@login_required
def salesforce_connect(request):
    auth_url = (
        f"{settings.SALESFORCE_AUTH_URL}"
        f"?response_type=code"
        f"&client_id={settings.SALESFORCE_CLIENT_ID}"
        f"&redirect_uri={settings.SALESFORCE_REDIRECT_URI}"
    )
    return redirect(auth_url)

@login_required
def salesforce_callback(request):
    code = request.GET.get('code')
    if not code:
        return JsonResponse({'error': 'Missing authorization code'}, status=400)

    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'client_id': settings.SALESFORCE_CLIENT_ID,
        'client_secret': settings.SALESFORCE_CLIENT_SECRET,
        'redirect_uri': settings.SALESFORCE_REDIRECT_URI,
    }

    response = requests.post(settings.SALESFORCE_TOKEN_URL, data=data)
    if response.status_code != 200:
        return JsonResponse({'error': 'Failed to get access token'}, status=400)

    token_data = response.json()
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.salesforce_access_token = token_data['access_token']
    profile.salesforce_refresh_token = token_data.get('refresh_token')
    profile.salesforce_instance_url = token_data['instance_url']
    profile.save()

    return redirect('leads:integrations') 