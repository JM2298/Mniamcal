from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0002_fcm_device_tokens'),
    ]

    operations = [
        migrations.CreateModel(
            name='FcmUserPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('push_enabled', models.BooleanField(default=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='fcm_preference', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'meals_fcm_user_preferences',
            },
        ),
    ]
