# -*- coding: utf-8 -*-
# Generated by Django 1.9.8 on 2016-07-21 16:53
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0967_category_asset'),
    ]

    operations = [
        migrations.AddField(
            model_name='staticassettemplatefield',
            name='hidden',
            field=models.BooleanField(default=False),
        ),
    ]
