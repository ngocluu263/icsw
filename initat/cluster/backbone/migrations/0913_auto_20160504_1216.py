# -*- coding: utf-8 -*-
# Generated by Django 1.9.5 on 2016-05-04 10:16
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0912_merge'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dispatchsetting',
            name='source',
            field=models.IntegerField(choices=[(1, b'SNMP'), (2, b'ASU'), (3, b'IPMI'), (4, b'PACKAGE'), (5, b'HARDWARE'), (6, b'LICENSE'), (7, b'UPDATE'), (8, b'SOFTWARE_VERSION'), (9, b'PROCESS'), (10, b'PENDING_UPDATE')]),
        ),
        migrations.AlterField(
            model_name='scanhistory',
            name='source',
            field=models.IntegerField(choices=[(1, b'SNMP'), (2, b'ASU'), (3, b'IPMI'), (4, b'PACKAGE'), (5, b'HARDWARE'), (6, b'LICENSE'), (7, b'UPDATE'), (8, b'SOFTWARE_VERSION'), (9, b'PROCESS'), (10, b'PENDING_UPDATE')]),
        ),
    ]