# -*- coding: utf-8 -*-
# Generated by Django 1.10 on 2016-09-05 08:48
from __future__ import unicode_literals
from functools import partial
from django.db import migrations


def convert_size(apps, schema_editor, factor):
    Partition = apps.get_model("backbone", "partition")
    for partition in Partition.objects.all():
        if partition.size:
            partition.size *= factor
            partition.save()


class Migration(migrations.Migration):

    dependencies = [
        ('backbone', '0989_auto_20160905_1047'),
    ]

    operations = [
        migrations.RunPython(
            # convert from MB to byte
            partial(convert_size, factor=1024 ** 2),
            # convert from byte to MB
            partial(convert_size, factor=1024 ** -2),
        )
    ]