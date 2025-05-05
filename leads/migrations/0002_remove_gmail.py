from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='leadroutingsettings',
            name='send_to_gmail',
        ),
        migrations.DeleteModel(
            name='GmailCredentials',
        ),
    ] 