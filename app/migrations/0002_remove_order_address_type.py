# Generated by Django 5.0.6 on 2025-06-30 13:53

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='order',
            name='address_type',
        ),
    ]
