# Copyright (C) 2015 Bernhard Mallinger, init.at
#
# this file is part of md-config-server
#
# Send feedback to: <mallinger@init.at>
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
import json
# noinspection PyUnresolvedReferences
import pprint
from django.db import connection
import itertools
import memcache
import time
from initat.cluster.backbone.models import device
from initat.cluster.backbone.models.monitoring import mon_check_command
import initat.collectd.aggregate
from initat.md_config_server.icinga_log_reader.log_reader import host_service_id_util
from initat.cluster.backbone.models.kpi import KpiSelectedDeviceMonitoringCategoryTuple, Kpi
from initat.md_config_server.config.objects import global_config
from initat.md_config_server.common import live_socket
from initat.md_config_server.kpi.kpi_language import KpiObject, KpiResult, KpiSet
import logging_tools
import threading_tools


class kpi_process(threading_tools.process_obj):

    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True
        )
        connection.close()

        # TODO: possibly like this:
        # self.register_func("update_kpi", self.update)

        # self.register_timer(self.update, 30 if global_config["DEBUG"] else 300, instant=True)
        self.update()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self.__log_template.close()

    def update(self):
        return
        data = _KpiData(self.log)
        host_rrd = data.get_memcached_data()
        dev_mon_tuple_data = data.get_check_results()

        print 'kpi proc started'
        #self["run_flag"] = False
        #self["exit_requested"] = True

        # recalculate kpis


            # TODO: data extraction in own function/class
            # TODO: permissions for devices?

            pprint.pprint(dev_mon_tuples)
            # calculate kpis, such that drill down data is present

            for kpi_db in Kpi.objects.all():
                kpi_set = KpiSet(list(itertools.chain.from_iterable(
                    dev_mon_tuples[(tup.device_category_id, tup.monitoring_category_id)]
                    for tup in kpi_db.kpiselecteddevicemonitoringcategorytuple_set.all()
                )))

                print 'evaluating', kpi_db.formula, type(kpi_db.formula), ' on '
                pprint.pprint(kpi_set)
                # print eval("return {}".format(kpi_db.formula), {'data': kpi_set})
                print eval(kpi_db.formula, {'data': kpi_set})


class _KpiData(object):
    """Data retrieval methods (mostly functions actually)"""

    def __init__(self, log):
        self.log = log

    def get_memcached_data(self):
        mc = memcache.Client([global_config["MEMCACHE_ADDRESS"]])
        host_rrd_data = {}
        try:
            host_list = json.loads(mc.get("cc_hc_list"))
        except Exception as e:
            self.log(unicode(e), logging_tools.LOG_LEVEL_ERROR)
        else:

            for host_uuid, host_data in host_list.iteritems():
                if host_data[0] + 10*60 < time.time():
                    self.log("data for {} is very old ({})".format(host_data[1], time.ctime(host_data[0])))

                values_list = json.loads(mc.get("cc_hc_{}".format(host_uuid)))

                host_rrd_data[host_data[1]] = \
                    list(
                        KpiObject(
                            host_name=host_data[1],
                            rrd=initat.collectd.aggregate.ve(*val)
                        ) for val in values_list
                    )

        return host_rrd_data

    def get_check_results(self):
        kpi_objects = []

        # check db for kpi definitions
        # gather data
        try:
            icinga_socket = live_socket.get_icinga_live_socket()
        except IOError as e:
            self.log(unicode(e), logging_tools.LOG_LEVEL_ERROR)
        else:

            # get hosts and services of categories
            # get checks for kpis

            if Kpi.objects.filter(uses_all_data=True).exists():
                # TODO
                pass

            else:
                queryset = KpiSelectedDeviceMonitoringCategoryTuple.objects.all() \
                    .select_related("monitoring_category", "device_category")

            # TODO: uses_all_data
            # simulate distinct
            dev_mon_tuple_data = dict()
            print 'qs', len(queryset)
            for item in queryset:
                if not (item.device_category_id, item.monitoring_category_id) in dev_mon_tuple_data:
                    print '\n\ngather for', item.monitoring_category, 'x', item.device_category

                    devices = item.device_category.device_set.all()
                    checks = item.monitoring_category.mon_check_command_set.all()

                    print 'dev ch', checks, devices

                    def create_kpi_obj(check_result):
                        property_names = {  # icinga names with renamings (currently none used)
                                            'display_name': None,
                                            'current_attempt': None,
                                            'plugin_output': None,
                                            'last_check': None,
                                            'description': None,
                                            'state_type': None,
                                            }
                        # TODO: if state type is supposed to be used, probably parse to something more readable
                        properties = {(our_name if our_name is not None else icinga_name): check_result[icinga_name]
                                      for icinga_name, our_name in property_names.iteritems()}

                        host_pk, service_pk, info = \
                            host_service_id_util.parse_host_service_description(check_result['description'])

                        try:
                            properties['host'] = device.objects.get(pk=host_pk).full_name
                        except device.DoesNotExist:
                            properties['host'] = None

                        try:
                            properties['check_command'] = mon_check_command.objects.get(pk=service_pk).name
                        except mon_check_command.DoesNotExist:
                            properties['check_command'] = None

                        return KpiObject(
                            result=KpiResult.from_numeric_icinga_service_status(int(check_result['state'])),
                            host_name=check_result['host_name'],
                            properties=properties,
                        )

                    for dev in devices:
                        for check in checks:
                            # this works because we match services by partial matches
                            print 'gather for', dev, check

                            service_query = icinga_socket.services.columns("host_name",
                                                                           "description",
                                                                           "state",
                                                                           "last_check",
                                                                           "check_type",
                                                                           "state_type",
                                                                           "plugin_output",
                                                                           "display_name",
                                                                           "current_attempt",
                                                                           )
                            description = host_service_id_util.create_host_service_description_direct(
                                dev.pk,
                                check.pk,
                                special_check_command_pk=check.mon_check_command_special_id,
                                info=".*"
                            )
                            description = "^{}".format(description)

                            service_query.filter("description", "~", description)  # ~ means regular expression match
                            print 'fil', 'desc', description
                            icinga_result = service_query.call()
                            print('res {}'.format(icinga_result))

                            for check_result in icinga_result:
                                # can be multiple in case of special check commands
                                kpi_objects.append(create_kpi_obj(check_result))

                    dev_mon_tuple_data[(item.device_category_id, item.monitoring_category_id)] = kpi_objects

        return dev_mon_tuple_data
