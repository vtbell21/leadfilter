import stripe
from django.conf import settings
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.contrib.auth.models import User
from leads.models import UserProfile
from django.contrib import messages

stripe.api_key = settings.STRIPE_SECRET_KEY

@login_required
@csrf_exempt
def create_checkout_session(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    try:
        price_id = request.POST.get('price_id')
        if not price_id:
            return JsonResponse({'error': 'Price ID is required'}, status=400)

        # Get the domain from the request
        domain = request.build_absolute_uri('/').rstrip('/')
        
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=f"{domain}{reverse('leads:subscription_success')}",
            cancel_url=f"{domain}{reverse('leads:subscription_cancel')}",
            customer_email=request.user.email,  # Pre-fill customer email
        )
        return JsonResponse({'id': session.id})
    except stripe.error.StripeError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': 'An unexpected error occurred'}, status=500)

@login_required
def subscription_success(request):
    return render(request, 'leads/subscription_success.html')

@login_required
def subscription_cancel(request):
    return render(request, 'leads/subscription_cancel.html')

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        return HttpResponse(status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        customer_email = session.get('customer_email')
        subscription_id = session.get('subscription')
        customer_id = session.get('customer')
        user = User.objects.filter(email=customer_email).first()
        if user:
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.stripe_subscription_id = subscription_id
            profile.stripe_customer_id = customer_id
            profile.subscription_status = 'active'
            price_id = None
            if 'display_items' in session and session['display_items']:
                price_id = session['display_items'][0]['price']['id']
            elif 'items' in session and session['items']['data']:
                price_id = session['items']['data'][0]['price']['id']
            elif 'line_items' in session and session['line_items']['data']:
                price_id = session['line_items']['data'][0]['price']['id']
            if price_id == 'price_1RIgLWDEGQhWV7HFHPDbJOX8':
                profile.lead_filter_quota = 100
            elif price_id == 'price_1RIgLWDEGQhWV7HFHPDbJOX9':
                profile.lead_filter_quota = 500
            elif price_id == 'price_1RIgLWDEGQhWV7HFHPDbJOX0':
                profile.lead_filter_quota = 999999
            profile.save()

    elif event['type'] in ['invoice.payment_failed', 'customer.subscription.deleted']:
        subscription = event['data']['object']
        customer_id = subscription.get('customer')
        profile = UserProfile.objects.filter(stripe_customer_id=customer_id).first()
        if profile:
            profile.subscription_status = 'inactive'
            profile.save()

    return HttpResponse(status=200)

@login_required
def cancel_subscription(request):
    try:
        profile = request.user.profile
        if profile.stripe_subscription_id:
            stripe.Subscription.delete(profile.stripe_subscription_id)
            profile.subscription_status = 'inactive'
            profile.save()
            messages.success(request, 'Subscription canceled successfully.')
        else:
            messages.warning(request, 'No active subscription found.')
    except Exception as e:
        messages.error(request, f'Error canceling subscription: {e}')
    return redirect('leads:dashboard') 