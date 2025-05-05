from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0004_add_timestamps'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='leadroutingsettings',
            name='spam_labeling_enabled',
        ),
        migrations.RemoveField(
            model_name='leadroutingsettings',
            name='good_lead_subject',
        ),
        migrations.RemoveField(
            model_name='leadroutingsettings',
            name='spam_lead_subject',
        ),
        migrations.AddField(
            model_name='leadroutingsettings',
            name='send_non_spam_to_inbox',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='leadroutingsettings',
            name='send_spam_to_inbox',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='leadroutingsettings',
            name='non_spam_subject',
            field=models.CharField(default='✅ New Qualified Lead', max_length=100),
        ),
        migrations.AddField(
            model_name='leadroutingsettings',
            name='spam_subject',
            field=models.CharField(default='🚫 New Spam Lead Detected', max_length=100),
        ),
        migrations.AddField(
            model_name='leadroutingsettings',
            name='notification_email',
            field=models.EmailField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='leadroutingsettings',
            name='user',
            field=models.OneToOneField(on_delete=models.CASCADE, related_name='lead_routing_settings', to='auth.user'),
        ),
    ] 