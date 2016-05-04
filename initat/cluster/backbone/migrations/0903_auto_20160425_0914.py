# -*- coding: utf-8 -*-
# Generated by Django 1.9.5 on 2016-04-25 07:14
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0902_auto_20160422_0958'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dispatchsetting',
            name='source',
            field=models.IntegerField(choices=[(1, b'SNMP'), (2, b'ASU'), (3, b'IPMI'), (4, b'NRPE')]),
        ),
        migrations.AlterField(
            model_name='scanhistory',
            name='source',
            field=models.IntegerField(choices=[(1, b'SNMP'), (2, b'ASU'), (3, b'IPMI'), (4, b'NRPE')]),
        ),
    ]