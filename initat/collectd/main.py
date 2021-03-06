# Copyright (C) 2014-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file belongs to the collectd-init package
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
""" main part of collectd-init """

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

import django
django.setup()

from initat.collectd.config import global_config
from initat.tools import configfile, process_tools
import time


def kill_previous():
    # check for already running rrdcached processes and kill them
    proc_dict = process_tools.get_proc_list(proc_name_list=["rrdcached", "collectd"])
    if proc_dict:
        for _key in proc_dict.iterkeys():
            try:
                os.kill(_key, 15)
            except:
                pass
        time.sleep(0.5)
        for _key in proc_dict.iterkeys():
            try:
                os.kill(_key, 9)
            except:
                pass


def main():
    global_config.add_config_entries(
        [
            ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
            ("VERBOSE", configfile.int_c_var(0, help_string="verbose lewel [%(default)s]", only_commandline=True)),
            ("VERBOSE", configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
            ("RRD_DIR", configfile.str_c_var("/var/cache/rrd", help_string="directory of rrd-files on local disc", database=True)),
            ("RRD_CACHED_DIR", configfile.str_c_var("/var/run/rrdcached", database=True)),
            ("RRD_CACHED_SOCKET", configfile.str_c_var("/var/run/rrdcached/rrdcached.sock", database=True)),
            ("RRD_STEP", configfile.int_c_var(60, help_string="RRD step value", database=True)),
            ("AGGREGATE_DIR", configfile.str_c_var("/opt/cluster/share/collectd", help_string="base dir for collectd aggregates")),
        ]
    )
    kill_previous()
    # late load after population of global_config
    from initat.collectd.server import server_process
    server_process().loop()
    os._exit(0)
