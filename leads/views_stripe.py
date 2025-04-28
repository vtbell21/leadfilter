import stripe
from django.conf import settings
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

stripe.api_key = settings.STRIPE_SECRET_KEY

@csrf_exempt
def create_checkout_session(request):
    if request.method == 'POST':
        price_id = request.POST.get('price_id')
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url='https://yourdomain.com/success/',
            cancel_url='https://yourdomain.com/cancel/',
        )
        return JsonResponse({'id': session.id})
    return JsonResponse({'error': 'Invalid request'}, status=400) 