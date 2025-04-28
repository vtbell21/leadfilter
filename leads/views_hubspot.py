import requests
from django.conf import settings
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import UserProfile

def create_hubspot_contact(user, lead):
    url = "https://api.hubapi.com/crm/v3/objects/contacts"
    headers = {
        'Authorization': f'Bearer {user.profile.hubspot_access_token}',
        'Content-Type': 'application/json'
    }
    data = {
        "properties": {
            "email": lead.email,
            "firstname": lead.first_name,
            "lastname": lead.last_name,
            "phone": lead.phone,
        }
    }
    response = requests.post(url, headers=headers, json=data)
    return response.status_code == 201

@login_required
def hubspot_connect(request):
    scopes = [
        "crm.objects.contacts.read",
        "crm.objects.contacts.write",
        "oauth",
    ]
    scope_str = "%20".join(scopes)  # Join with %20 for URL

    auth_url = (
        f"https://app.hubspot.com/oauth/authorize"
        f"?client_id={settings.HUBSPOT_CLIENT_ID}"
        f"&scope={scope_str}"
        f"&redirect_uri={settings.HUBSPOT_REDIRECT_URI}"
    )
    return redirect(auth_url)

@login_required
def hubspot_callback(request):
    code = request.GET.get('code')
    if not code:
        return JsonResponse({'error': 'Missing authorization code'}, status=400)

    token_url = 'https://api.hubapi.com/oauth/v1/token'
    data = {
        'grant_type': 'authorization_code',
        'client_id': settings.HUBSPOT_CLIENT_ID,
        'client_secret': settings.HUBSPOT_CLIENT_SECRET,
        'redirect_uri': settings.HUBSPOT_REDIRECT_URI,
        'code': code,
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post(token_url, data=data, headers=headers)

    if response.status_code == 200:
        tokens = response.json()
        access_token = tokens['access_token']
        refresh_token = tokens['refresh_token']

        # Get or create user profile
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        
        # Save tokens to profile
        profile.hubspot_access_token = access_token
        profile.hubspot_refresh_token = refresh_token
        profile.save()

        return redirect('leads:hubspot_connected_success')
    else:
        return JsonResponse({'error': 'Failed to get access token'}, status=400)

@login_required
def hubspot_connected_success(request):
    return render(request, 'leads/hubspot_connected.html') 