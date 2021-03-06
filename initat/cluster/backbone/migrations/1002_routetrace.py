# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2016-09-27 06:13
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '1001_hardwarefingerprint_changecount'),
    ]

    operations = [
        migrations.CreateModel(
            name='RouteTrace',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('session_id', models.CharField(default=b'', max_length=64)),
                ('user_id', models.IntegerField(default=0)),
                ('from_name', models.CharField(max_length=64)),
                ('to_name', models.CharField(max_length=64)),
                ('created', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
