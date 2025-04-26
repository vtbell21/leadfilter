from django.core.management.base import BaseCommand
from leads.models import FacebookLead
from django.utils import timezone

class Command(BaseCommand):
    help = 'Creates sample leads for testing'

    def handle(self, *args, **kwargs):
        # Create valid leads
        FacebookLead.objects.create(
            leadgen_id='123456789',
            full_name='John Smith',
            email='john.smith@gmail.com',
            phone='+1234567890',
            message='I am interested in purchasing a new vehicle. Please contact me with more information about your current inventory.',
            custom_fields={
                'vehicle_type': 'SUV',
                'preferred_brand': 'Toyota',
                'budget_range': '$30,000 - $40,000',
                'preferred_contact_time': 'Evening'
            },
            gpt_score=0.2,
            gpt_reason='Valid name format, legitimate email domain, proper phone format, coherent message with specific details',
            total_score=0.2,
            is_spam=False,
            is_valid_email=True,
            is_valid_phone=True,
            received_at=timezone.now()
        )

        FacebookLead.objects.create(
            leadgen_id='987654321',
            full_name='Sarah Johnson',
            email='sarah.j@outlook.com',
            phone='+1987654321',
            message='Looking for a certified pre-owned sedan with low mileage. Available for test drive this weekend.',
            custom_fields={
                'vehicle_type': 'Sedan',
                'mileage_preference': 'Under 50,000',
                'financing_needed': 'Yes',
                'trade_in_available': 'Yes',
                'current_vehicle': '2018 Honda Civic'
            },
            gpt_score=0.3,
            gpt_reason='Valid name and contact details, professional email format, detailed and specific inquiry',
            total_score=0.3,
            is_spam=False,
            is_valid_email=True,
            is_valid_phone=True,
            received_at=timezone.now()
        )

        # Create spam leads
        FacebookLead.objects.create(
            leadgen_id='111222333',
            full_name='Test User',
            email='test@test.com',
            phone='123',
            message='URGENT!!! Best deals on cars!!! Contact immediately for amazing offer!!!',
            custom_fields={
                'vehicle_type': 'ANY',
                'price': 'BEST PRICE!!!',
                'urgent': 'YES!!!',
                'spam_indicator': 'high'
            },
            gpt_score=0.9,
            gpt_reason='Test name, suspicious email domain, invalid phone format, excessive punctuation and urgency in message',
            total_score=0.9,
            is_spam=True,
            is_valid_email=False,
            is_valid_phone=False,
            received_at=timezone.now()
        )

        FacebookLead.objects.create(
            leadgen_id='444555666',
            full_name='Spam Bot',
            email='spam@example.com',
            phone='invalid',
            message='Buy car now! Best price guaranteed! Click here >>> http://suspicious-link.com',
            custom_fields={
                'click_here': 'http://suspicious-link.com',
                'offer_type': 'AMAZING DEAL!!!',
                'discount': '90% OFF!!!',
                'spam_indicator': 'very_high'
            },
            gpt_score=0.95,
            gpt_reason='Bot-like name, example domain, non-numeric phone, suspicious links in message, spam-like custom fields',
            total_score=0.95,
            is_spam=True,
            is_valid_email=False,
            is_valid_phone=False,
            received_at=timezone.now()
        )

        self.stdout.write(self.style.SUCCESS('Successfully created sample leads')) 