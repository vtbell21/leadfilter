from django.core.management.base import BaseCommand
from django.db import connections, connection
from django.conf import settings
import dj_database_url
import os

class Command(BaseCommand):
    help = 'Check which migrations are applied in the database'

    def add_arguments(self, parser):
        parser.add_argument('--database-url', type=str, help='Database URL to check')

    def handle(self, *args, **options):
        if options['database_url']:
            # Temporarily override the default database
            old_default_db = settings.DATABASES['default']
            settings.DATABASES['temp_db'] = dj_database_url.parse(options['database_url'])
            connection_name = 'temp_db'
        else:
            connection_name = 'default'

        try:
            with connections[connection_name].cursor() as cursor:
                cursor.execute("""
                    SELECT app, name 
                    FROM django_migrations 
                    WHERE app = 'leads' 
                    ORDER BY id;
                """)
                rows = cursor.fetchall()
                for row in rows:
                    self.stdout.write(f"{row[0]}.{row[1]}")
        finally:
            if options['database_url']:
                # Restore the original database settings
                settings.DATABASES.pop('temp_db')
                settings.DATABASES['default'] = old_default_db 