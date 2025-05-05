from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Check which migrations are applied in the database'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT app, name 
                FROM django_migrations 
                WHERE app = 'leads' 
                ORDER BY id;
            """)
            rows = cursor.fetchall()
            for row in rows:
                self.stdout.write(f"{row[0]}.{row[1]}") 