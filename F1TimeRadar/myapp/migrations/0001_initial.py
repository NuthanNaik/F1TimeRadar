# Generated by Django 4.2.13 on 2024-06-27 13:41

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Time',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('master_time', models.DateTimeField(default=datetime.datetime(2024, 6, 27, 19, 11, 2, 423147))),
                ('master_delay', models.DateTimeField()),
            ],
        ),
    ]
