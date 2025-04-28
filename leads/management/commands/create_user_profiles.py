from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from leads.models import UserProfile

class Command(BaseCommand):
    help = 'Creates user profiles for users that do not have one'

    def handle(self, *args, **kwargs):
        users = User.objects.all()
        created_count = 0
        
        for user in users:
            profile, created = UserProfile.objects.get_or_create(user=user)
            if created:
                created_count += 1
                self.stdout.write(f'Created profile for user {user.username}')
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {created_count} user profiles')) 