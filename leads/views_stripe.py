import stripe
from django.conf import settings
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

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