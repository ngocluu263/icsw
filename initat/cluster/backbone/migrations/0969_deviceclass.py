# -*- coding: utf-8 -*-
# Generated by Django 1.9.8 on 2016-07-25 13:35
from __future__ import unicode_literals

from django.conf import settings
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0968_staticassettemplatefield_hidden'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeviceClass',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(default=b'', max_length=64, unique=True)),
                ('description', models.CharField(default=b'', max_length=128)),
                ('limitations', django.contrib.postgres.fields.jsonb.JSONField(default=None, null=True)),
                ('system_class', models.BooleanField(default=False)),
                ('default_system_class', models.BooleanField(default=False)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('create_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
