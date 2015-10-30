#!/usr/bin/python-init -Ot
#
# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-client
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

""" parser for icsw command """

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

try:
    import django
    django.setup()
except:
    django = None

import argparse

from .service.service_parser import Parser as ServiceParser
from .logwatch.logwatch_parser import Parser as LogwatchParser
from .cstore.cstore_parser import Parser as CStoreParser
from .relay.relay_parser import Parser as RelayParser
from .lse.lse_parser import Parser as LseParser
from .info.info_parser import Parser as InfoParser
from initat.icsw.service.instance import InstanceXML

try:
    from .license.license_parser import Parser as LicenseParser
except ImportError:
    LicenseParser = None

try:
    from .setup.parser import Parser as SetupParser
except ImportError:
    SetupParser = None

try:
    from .device.device_parser import Parser as DeviceParser
except ImportError:
    DeviceParser = None

try:
    from .image.image_parser import Parser as ImageParser
except ImportError:
    ImageParser = None

try:
    from .job.job_parser import Parser as JobParser
except ImportError:
    JobParser = None


try:
    from .collectd.collectd_parser import Parser as CollectdParser
except ImportError:
    CollectdParser = None


try:
    from .user.user_parser import Parser as UserParser
except:
    UserParser = None


class ICSWParser(object):
    def __init__(self):
        self._parser = argparse.ArgumentParser(prog="icsw")
        self._parser.add_argument("--logger", type=str, default="stdout", choices=["stdout", "logserver"], help="choose logging facility")
        sub_parser = self._parser.add_subparsers(help="sub-command help")
        server_mode = True if django is not None else False
        inst_xml = InstanceXML(quiet=True)
        # ServiceParser().link(sub_parser)
        # LogwatchParser().link(sub_parser)
        for _sp in [
            LseParser,
            InfoParser,
            ServiceParser,
            LogwatchParser,
            LicenseParser,
            SetupParser,
            DeviceParser,
            CStoreParser,
            RelayParser,
            ImageParser,
            JobParser,
            CollectdParser,
            UserParser,
        ]:
            if _sp is not None:
                try:
                    _sp().link(
                        sub_parser,
                        server_mode=server_mode,
                        instance_xml=inst_xml,
                    )
                except TypeError:
                    # happens when switching to kwarg-expecting parsers
                    pass

    def parse_args(self):
        opt_ns = self._parser.parse_args()
        return opt_ns
