# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2016-09-27 07:07
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '1002_routetrace'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='assetbatch',
            name='num_completed',
        ),
        migrations.RemoveField(
            model_name='assetbatch',
            name='num_runs',
        ),
        migrations.RemoveField(
            model_name='assetbatch',
            name='num_runs_error',
        ),
        migrations.RemoveField(
            model_name='assetbatch',
            name='num_runs_ok',
        ),
        migrations.RemoveField(
            model_name='assetbatch',
            name='partitions',
        ),
        migrations.RemoveField(
            model_name='assetbatch',
            name='run_result',
        ),
        migrations.RemoveField(
            model_name='assetbatch',
            name='run_time',
        ),
        migrations.AlterField(
            model_name='assetbatch',
            name='run_status',
            field=models.IntegerField(choices=[(1, b'PLANNED'), (2, b'RUNNING'), (3, b'FINISHED_RUNS'), (4, b'GENERATING_ASSETS'), (5, b'FINISHED')], default=1),
        ),
        migrations.AlterField(
            model_name='assetrun',
            name='run_status',
            field=models.IntegerField(choices=[(1, b'PLANNED'), (2, b'SCANNING'), (3, b'FINISHED_SCANNING'), (4, b'GENERATING_ASSETS'), (5, b'FINISHED')], default=1),
        ),
    ]