import os
import sys
import django
import dj_database_url
import shutil
from django.db import connections
from django.conf import settings
from django.core.management import call_command

def reset_migrations(database_url):
    # Configure Django settings
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()
    
    # Override database configuration
    settings.DATABASES['default'] = dj_database_url.parse(database_url)
    
    # Reset database
    with connections['default'].cursor() as cursor:
        # Drop all leads tables
        cursor.execute("""
            DROP TABLE IF EXISTS leads_facebooklead CASCADE;
            DROP TABLE IF EXISTS leads_facebookpageconnection CASCADE;
            DROP TABLE IF EXISTS leads_gmailcredentials CASCADE;
            DROP TABLE IF EXISTS leads_leadroutingsettings CASCADE;
            DROP TABLE IF EXISTS leads_userprofile CASCADE;
            DROP TABLE IF EXISTS leads_webhooksettings CASCADE;
            DELETE FROM django_migrations WHERE app = 'leads';
        """)
        print("Successfully reset database tables and migration history.")

    # Clean up migration files
    migrations_dir = os.path.join('leads', 'migrations')
    for filename in os.listdir(migrations_dir):
        if filename != '__init__.py':
            file_path = os.path.join(migrations_dir, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
    print("Successfully cleaned up migration files.")

    # Create fresh migration
    call_command('makemigrations', 'leads')
    print("Successfully created fresh migration.")

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python reset_migrations.py <database_url>")
        sys.exit(1)
    
    database_url = sys.argv[1]
    reset_migrations(database_url) 