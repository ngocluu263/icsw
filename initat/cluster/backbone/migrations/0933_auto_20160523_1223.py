# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-05-23 10:23
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0932_auto_20160523_1107'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='assethardwareentry',
            options={'ordering': ('idx',)},
        ),
        migrations.AddField(
            model_name='assethardwareentry',
            name='depth',
            field=models.IntegerField(default=0),
        ),
    ]
