# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2016-09-12 06:27
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0992_logicaldisc'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfigServiceEnum',
            fields=[
                ('idx', models.AutoField(primary_key=True, serialize=False)),
                ('enum_name', models.CharField(default=b'', max_length=255, unique=True)),
                ('name', models.CharField(default=b'', max_length=255, unique=True)),
                ('info', models.TextField(blank=True, default=b'')),
                ('date', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AlterField(
            model_name='assetbatch',
            name='partition_table',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='backbone.partition_table'),
        ),
        migrations.AlterField(
            model_name='assetrun',
            name='run_type',
            field=models.IntegerField(choices=[(1, b'PACKAGE'), (2, b'HARDWARE'), (3, b'LICENSE'), (4, b'UPDATE'), (5, b'LSHW'), (6, b'PROCESS'), (7, b'PENDING_UPDATE'), (8, b'DMI'), (9, b'PCI'), (10, b'PRETTYWINHW'), (11, b'PARTITION')], default=1),
        ),
        migrations.AlterField(
            model_name='device',
            name='act_partition_table',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='act_partition_table', to='backbone.partition_table'),
        ),
        migrations.AlterField(
            model_name='device',
            name='partition_table',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='new_partition_table', to='backbone.partition_table'),
        ),
        migrations.AddField(
            model_name='config',
            name='config_service_enum',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='backbone.ConfigServiceEnum'),
        ),
    ]