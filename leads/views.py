from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
import json
import logging
import requests
from django.conf import settings
import pprint
from .models import FacebookLead, FacebookPageConnection, UserProfile, LeadRoutingSettings, WebhookSettings
from base64 import b64encode, b64decode
from django.core.paginator import Paginator
from urllib.parse import urlencode
import csv
from datetime import datetime
from django.utils.dateparse import parse_date
import os
from leads.services.gpt import score_lead_with_gpt
from .forms import LeadRoutingSettingsForm, CustomUserCreationForm, EmailUpdateForm, WebhookSettingsForm, GHLApiKeyForm
from django.contrib.admin.views.decorators import staff_member_required
from leads.decorators import login_required_and_subscribed, check_subscription_limits
from leads.services.email_notifications import send_spam_lead_notification_email, send_non_spam_lead_notification_email
from collections import defaultdict
from leads.models import FacebookLead
from leads.services import salesforce, zoho, pipedrive, gohighlevel
from django.db.models import Q
from leads.hubspot_utils import create_hubspot_contact
from leads.utils.phone_validation import normalize_phone_number, validate_phone_twilio
from functools import wraps

logger = logging.getLogger(__name__)

# Write client_secret.json from env var at import time
secret_path = '/tmp/client_secret.json'
if not os.path.exists(secret_path):
    secret_json = os.environ.get('GOOGLE_CLIENT_SECRET_JSON')
    if secret_json:
        with open(secret_path, 'w') as f:
            f.write(secret_json)

def get_lead_data(leadgen_id, access_token):
    """Fetch lead data from Facebook Graph API using the provided access token."""
    try:
        graph_api_url = f"https://graph.facebook.com/v19.0/{leadgen_id}"
        params = {
            'access_token': access_token
        }
        
        response = requests.get(graph_api_url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error fetching lead data: {str(e)}")
        return None

def score_lead(lead_data):
    """Evaluate if a lead is spam based on its data using GPT and phone validation."""
    if not lead_data or 'field_data' not in lead_data:
        return {
            'total_score': 1.0,
            'is_spam': True,
            'gpt_score': 1.0,
            'gpt_reason': 'No lead data available',
        }
    
    # Convert field_data array to flat dictionary
    field_dict = {}
    custom_fields = {}
    core_fields = {'full_name', 'name', 'email', 'phone', 'phone_number', 'message'}
    
    for field in lead_data['field_data']:
        if field['values'] and len(field['values']) > 0:
            field_name = field['name']
            value = field['values'][0]
            
            # Normalize core field names
            normalized_name = field_name
            if field_name == 'phone_number':
                normalized_name = 'phone'
            elif field_name in ['name', 'full_name']:
                normalized_name = 'full_name'
            
            # Store in appropriate dictionary
            if field_name in core_fields:
                field_dict[normalized_name] = value
            else:
                custom_fields[field_name] = value
                field_dict[field_name] = value  # Include in field_dict for GPT scoring

    # --- Phone validation: Twilio only ---
    phone_number = field_dict.get('phone', '')
    twilio_result = None
    phone_spam_penalty = 0.0

    if phone_number:
        normalized = normalize_phone_number(phone_number)
        if normalized:
            twilio_result = validate_phone_twilio(normalized)
            logger.info(f"Twilio debug — raw: {phone_number}, normalized: {normalized}, result: {twilio_result}")

            if not twilio_result.get('valid'):
                phone_spam_penalty += 0.4
            elif twilio_result.get('line_type') == 'voip':
                phone_spam_penalty += 0.3
            if not twilio_result.get('is_us_number'):
                phone_spam_penalty += 0.2
        else:
            phone_spam_penalty += 0.4
            twilio_result = {'valid': False, 'error': 'Normalization failed'}

    try:
        # Get GPT scoring result
        gpt_result = score_lead_with_gpt(field_dict)  # Pass all fields for scoring
        gpt_score = float(gpt_result['score'])
        gpt_reason = gpt_result['reason']
        
        # --- Email spam penalty logic ---
        email_spam_penalty = 0.0
        email = field_dict.get('email', '')
        if email:
            is_valid_email = validate_email_zb(email)
            if not is_valid_email:
                email_spam_penalty += 0.3
        else:
            is_valid_email = False
        
        # Compute final results
        total_score = gpt_score + phone_spam_penalty + email_spam_penalty
        total_score = min(total_score, 1.0)  # Cap at 1.0
        is_spam = total_score > 0.7
        logger.info(f"Scoring debug — phone_spam_penalty: {phone_spam_penalty}, email_spam_penalty: {email_spam_penalty}, total_score: {total_score}, gpt_score: {gpt_score}, is_spam: {is_spam}")
        return {
            'total_score': total_score,
            'is_spam': is_spam,
            'gpt_score': gpt_score,
            'gpt_reason': gpt_reason,
            'field_data': field_dict,
            'custom_fields': custom_fields,
            'twilio_result': twilio_result,
            'phone_spam_penalty': phone_spam_penalty,
        }
        
    except Exception as e:
        logger.error(f"Error in GPT scoring: {str(e)}")
        return {
            'total_score': 1.0,
            'is_spam': True,
            'gpt_score': 1.0,
            'gpt_reason': f'Error in GPT scoring: {str(e)}',
            'field_data': field_dict,
            'custom_fields': custom_fields,
            'twilio_result': twilio_result,
            'phone_spam_penalty': 0.0,
        }

def validate_email_zb(email):
    """Validate email using ZeroBounce API."""
    try:
        logger.info(f"Validating email with ZeroBounce: {email}")
        api_key = '60e2eac9bffc4a3fb7877db03629d88f'
        api_url = 'https://api.zerobounce.net/v2/validate'
        
        params = {
            'api_key': api_key,
            'email': email,
            'ip_address': ''  # Optional IP address parameter
        }
        
        response = requests.get(api_url, params=params)
        response.raise_for_status()
        result = response.json()
        logger.info(f"ZeroBounce API response: {result}")
        # Check if email is valid (not disposable or invalid)
        is_valid = result.get('status') in ['valid', 'catch-all']
        logger.info(f"Email validation result for {email}: {is_valid}")
        return is_valid
        
    except requests.RequestException as e:
        logger.error(f"Error validating email with ZeroBounce: {str(e)}")
        return False



# Helper function to parse field_data

def parse_field_data(field_data):
    """
    Convert a list of {name, values} dicts into a flat dict.
    """
    result = {}
    for item in field_data:
        name = item.get('name')
        values = item.get('values', [])
        if name and values:
            result[name] = values[0] if len(values) == 1 else values
    return result

# Create your views here.

@csrf_exempt
@check_subscription_limits
@require_http_methods(["GET", "POST"])
def facebook_webhook(request):
    logger.warning("facebook_webhook view was called")
    if request.method == "GET":
        # Handle verification
        mode = request.GET.get('hub.mode')
        verify_token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        
        if mode == 'subscribe' and verify_token == "spamguard123":
            return HttpResponse(challenge, content_type='text/plain', status=200)
        else:
            return HttpResponse("Invalid verification token", status=403)
    
    elif request.method == "POST":
        raw_body = request.body.decode('utf-8')
        logger.info("=== Facebook Webhook POST Request ===")
        logger.info(f"Raw request body: {raw_body}")
        logger.info("===================================")
        
        try:
            body = json.loads(raw_body)
            page_id = body['entry'][0]['id']
            lead_value = body['entry'][0]['changes'][0]['value']
            leadgen_id = lead_value.get('leadgen_id')
            field_data = lead_value.get('field_data')
            logger.info(f"Received webhook for page {page_id}, leadgen_id: {leadgen_id}")
            try:
                page_connection = FacebookPageConnection.objects.get(page_id=page_id)
                logger.warning(f"Found page connection for user: {page_connection.user.id}")
                profile = page_connection.user.profile
                logger.warning(f"User profile details - subscription_status: {profile.subscription_status}")
            except FacebookPageConnection.DoesNotExist:
                logger.error(f"No page connection found for page_id: {page_id}")
                return HttpResponse("Page not connected", status=404)

            # If field_data is present, use it directly
            if field_data:
                parsed_fields = parse_field_data(field_data)
                logger.info(f"Parsed lead fields from field_data: {parsed_fields}")
                logger.info("Data source: field_data (manual/test payload)")
                data_source = 'field_data'
            else:
                # Fallback to fetching from Facebook API
                try:
                    lead_data = get_lead_data(leadgen_id, page_connection.page_access_token)
                    logger.info(f"Fetched lead data from Facebook API: {lead_data}")
                    logger.info("Data source: Facebook API")
                    data_source = 'api'
                    # Facebook API returns field_data as well
                    parsed_fields = parse_field_data(lead_data.get('field_data', []))
                except Exception as e:
                    logger.error(f"Failed to fetch lead from Facebook: {e}")
                    return HttpResponse("Failed to fetch lead from Facebook", status=400)

            # Save the lead using the parsed fields
            try:
                full_name = parsed_fields.get('full_name') or parsed_fields.get('name', '')
                email = parsed_fields.get('email', '')
                phone = parsed_fields.get('phone_number', parsed_fields.get('phone', ''))
                message = parsed_fields.get('message', '')
                custom_fields = {k: v for k, v in parsed_fields.items() if k not in ['full_name', 'name', 'email', 'phone', 'phone_number', 'message']}
                # Score the lead
                if field_data:
                    score_result = score_lead({'field_data': field_data})
                else:
                    score_result = score_lead(lead_data)
                logger.info(f"Lead scored as {'spam' if score_result['is_spam'] else 'not spam'}: {score_result['gpt_reason']}")
                logger.info(f"Custom fields: {custom_fields}")
                is_valid_email = validate_email_zb(email) if email else False
                logger.info(f"About to validate phone: {phone}")
                logger.info(f"Raw phone before normalization: {phone}")
                normalized_phone = normalize_phone_number(phone)
                logger.info(f"Normalized phone: {normalized_phone}")
                # numverify_result = validate_phone_with_numverify(normalized_phone) if normalized_phone else None
                twilio_result = validate_phone_twilio(normalized_phone) if normalized_phone else None
                is_valid_phone = twilio_result.get('valid') if twilio_result else False
                phone_to_save = normalized_phone if normalized_phone else phone
                # --- Advanced filter logic ---
                filter_matched = True
                try:
                    settings = page_connection.user.lead_routing_settings
                    filters = settings.advanced_filters or {}
                    for field, keywords in filters.items():
                        if not isinstance(keywords, list) or not keywords:
                            continue
                        match = False
                        if field in ["full_name", "email", "phone", "message"]:
                            value = locals().get(field, "")
                            for kw in keywords:
                                if value and kw.lower() in value.lower():
                                    match = True
                                    break
                        else:
                            value = custom_fields.get(field, "")
                            for kw in keywords:
                                if value and kw.lower() in str(value).lower():
                                    match = True
                                    break
                        if not match:
                            filter_matched = False
                            break
                except LeadRoutingSettings.DoesNotExist:
                    pass
                # --- End advanced filter logic ---
                lead = FacebookLead.objects.create(
                    user=page_connection.user,
                    leadgen_id=leadgen_id,
                    full_name=full_name,
                    email=email,
                    phone=phone_to_save,
                    message=message,
                    custom_fields=custom_fields,
                    gpt_score=score_result['gpt_score'],
                    gpt_reason=score_result['gpt_reason'],
                    is_spam=(not filter_matched) or score_result['is_spam'],
                    is_valid_email=is_valid_email,
                    is_valid_phone=is_valid_phone,
                    is_filtered_out=False,
                )
                # Increment lead_filter_count if the lead is not spam
                if not lead.is_spam and hasattr(lead.user, 'profile'):
                    lead.user.profile.lead_filter_count += 1
                    lead.user.profile.save()
                logger.warning(f"Lead saved with ID: {lead.id} (source: {data_source})")

                # Send email notification based on lead status
                try:
                    if lead.is_spam:
                        send_spam_lead_notification_email(lead, page_connection.user)
                    else:
                        send_non_spam_lead_notification_email(lead, page_connection.user)
                except Exception as email_error:
                    logger.error(f"Error sending email notification: {email_error}")

            except Exception as save_error:
                logger.error(f"Error saving lead: {save_error}")
                return HttpResponse("Error saving lead", status=500)
            return HttpResponse("OK", status=200)
            
        except json.JSONDecodeError:
            logger.error("Invalid JSON received from Facebook webhook")
            return HttpResponse("Invalid JSON", status=400)
        except (KeyError, IndexError) as e:
            logger.error(f"Error extracting data from webhook payload: {str(e)}")
            return HttpResponse("Invalid webhook payload", status=400)
        except Exception as e:
            logger.error(f"Unhandled error in webhook: {e}")
            return HttpResponse("Internal server error", status=500)

def signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Set Free plan defaults
            if hasattr(user, 'profile'):
                user.profile.lead_filter_quota = 50
                user.profile.subscription_status = 'active'
                user.profile.save()
            messages.success(request, 'Welcome to the Free tier! You get 50 leads per month, basic spam filtering, and community support. <a href="/pricing/" class="btn btn-sm btn-primary ms-2">Upgrade Plan</a>')
            login(request, user)
            return redirect('leads:dashboard')
    else:
        form = CustomUserCreationForm()
    return render(request, 'leads/signup.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('leads:dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'leads/login.html')

def logout_view(request):
    logout(request)
    messages.info(request, 'Logged out successfully!')
    return redirect('leads:homepage')

@login_required
def lead_dashboard(request):
    """Display a dashboard of valid and spam leads for the authenticated user."""
    facebook_connected = request.session.pop('facebook_connected', False)
    facebook_disconnected = request.session.pop('facebook_disconnected', False)
    analytics_labels = []
    analytics_valid_counts = []
    analytics_spam_counts = []
    try:
        # Get Facebook page connection status first
        try:
            facebook_page = FacebookPageConnection.objects.filter(user=request.user).first()
            if facebook_page:
                logger.info(f"User {request.user.id} has connected page: {facebook_page.page_name} ({facebook_page.page_id})")
            else:
                logger.info(f"User {request.user.id} has no connected Facebook pages")
        except Exception as e:
            logger.error(f"Error getting Facebook page connection: {str(e)}")
            facebook_page = None
        
        # Get all leads for the current user ordered by received_at (newest first)
        try:
            all_leads = FacebookLead.objects.filter(user=request.user).order_by('-received_at')
            # --- Date filter logic ---
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            if start_date:
                start_date_parsed = parse_date(start_date)
                if start_date_parsed:
                    all_leads = all_leads.filter(received_at__date__gte=start_date_parsed)
            if end_date:
                end_date_parsed = parse_date(end_date)
                if end_date_parsed:
                    all_leads = all_leads.filter(received_at__date__lte=end_date_parsed)
            # --- Advanced filter logic ---
            # (Removed: now handled at lead creation)
            # --- End advanced filter logic ---
            valid_leads = all_leads.filter(is_spam=False)
            spam_leads = all_leads.filter(is_spam=True)
            
            # Get counts for the dashboard
            total_leads = all_leads.count()
            valid_count = valid_leads.count()
            spam_count = spam_leads.count()
            spam_rate = round((spam_count / total_leads * 100) if total_leads > 0 else 0, 1)
            
            # Paginate both lists
            valid_paginator = Paginator(valid_leads, 25)
            spam_paginator = Paginator(spam_leads, 25)
            
            # Get current page numbers from request
            valid_page = request.GET.get('valid_page', 1)
            spam_page = request.GET.get('spam_page', 1)
            
            # Get the page objects
            valid_leads_page = valid_paginator.get_page(valid_page)
            spam_leads_page = spam_paginator.get_page(spam_page)

            # --- Analytics aggregation ---
            analytics = defaultdict(lambda: {'valid': 0, 'spam': 0})
            for lead in all_leads:
                date_str = lead.received_at.strftime('%Y-%m-%d')
                if lead.is_spam:
                    analytics[date_str]['spam'] += 1
                else:
                    analytics[date_str]['valid'] += 1
            analytics_labels = sorted(analytics.keys())
            analytics_valid_counts = [analytics[date]['valid'] for date in analytics_labels]
            analytics_spam_counts = [analytics[date]['spam'] for date in analytics_labels]
        except Exception as e:
            logger.error(f"Error getting leads data: {str(e)}")
            valid_leads_page = []
            spam_leads_page = []
            total_leads = 0
            valid_count = 0
            spam_count = 0
            spam_rate = 0
        
        context = {
            'facebook_page': facebook_page,
            'valid_leads': valid_leads_page,
            'spam_leads': spam_leads_page,
            'total_leads': total_leads,
            'valid_count': valid_count,
            'spam_count': spam_count,
            'spam_rate': spam_rate,
            'start_date': start_date or '',
            'end_date': end_date or '',
            'facebook_connected': facebook_connected,
            'facebook_disconnected': facebook_disconnected,
            'analytics_labels': analytics_labels,
            'analytics_valid_counts': analytics_valid_counts,
            'analytics_spam_counts': analytics_spam_counts,
        }
        
        return render(request, 'leads/leads_dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Error in dashboard view: {str(e)}")
        messages.error(request, 'An error occurred while loading the dashboard')
        context = {
            'facebook_page': None,
            'valid_leads': [],
            'spam_leads': [],
            'total_leads': 0,
            'valid_count': 0,
            'spam_count': 0,
            'spam_rate': 0,
            'start_date': '',
            'end_date': '',
            'facebook_connected': False,
            'facebook_disconnected': False,
            'analytics_labels': [],
            'analytics_valid_counts': [],
            'analytics_spam_counts': [],
        }
        return render(request, 'leads/leads_dashboard.html', context)

def homepage(request):
    """Render the homepage with a link to the leads dashboard."""
    if request.user.is_authenticated:
        return redirect('leads:dashboard')
    return render(request, 'leads/homepage.html')

@login_required
def facebook_connect(request):
    """Redirect user to Facebook OAuth endpoint for page access."""
    # Facebook OAuth parameters
    params = {
        'client_id': settings.FACEBOOK_APP_ID,
        'redirect_uri': request.build_absolute_uri('/facebook/callback/'),
        'scope': 'pages_show_list,leads_retrieval,pages_manage_metadata,pages_read_engagement',
        'response_type': 'code',
        'state': b64encode(str(request.user.id).encode()).decode(),  # Encode user ID for security
        'auth_type': 'rerequest',  # Force re-authentication
        'display': 'popup',  # Use popup display
    }
    
    # Build the Facebook OAuth URL
    facebook_oauth_url = f"https://www.facebook.com/v19.0/dialog/oauth?{urlencode(params)}"
    
    logger.info(f"Redirecting user {request.user.id} to Facebook OAuth: {facebook_oauth_url}")
    
    # Clear any existing Facebook sessions in our app
    for key in list(request.session.keys()):
        if key.startswith('facebook_'):
            del request.session[key]
    request.session.modified = True
    
    return redirect(facebook_oauth_url)

@login_required
def facebook_callback(request):
    """Handle Facebook OAuth callback and fetch user's pages."""
    # Check for error response from Facebook
    if 'error' in request.GET:
        error = request.GET.get('error')
        error_reason = request.GET.get('error_reason', '')
        error_description = request.GET.get('error_description', '')
        logger.error(f"Facebook OAuth error: {error} - {error_reason} - {error_description}")
        messages.error(request, f"Facebook connection failed: {error_description}")
        return redirect('leads:dashboard')

    # Get the authorization code from the request
    code = request.GET.get('code')
    state = request.GET.get('state')
    
    if not code:
        messages.error(request, 'No authorization code received from Facebook')
        return redirect('leads:dashboard')
    
    try:
        # Verify state parameter matches the user's ID
        decoded_state = b64decode(state.encode()).decode()
        if int(decoded_state) != request.user.id:
            messages.error(request, 'Invalid state parameter')
            return redirect('leads:dashboard')
        
        # Exchange code for access token
        token_url = 'https://graph.facebook.com/v19.0/oauth/access_token'
        token_params = {
            'client_id': settings.FACEBOOK_APP_ID,
            'redirect_uri': request.build_absolute_uri('/facebook/callback/'),
            'client_secret': settings.FACEBOOK_APP_SECRET,
            'code': code
        }
        
        token_response = requests.get(token_url, params=token_params)
        token_response.raise_for_status()
        token_data = token_response.json()
        
        if 'error' in token_data:
            logger.error(f"Facebook token error: {token_data['error']}")
            messages.error(request, 'Error obtaining Facebook access token')
            return redirect('leads:dashboard')
            
        access_token = token_data['access_token']
        
        # Fetch user's pages
        pages_url = 'https://graph.facebook.com/me/accounts'
        pages_params = {
            'access_token': access_token,
            'fields': 'id,name,access_token'  # Explicitly request these fields
        }
        
        pages_response = requests.get(pages_url, params=pages_params)
        pages_response.raise_for_status()
        pages_data = pages_response.json()
        
        if not pages_data.get('data'):
            messages.warning(request, 'No Facebook Pages found. Make sure you have admin access to at least one Facebook Page.')
            return redirect('leads:dashboard')
        
        # Get the first available page
        page = pages_data['data'][0]
        page_id = page['id']
        page_name = page['name']
        page_access_token = page['access_token']
        
        # Create or update the page connection
        page_connection, created = FacebookPageConnection.objects.update_or_create(
            page_id=page_id,
            defaults={
                'user': request.user,
                'page_name': page_name,
                'page_access_token': page_access_token
            }
        )
        
        # Subscribe the page to the webhook
        subscribe_url = f'https://graph.facebook.com/v19.0/{page_id}/subscribed_apps'
        subscribe_params = {
            'access_token': page_access_token,
            'subscribed_fields': 'leadgen'
        }
        
        subscribe_response = requests.post(subscribe_url, params=subscribe_params)
        subscribe_response.raise_for_status()
        
        # Log the successful connection
        logger.info(f"User {request.user.id} successfully connected page {page_name} ({page_id})")
        
        request.session['facebook_connected'] = True
        return redirect('leads:dashboard')
        
    except requests.RequestException as e:
        logger.error(f"Error in Facebook OAuth callback: {str(e)}")
        messages.error(request, 'Error connecting to Facebook. Please try again.')
        return redirect('leads:dashboard')
    except Exception as e:
        logger.error(f"Unexpected error in Facebook callback: {str(e)}")
        messages.error(request, 'An unexpected error occurred. Please try again.')
        return redirect('leads:dashboard')

@login_required
def select_facebook_page(request):
    """Display available Facebook pages for selection."""
    pages = request.session.get('facebook_pages')
    
    if not pages:
        messages.error(request, 'Session expired or invalid. Please reconnect your Facebook account.')
        return redirect('leads:dashboard')
    
    context = {
        'pages': pages
    }
    
    return render(request, 'leads/select_facebook_page.html', context)

@login_required
@require_http_methods(["POST"])
def save_facebook_page(request):
    """Save the selected Facebook page and subscribe it to the webhook."""
    try:
        # Get page data from POST request
        page_id = request.POST.get('page_id')
        page_name = request.POST.get('page_name')
        page_access_token = request.POST.get('page_access_token')
        force_reassign = request.POST.get('force_reassign') == 'true'
        
        # Log the received data (excluding sensitive token)
        logger.info(f"Attempting to save page - ID: {page_id}, Name: {page_name}")
        
        if not all([page_id, page_name, page_access_token]):
            missing = []
            if not page_id: missing.append('page_id')
            if not page_name: missing.append('page_name')
            if not page_access_token: missing.append('page_access_token')
            logger.error(f"Missing required page information: {', '.join(missing)}")
            messages.error(request, 'Missing required page information')
            return redirect('leads:dashboard')
        
        # Check if page is already connected to another user
        existing_connection = FacebookPageConnection.objects.filter(page_id=page_id).exclude(user=request.user).first()
        if existing_connection and not force_reassign:
            logger.warning(f"Page {page_id} is already connected to user {existing_connection.user.id}")
            # Store connection attempt info in session for potential reassignment
            request.session['pending_page_connection'] = {
                'page_id': page_id,
                'page_name': page_name,
                'page_access_token': page_access_token,
                'current_owner': existing_connection.user.username
            }
            request.session.modified = True
            messages.warning(request, 
                f'This page is already connected to another account ({existing_connection.user.username}). '
                'Please disconnect it first or use force reassign option.')
            return redirect('leads:handle_page_conflict')
        
        try:
            # Create or update the page connection
            page_connection, created = FacebookPageConnection.objects.update_or_create(
                page_id=page_id,
                defaults={
                    'user': request.user,
                    'page_name': page_name,
                    'page_access_token': page_access_token
                }
            )
            
            # Log the connection/reconnection
            if created:
                logger.info(f"User {request.user.id} connected new page {page_name} ({page_id})")
            else:
                logger.info(f"User {request.user.id} reconnected existing page {page_name} ({page_id})")
            
            # Subscribe the page to the webhook
            subscribe_url = f'https://graph.facebook.com/v19.0/{page_id}/subscribed_apps'
            subscribe_params = {
                'access_token': page_access_token,
                'subscribed_fields': 'leadgen'
            }
            
            subscribe_response = requests.post(subscribe_url, params=subscribe_params)
            subscribe_response.raise_for_status()
            
            # Verify the page was actually saved
            saved_connection = FacebookPageConnection.objects.filter(page_id=page_id, user=request.user).first()
            if not saved_connection:
                raise Exception("Page connection was not saved successfully")
            
            # Log the successful subscription
            logger.info(f"Successfully subscribed page {page_name} ({page_id}) to webhook")
            
            request.session['facebook_connected'] = True
            messages.success(request, f'Successfully connected to {page_name}')
            return redirect('leads:dashboard')
            
        except FacebookPageConnection.DoesNotExist:
            logger.error(f"Failed to save page connection for page {page_id}")
            messages.error(request, 'Failed to save page connection')
            return redirect('leads:dashboard')
            
    except requests.RequestException as e:
        logger.error(f"Error subscribing page to webhook: {str(e)}")
        messages.error(request, 'Error connecting to Facebook page')
        return redirect('leads:dashboard')
    except Exception as e:
        logger.error(f"Unexpected error saving page: {str(e)}")
        messages.error(request, 'An unexpected error occurred')
        return redirect('leads:dashboard')

@login_required
def handle_page_conflict(request):
    """Handle cases where a Facebook page is already connected to another account."""
    pending_connection = request.session.get('pending_page_connection')
    if not pending_connection:
        messages.error(request, 'No pending page connection found')
        return redirect('leads:dashboard')
    
    context = {
        'page_name': pending_connection['page_name'],
        'current_owner': pending_connection['current_owner'],
    }
    
    return render(request, 'leads/handle_page_conflict.html', context)

@login_required
def connected_pages_view(request):
    """Display all Facebook pages connected by the current user."""
    # Get all page connections for the current user
    page_connections = FacebookPageConnection.objects.filter(user=request.user).order_by('-connected_at')
    
    context = {
        'page_connections': page_connections,
        'total_pages': page_connections.count(),
    }
    
    return render(request, 'leads/connected_pages.html', context)

@login_required
@require_http_methods(["POST"])
def disconnect_page_view(request, page_id):
    """Disconnect a Facebook page and optionally unsubscribe it from the webhook."""
    try:
        # Get the page connection
        page_connection = get_object_or_404(FacebookPageConnection, page_id=page_id, user=request.user)
        
        # Optionally unsubscribe the page from the webhook
        try:
            unsubscribe_url = f'https://graph.facebook.com/v19.0/{page_id}/subscribed_apps'
            unsubscribe_params = {
                'access_token': page_connection.page_access_token,
                'subscribed_fields': 'leadgen'
            }
            
            # Make DELETE request to unsubscribe
            unsubscribe_response = requests.delete(unsubscribe_url, params=unsubscribe_params)
            unsubscribe_response.raise_for_status()
            logger.info(f"Successfully unsubscribed page {page_connection.page_name} from webhook")
        except requests.RequestException as e:
            logger.warning(f"Failed to unsubscribe page from webhook: {str(e)}")
            # Continue with disconnection even if unsubscribe fails
        
        # Delete the page connection
        page_name = page_connection.page_name
        page_connection.delete()
        
        # Log the successful disconnection
        logger.info(f"Successfully disconnected page {page_name} ({page_id})")
        
        request.session['facebook_disconnected'] = True
        messages.success(request, f'Successfully disconnected {page_name}')
        return redirect('leads:dashboard')
        
    except Exception as e:
        logger.error(f"Error disconnecting page: {str(e)}")
        messages.error(request, 'An error occurred while disconnecting the page')
        return redirect('leads:dashboard')

@login_required
def lead_detail_view(request, pk):
    """Display detailed information about a specific lead."""
    # Get the lead and verify ownership
    lead = get_object_or_404(FacebookLead, pk=pk, user=request.user)
    
    context = {
        'lead': lead,
        'is_spam': lead.is_spam,
        'is_valid_email': lead.is_valid_email,
        'is_valid_phone': lead.is_valid_phone,
    }
    
    return render(request, 'leads/lead_detail.html', context)

@login_required
@require_http_methods(["POST"])
def toggle_lead_spam(request, pk):
    """Toggle the spam status of a lead."""
    lead = get_object_or_404(FacebookLead, pk=pk, user=request.user)
    
    # Toggle the spam status
    lead.is_spam = not lead.is_spam
    logger.info(f"Manual spam toggle — Lead {lead.id} marked as {'SPAM' if lead.is_spam else 'NOT SPAM'} by user {request.user.id}. GPT score: {lead.gpt_score}, reason: {lead.gpt_reason}")
    lead.save()

    # If the lead is now valid, send to HubSpot
    if not lead.is_spam:
        try:
            from leads.services.hubspot import send_lead_to_hubspot
            result = send_lead_to_hubspot(request.user, lead)
            if not result.get('success'):
                logger.error(f"Failed to sync lead {lead.id} to HubSpot: {result.get('error')}")
            else:
                logger.info(f"Lead {lead.id} synced to HubSpot: {result}")
        except Exception as e:
            logger.error(f"Exception while syncing lead {lead.id} to HubSpot: {e}")

    # Log the action
    logger.info(f"User {request.user.id} toggled spam status for lead {lead.id} to {lead.is_spam}")
    
    messages.success(request, f'Lead marked as {"spam" if lead.is_spam else "valid"}')
    return redirect('leads:lead_detail', pk=pk)

@login_required
def export_clean_leads(request):
    """Export all non-spam leads for the current user as a CSV file."""
    # Get all non-spam leads for the current user
    leads = FacebookLead.objects.filter(user=request.user, is_spam=False)
    
    # Apply date filters if provided
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        start_date = parse_date(start_date)
        if start_date:
            leads = leads.filter(received_at__date__gte=start_date)
    
    if end_date:
        end_date = parse_date(end_date)
        if end_date:
            leads = leads.filter(received_at__date__lte=end_date)
    
    # Order by received date
    leads = leads.order_by('-received_at')
    
    # Create the HttpResponse object with CSV header
    response = HttpResponse(content_type='text/csv')
    filename = f"clean_leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if start_date or end_date:
        filename += "_filtered"
    response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
    
    # Create CSV writer
    writer = csv.writer(response)
    
    # Write header row
    writer.writerow([
        'Full Name',
        'Email',
        'Phone',
        'Message',
        'GPT Score',
        'Custom Fields',
        'Received At'
    ])
    
    # Write data rows
    for lead in leads:
        # Serialize custom fields as a string
        custom_fields_str = json.dumps(lead.custom_fields) if lead.custom_fields else ''
        
        writer.writerow([
            lead.full_name,
            lead.email,
            lead.phone,
            lead.message or '',
            f"{lead.gpt_score:.2f}",
            custom_fields_str,
            lead.received_at.strftime("%Y-%m-%d %H:%M:%S")
        ])
    
    # Log the export
    logger.info(f"User {request.user.id} exported {leads.count()} clean leads" + 
                (f" from {start_date} to {end_date}" if start_date or end_date else ""))
    
    return response

def privacy_policy(request):
    return render(request, 'leads/privacy.html')

def terms_of_service(request):
    return render(request, 'leads/terms.html')

def pricing_view(request):
    return render(request, 'leads/pricing.html', {
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
        'starter_price_id': settings.STRIPE_PRICE_ID_STARTER,
        'growth_price_id': settings.STRIPE_PRICE_ID_GROWTH,
        'enterprise_price_id': settings.STRIPE_PRICE_ID_ENTERPRISE,
    })

@login_required
def integrations_view(request):
    # Get or create the user's profile
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    if profile.lead_filter_quota == 50:
        messages.warning(request, 'Upgrade your plan to enable integrations.')
        return redirect('leads:pricing')
    pipedrive_connected = bool(profile.pipedrive_access_token)
    context = {
        'hubspot_connected': bool(profile.hubspot_access_token),
        'pipedrive_connected': pipedrive_connected,
    }
    return render(request, 'leads/integrations.html', context)

@login_required
def hubspot_connect(request):
    scopes = [
        "crm.objects.contacts.read",
        "crm.objects.contacts.write",
        "oauth",  # IMPORTANT: include oauth scope
    ]
    scope_str = "%20".join(scopes)  # HubSpot expects scopes separated by %20 (space)

    auth_url = (
        f"https://app.hubspot.com/oauth/authorize"
        f"?client_id={settings.HUBSPOT_CLIENT_ID}"
        f"&scope={scope_str}"
        f"&redirect_uri={settings.HUBSPOT_REDIRECT_URI}"
    )
    return redirect(auth_url)

def about_view(request):
    return render(request, 'leads/about.html')

@login_required
def lead_routing_settings_view(request):
    # Ensure the user has a LeadRoutingSettings object
    try:
        settings = request.user.lead_routing_settings
    except LeadRoutingSettings.DoesNotExist:
        settings = LeadRoutingSettings.objects.create(user=request.user, notification_email=request.user.email)

    if request.method == 'POST':
        form = LeadRoutingSettingsForm(request.POST, instance=settings)
        if form.is_valid():
            form.save()
            messages.success(request, 'Lead routing settings updated successfully.')
            return redirect('leads:lead_routing_settings')
    else:
        form = LeadRoutingSettingsForm(instance=settings)
    return render(request, 'leads/lead_routing_settings.html', {'form': form})

@login_required
def update_email_view(request):
    if request.method == 'POST':
        form = EmailUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Email updated successfully!')
            return redirect('leads:update_email')
    else:
        form = EmailUpdateForm(instance=request.user)
    return render(request, 'leads/update_email.html', {'form': form})

@login_required
def webhook_settings_view(request):
    try:
        webhook_settings = request.user.webhook_settings
    except WebhookSettings.DoesNotExist:
        webhook_settings = None

    if request.method == 'POST':
        form = WebhookSettingsForm(request.POST, instance=webhook_settings)
        if form.is_valid():
            ws = form.save(commit=False)
            ws.user = request.user
            ws.save()
            messages.success(request, 'Webhook settings updated!')
            return redirect('leads:webhook_settings')
    else:
        form = WebhookSettingsForm(instance=webhook_settings)

    return render(request, 'leads/webhook_settings.html', {'form': form})

@login_required
@require_POST
def test_webhook(request):
    try:
        webhook_settings = request.user.webhook_settings
    except WebhookSettings.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'No webhook settings found for this user.'}, status=400)

    if not webhook_settings.webhook_url:
        return JsonResponse({'success': False, 'error': 'No webhook URL configured.'}, status=400)

    from .models import FacebookLead
    lead = FacebookLead.objects.filter(user=request.user).order_by('-received_at').first()
    if lead:
        payload = {
            'name': lead.full_name,
            'email': lead.email,
            'phone': lead.phone,
            'message': lead.message,
            'timestamp': lead.received_at.isoformat() if lead.received_at else '',
        }
    else:
        payload = {
            'name': 'Sample Lead',
            'email': 'sample@example.com',
            'phone': '+1234567890',
            'message': 'This is a test lead from Spam Guard.',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
        }

    logger.info(f"[TEST] Attempting to POST to webhook: {webhook_settings.webhook_url} with payload: {payload}")
    try:
        resp = requests.post(
            webhook_settings.webhook_url,
            json=payload,
            timeout=5
        )
        logger.info(f"[TEST] Webhook POST response: {resp.status_code} {resp.text}")
        if resp.status_code >= 200 and resp.status_code < 300:
            return JsonResponse({'success': True, 'message': f'Successfully sent test payload. Webhook responded with status {resp.status_code}.', 'payload': payload})
        else:
            return JsonResponse({'success': False, 'error': f'Webhook responded with status {resp.status_code}: {resp.text}', 'payload': payload}, status=400)
    except Exception as exc:
        logger.warning(f"[TEST] Failed to POST to webhook: {exc}")
        return JsonResponse({'success': False, 'error': f'Failed to POST to webhook: {exc}', 'payload': payload}, status=400)

@staff_member_required
@require_http_methods(["GET"])
def validate_phone_view(request):
    phone = request.GET.get('phone', '')
    if not phone:
        return JsonResponse({'error': 'Missing phone parameter'}, status=400)
    # from leads.utils.phone_validation import validate_phone_with_numverify
    result = validate_phone_twilio(phone)
    return JsonResponse(result)

@login_required
def subscribe(request):
    return render(request, 'subscribe.html')

def how_to_folder_view(request):
    return render(request, 'leads/how_to_folder.html')

def how_to_inbox_view(request):
    return render(request, 'leads/how_to_inbox.html')

def solutions_view(request):
    return render(request, 'leads/solutions.html')

@login_required
def ghl_settings_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = GHLApiKeyForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "GHL API Key saved successfully.")
            return redirect('leads:integrations')
    else:
        form = GHLApiKeyForm(instance=profile)

    return render(request, 'leads/ghl_settings.html', {'form': form})

@login_required
def ghl_disconnect(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.ghl_api_key = None
    profile.save()
    messages.success(request, "GoHighLevel disconnected successfully.")
    return redirect('leads:integrations')

@login_required
def settings_view(request):
    facebook_page = FacebookPageConnection.objects.filter(user=request.user).first()
    return render(request, 'leads/settings.html', {'facebook_page': facebook_page})

@login_required
@require_POST
def send_to_crm_view(request, lead_id):
    try:
        lead = get_object_or_404(FacebookLead, pk=lead_id, user=request.user)
        user = request.user
        profile = user.profile
        result = None

        # Try each CRM in order of connection
        if getattr(profile, 'hubspot_access_token', None):
            result = create_hubspot_contact(user, lead)
        elif getattr(profile, 'salesforce_access_token', None) and getattr(profile, 'salesforce_instance_url', None):
            result = salesforce.send_lead_to_salesforce(user, lead)
        elif getattr(profile, 'zoho_access_token', None):
            result = zoho.send_lead_to_zoho(user, lead)
        elif getattr(profile, 'pipedrive_access_token', None):
            result = pipedrive.send_lead_to_pipedrive(user, lead)
        elif getattr(profile, 'ghl_api_key', None):
            result = gohighlevel.send_lead_to_ghl(user, lead)
        else:
            return JsonResponse({'success': False, 'error': 'No CRM integration connected.'}, status=400)

        # Interpret result
        if isinstance(result, dict):
            if result.get('success'):
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'success': False, 'error': result.get('error', 'Unknown error')}, status=400)
        elif isinstance(result, bool):
            if result:
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'success': False, 'error': 'Failed to send to HubSpot.'}, status=400)
        elif hasattr(result, 'ok') and hasattr(result, 'status_code'):
            if result.ok:
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'success': False, 'error': getattr(result, 'text', 'Unknown error')}, status=400)
        elif result is None:
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': str(result)}, status=400)
    except Exception as e:
        import traceback
        logger.error(f"Error in send_to_crm_view: {e}\n{traceback.format_exc()}")
        return JsonResponse({'success': False, 'error': f'Internal server error: {str(e)}'}, status=500)

def check_subscription_limits(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated:
            profile = getattr(request.user, 'profile', None)
            if profile and profile.lead_filter_quota > 0 and profile.lead_filter_count >= profile.lead_filter_quota:
                # For webhook requests, return a JSON response
                if request.path.startswith('/facebook/webhook'):
                    return JsonResponse({
                        'error': 'Lead quota exceeded',
                        'message': 'You have reached your monthly lead limit. Please upgrade your plan to continue.'
                    }, status=403)
                # For browser requests, redirect to pricing page
                messages.warning(request, 'You have reached your monthly lead limit. Please upgrade your plan to continue.')
                return redirect('leads:pricing')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

@login_required
def subscription_management_view(request):
    profile = request.user.profile
    return render(request, 'leads/subscription_management.html', {'profile': profile})
