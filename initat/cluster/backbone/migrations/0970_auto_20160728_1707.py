# -*- coding: utf-8 -*-
# Generated by Django 1.9.8 on 2016-07-28 15:07
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0969_auto_20160728_1328'),
    ]

    operations = [
        migrations.AlterField(
            model_name='deviceclass',
            name='limitations',
            field=models.TextField(default=b'', null=True),
        ),
    ]
