from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0002_remove_gmail'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='subscription_id',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ] 