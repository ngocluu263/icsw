# -*- coding: utf-8 -*-
# Generated by Django 1.10 on 2016-08-11 06:40
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0974_auto_20160810_1606'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='staticassettemplatefield',
            options={'ordering': ['ordering']},
        ),
        migrations.AddField(
            model_name='staticassettemplatefield',
            name='ordering',
            field=models.IntegerField(default=0),
        ),
    ]
