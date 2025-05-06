import requests
from django.conf import settings
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import UserProfile
import base64
import hashlib
import os

def generate_pkce_pair():
    code_verifier = base64.urlsafe_b64encode(os.urandom(40)).rstrip(b'=').decode('utf-8')
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).rstrip(b'=').decode('utf-8')
    return code_verifier, code_challenge

@login_required
def salesforce_connect(request):
    code_verifier, code_challenge = generate_pkce_pair()
    request.session['sf_code_verifier'] = code_verifier
    auth_url = (
        f"{settings.SALESFORCE_AUTH_URL}"
        f"?response_type=code"
        f"&client_id={settings.SALESFORCE_CLIENT_ID}"
        f"&redirect_uri={settings.SALESFORCE_REDIRECT_URI}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
    )
    return redirect(auth_url)

@login_required
def salesforce_callback(request):
    code = request.GET.get('code')
    if not code:
        return JsonResponse({'error': 'Missing authorization code'}, status=400)
    code_verifier = request.session.get('sf_code_verifier')
    if not code_verifier:
        return JsonResponse({'error': 'Missing PKCE code_verifier in session'}, status=400)
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'client_id': settings.SALESFORCE_CLIENT_ID,
        'client_secret': settings.SALESFORCE_CLIENT_SECRET,
        'redirect_uri': settings.SALESFORCE_REDIRECT_URI,
        'code_verifier': code_verifier,
    }
    response = requests.post(settings.SALESFORCE_TOKEN_URL, data=data)
    if response.status_code != 200:
        return JsonResponse({'error': 'Failed to get access token', 'details': response.text}, status=400)
    token_data = response.json()
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.salesforce_access_token = token_data['access_token']
    profile.salesforce_refresh_token = token_data.get('refresh_token')
    profile.salesforce_instance_url = token_data['instance_url']
    profile.save()
    return redirect('leads:integrations')

@login_required
def salesforce_disconnect(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.salesforce_access_token = None
    profile.salesforce_refresh_token = None
    profile.salesforce_instance_url = None
    profile.save()
    return redirect('leads:integrations') 