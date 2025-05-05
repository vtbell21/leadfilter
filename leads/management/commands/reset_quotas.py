from django.core.management.base import BaseCommand
from leads.models import UserProfile

class Command(BaseCommand):
    help = 'Reset all users\' lead_filter_count to 0 (monthly quota reset)'

    def handle(self, *args, **kwargs):
        UserProfile.objects.all().update(lead_filter_count=0)
        self.stdout.write(self.style.SUCCESS("Monthly quotas reset.")) 