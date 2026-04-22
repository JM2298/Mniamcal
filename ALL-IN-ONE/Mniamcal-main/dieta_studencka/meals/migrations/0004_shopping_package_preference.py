from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0003_fcm_user_preference'),
    ]

    operations = [
        migrations.CreateModel(
            name='ShoppingPackagePreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rodzina_id', models.PositiveIntegerField(db_index=True)),
                ('nazwa_produktu_uproszczonego_id', models.PositiveIntegerField(db_index=True)),
                ('wielkosc_opakowania', models.FloatField()),
                ('jednostka_opakowania', models.CharField(choices=[('g', 'g'), ('ml', 'ml')], max_length=2)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'meals_shopping_package_preferences',
                'unique_together': {('rodzina_id', 'nazwa_produktu_uproszczonego_id')},
            },
        ),
    ]