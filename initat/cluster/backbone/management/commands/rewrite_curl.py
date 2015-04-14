#!/usr/bin/python-init -Otu
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" move from curl to flags """

from django.core.management.base import BaseCommand
from initat.cluster.backbone.models import device


class Command(BaseCommand):
    help = ("Migrate from curl to flags")
    args = ''

    def handle(self, **options):
        # uncomment for testing
        # DeviceLogEntry.objects.all().delete()
        _checked, _changed = (0, 0)
        for _dev in device.objects.all():
            _checked += 1
            if _dev.curl.lower().startswith("ipmi://") and not _dev.ipmi_capable:
                _changed += 1
                _dev.curl = ""
                _dev.ipmi_capable = True
                _dev.save()
        print("checked {:d} devices, changed {:d} (curl -> ipmi_capable)".format(_checked, _changed))