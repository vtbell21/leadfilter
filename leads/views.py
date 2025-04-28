from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
import json
import logging
import requests
from django.conf import settings
import pprint
from .models import FacebookLead, FacebookPageConnection, UserProfile
from base64 import b64encode, b64decode
from django.core.paginator import Paginator
from urllib.parse import urlencode
import csv
from datetime import datetime
from django.utils.dateparse import parse_date
import os

logger = logging.getLogger(__name__)

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
    """Evaluate if a lead is spam based on its data using GPT."""
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
    
    try:
        from services.gpt import score_lead_with_gpt
        
        # Get GPT scoring result
        gpt_result = score_lead_with_gpt(field_dict)  # Pass all fields for scoring
        gpt_score = float(gpt_result['score'])
        gpt_reason = gpt_result['reason']
        
        # Compute final results
        total_score = gpt_score  # Can be extended to include other scores
        is_spam = gpt_score > 0.7
        
        return {
            'total_score': total_score,
            'is_spam': is_spam,
            'gpt_score': gpt_score,
            'gpt_reason': gpt_reason,
            'field_data': field_dict,
            'custom_fields': custom_fields
        }
        
    except Exception as e:
        logger.error(f"Error in GPT scoring: {str(e)}")
        return {
            'total_score': 1.0,
            'is_spam': True,
            'gpt_score': 1.0,
            'gpt_reason': f'Error in GPT scoring: {str(e)}',
            'field_data': field_dict,
            'custom_fields': custom_fields
        }

def validate_email_zb(email):
    """Validate email using ZeroBounce API."""
    try:
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
        
        # Check if email is valid (not disposable or invalid)
        return result.get('status') in ['valid', 'catch-all']
        
    except requests.RequestException as e:
        logger.error(f"Error validating email with ZeroBounce: {str(e)}")
        return False

def validate_phone_twilio(phone_number):
    """Validate phone number using Twilio Lookup API."""
    try:
        # Twilio credentials from environment variables
        account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
        auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
        
        if not account_sid or not auth_token:
            logger.error("Twilio credentials not found in environment variables")
            return False
        
        # Create basic auth header
        auth_string = f"{account_sid}:{auth_token}"
        auth_bytes = auth_string.encode('ascii')
        auth_header = f"Basic {b64encode(auth_bytes).decode('ascii')}"
        
        # Prepare the API request
        api_url = f"https://lookups.twilio.com/v1/PhoneNumbers/{phone_number}"
        headers = {
            'Authorization': auth_header
        }
        
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        result = response.json()
        
        # Check if phone is valid and possible
        return result.get('valid', False) and result.get('phone_number', {}).get('carrier', {}).get('type') != 'voip'
        
    except requests.RequestException as e:
        logger.error(f"Error validating phone with Twilio: {str(e)}")
        return False

# Create your views here.

@csrf_exempt
@require_http_methods(["GET", "POST"])
def facebook_webhook(request):
    if request.method == "GET":
        # Handle verification
        mode = request.GET.get('hub.mode')
        verify_token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        
        if mode == 'subscribe' and verify_token == "leadfilter123":
            return HttpResponse(challenge, content_type='text/plain', status=200)
        else:
            return HttpResponse("Invalid verification token", status=403)
    
    elif request.method == "POST":
        # Print the raw request body for debugging
        print("\n=== Raw Request Body ===")
        pprint.pprint(request.body.decode())
        print("=======================\n")
        
        try:
            # Parse the webhook payload
            body = json.loads(request.body)
            
            # Extract page_id and leadgen_id
            page_id = body['entry'][0]['id']
            leadgen_id = body['entry'][0]['changes'][0]['value']['leadgen_id']
            logger.info(f"Received webhook for page {page_id}, leadgen_id: {leadgen_id}")
            
            # Look up the page connection
            try:
                page_connection = FacebookPageConnection.objects.get(page_id=page_id)
            except FacebookPageConnection.DoesNotExist:
                logger.error(f"No page connection found for page_id: {page_id}")
                return HttpResponse("Page not connected", status=404)
            
            # Get full lead data using the page's access token
            lead_data = get_lead_data(leadgen_id, page_connection.page_access_token)
            if lead_data:
                print("\n=== Lead Data ===")
                pprint.pprint(lead_data)
                print("=================\n")
                
                # Score the lead
                score_result = score_lead(lead_data)
                logger.info(f"Lead scored as {'spam' if score_result['is_spam'] else 'not spam'}: {score_result['gpt_reason']}")
                
                # Extract field data
                field_dict = score_result['field_data']
                custom_fields = score_result['custom_fields']
                
                # Validate email and phone
                email = field_dict.get('email', '')
                phone = field_dict.get('phone', '')
                is_valid_email = validate_email_zb(email) if email else False
                is_valid_phone = validate_phone_twilio(phone) if phone else False
                
                # Create and save the lead with GPT results
                FacebookLead.objects.create(
                    user=page_connection.user,  # Associate with the page owner
                    leadgen_id=leadgen_id,
                    full_name=field_dict.get('full_name', ''),
                    email=email,
                    phone=phone,
                    message=field_dict.get('message', ''),
                    custom_fields=custom_fields,
                    gpt_score=score_result['gpt_score'],
                    gpt_reason=score_result['gpt_reason'],
                    total_score=score_result['total_score'],
                    is_spam=score_result['is_spam'],
                    is_valid_email=is_valid_email,
                    is_valid_phone=is_valid_phone
                )
                logger.info(f"Saved lead {leadgen_id} to database for user {page_connection.user.id}")
            
            return HttpResponse("Event received", status=200)
            
        except json.JSONDecodeError:
            logger.error("Invalid JSON received from Facebook webhook")
            return HttpResponse("Invalid JSON", status=400)
        except (KeyError, IndexError) as e:
            logger.error(f"Error extracting data from webhook payload: {str(e)}")
            return HttpResponse("Invalid webhook payload", status=400)

def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully!')
            return redirect('leads:dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'leads/signup.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, 'Logged in successfully!')
            return redirect('leads:dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'leads/login.html')

def logout_view(request):
    logout(request)
    messages.info(request, 'Logged out successfully!')
    return redirect('leads:homepage')

@login_required(login_url='leads:login')
def lead_dashboard(request):
    """Display a dashboard of valid and spam leads for the authenticated user."""
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
        messages.success(request, f'Successfully connected to {page_name}')
        
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
    lead.save()
    
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
    context = {
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY
    }
    return render(request, 'leads/pricing.html', context)

@login_required
def integrations_view(request):
    # Get or create the user's profile
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    context = {
        'hubspot_connected': bool(profile.hubspot_access_token),
    }
    return render(request, 'leads/integrations.html', context)

@login_required
def hubspot_connect(request):
    auth_url = (
        f"https://app.hubspot.com/oauth/authorize"
        f"?client_id={settings.HUBSPOT_CLIENT_ID}"
        f"&scope={settings.HUBSPOT_SCOPES}"
        f"&redirect_uri={settings.HUBSPOT_REDIRECT_URI}"
    )
    return redirect(auth_url)
