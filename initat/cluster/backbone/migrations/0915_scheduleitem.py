# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-05-06 10:41
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0914_merge'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScheduleItem',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('source', models.IntegerField(choices=[(1, b'SNMP'), (2, b'ASU'), (3, b'IPMI'), (4, b'PACKAGE'), (5, b'HARDWARE'), (6, b'LICENSE'), (7, b'UPDATE'), (8, b'SOFTWARE_VERSION'), (9, b'PROCESS'), (10, b'PENDING_UPDATE')])),
                ('planned_date', models.DateTimeField(default=None, null=True)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='backbone.device')),
            ],
        ),
    ]