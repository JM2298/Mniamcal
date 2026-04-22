from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0004_shopping_package_preference'),
    ]

    operations = [
        migrations.AddField(
            model_name='fcmuserpreference',
            name='shopping_package_size_enabled',
            field=models.BooleanField(default=True),
        ),
    ]
