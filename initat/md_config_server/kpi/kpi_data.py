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

import collections
import json
import time
from django.db.models import Q

import memcache
import operator
import initat.collectd
from initat.md_config_server.icinga_log_reader.log_aggregation import icinga_log_aggregator
import logging_tools
# noinspection PyUnresolvedReferences
import pprint
import initat.collectd.aggregate

from initat.cluster.backbone.models import device, mon_check_command, Kpi, KpiDataSourceTuple, category, duration
from initat.md_config_server.common import live_socket
from initat.md_config_server.config.objects import global_config
from initat.md_config_server.icinga_log_reader.log_reader import host_service_id_util
from initat.md_config_server.kpi.kpi_language import KpiObject, KpiResult, KpiRRDObject, KpiServiceObject
from initat.md_config_server.kpi.kpi_utils import KpiUtils


class KpiData(object):
    """Data retrieval methods (mostly functions actually)"""

    def __init__(self, log):
        self.log = log

        try:
            self.icinga_socket = live_socket.get_icinga_live_socket()
        except IOError as e:
            self.log(u"error when opening icinga socket: {}".format(e), logging_tools.LOG_LEVEL_ERROR)
            raise

        host_rrd_data = self._get_memcached_data()

        self.log("got rrd_data for {} hosts".format(len(host_rrd_data)))

        if Kpi.objects.filter(uses_all_data=True).exists():
            # self.kpi_device_categories = set(device.categories_set.all())
            # self.kpi_devices = list(device.objects.all())
            # self.kpi_mon_categories = list(mon_check_command.categories_set.all())

            dev_mon_tuples = self._get_dev_mon_tuples_from_category_tuples(
                [
                    KpiDataSourceTuple(kpi=None, device_category=dev_cat, monitoring_category=mon_cat)
                    for dev_cat in category.objects.get_device_categories()
                    for mon_cat in category.objects.get_monitoring_categories()
                ]
            )

        else:
            # self.kpi_device_categories = set(tup.device_category_id for tup in KpiDataSourceTuple.objects.all())

            # self.kpi_devices = set(device.objects.filter(categories__in=self.kpi_device_categories))

            # self.kpi_mon_categories = set(tup.monitoring_category_id for tup in KpiDataSourceTuple.objects.all())

            # self.kpi_mon_check_commands = set(mon_check_command.objects.filter(categories__in=self.kpi_mon_categories))

            dev_mon_tuples = self._get_dev_mon_tuples_from_category_tuples(
                KpiDataSourceTuple.objects.all().prefetch_related("device_category")
            )

        # this is merely internal to this class
        HostData = collections.namedtuple('HostData', ('rrd_data', 'host_check_results', 'service_check_results'))
        self.host_data = {}

        service_check_results = collections.defaultdict(lambda: {})
        for dev, mcc in dev_mon_tuples:

            service_check_results[dev.pk][mcc.pk] = self._get_service_check_results(dev, mcc)

        for dev in {dev for (dev, _) in dev_mon_tuples}:
            self.host_data[dev.pk] = HostData(rrd_data=host_rrd_data.get(dev.pk, None),
                                              host_check_results=self._get_host_check_results(dev),
                                              service_check_results=service_check_results[dev.pk])

    def get_data_for_kpi(self, kpi_db):
        dev_mon_tuples = kpi_db.kpidatasourcetuple_set.all()

        if kpi_db.has_historic_data():
            start, end = KpiUtils.parse_kpi_time_range_from_kpi(kpi_db)
        else:
            start, end = None, None

        return self.get_data_for_dev_mon_tuples(dev_mon_tuples, start, end)

    def get_data_for_dev_mon_tuples(self, tuples, start=None, end=None):
        """
        Retrieves current results for (dev, mon)
        :rtype: list of KpiObject
        """
        # NOTE: only used through get_data_for_kpi as of now
        kpi_objects = []
        dev_mon_tuples = self._get_dev_mon_tuples_from_category_tuples(tuples)

        device_id_set = {dev for (dev, _) in dev_mon_tuples}

        if start is not None:

            timespan_hosts_qs, timespan_services_qs =\
                icinga_log_aggregator.get_active_hosts_and_services_in_timespan_queryset(start, end)

            timespan_hosts_qs = timespan_hosts_qs.filter(device_id__in=device_id_set)

            timespan_services_qs = timespan_services_qs.filter(
                reduce(operator.or_, (Q(device_id=dev_id, service_id=mcc.pk) for (dev_id, mcc) in dev_mon_tuples))
            )

            # TODO: add those timespan/hosts data which don't have current sets
            # possibly use set hashing for somewhat reasonable approach (OR NOT, can there reasonable be more than a million dev/mon tuples?)

        for dev in device_id_set:
            if self.host_data[dev.pk].rrd_data is not None:
                kpi_objects.extend(self.host_data[dev.pk].rrd_data)
            kpi_objects.extend(
                self.host_data[dev.pk].host_check_results
            )
        for dev, mcc in dev_mon_tuples:
            kpi_objects.extend(
                self.host_data[dev.pk].service_check_results[mcc.pk]
            )
        return kpi_objects

    def _get_dev_mon_tuples_from_category_tuples(self, queryset):
        queryset = queryset.prefetch_related('device_category', 'device_category__device_set')
        queryset = queryset.prefetch_related('monitoring_category', 'monitoring_category__mon_check_command_set')
        dev_mon_tuples = set()
        for tup in queryset:
            for dev in tup.device_category.device_set.all():
                for mcc in tup.monitoring_category.mon_check_command_set.all():
                    if (dev, mcc) not in dev_mon_tuples:
                        dev_mon_tuples.add((dev, mcc))

        return dev_mon_tuples

    def _get_memcached_data(self):

        device_full_names = {entry.full_name: entry for entry in device.objects.all().prefetch_related('domain_tree_node')}

        mc = memcache.Client([global_config["MEMCACHE_ADDRESS"]])
        host_rrd_data = {}
        try:
            host_list_mc = mc.get("cc_hc_list")
            if host_list_mc is None:
                raise Exception("host list is None")
        except Exception as e:
            self.log(u"error when loading memcache host list: {}".format(e), logging_tools.LOG_LEVEL_ERROR)
        else:
            host_list = json.loads(host_list_mc)

            for host_uuid, host_data in host_list.iteritems():
                try:
                    host_db = device_full_names[host_data[1]]
                except KeyError:
                    self.log(u"device {} does not exist but is referenced in rrd data".format(host_data[1]),
                             logging_tools.LOG_LEVEL_WARN)
                else:
                    if (host_data[0] + 60 * 60) < time.time():
                        self.log(u"data for {} is very old ({})".format(host_data[1], time.ctime(host_data[0])))

                    host_mc = mc.get("cc_hc_{}".format(host_uuid))
                    if host_mc is not None:
                        values_list = json.loads(host_mc)

                        vector_entries = (initat.collectd.aggregate.ve(*val) for val in values_list)

                        host_rrd_data[host_db.pk] = list(
                            KpiRRDObject(
                                host_name=host_data[1],
                                host_pk=host_db.pk,
                                rrd_key=ve.key,
                                rrd_value=ve.get_value(),
                            ) for ve in vector_entries
                        )
                    else:
                        self.log(u"no memcache data for {} ({})".format(host_data[1], host_uuid))

        return host_rrd_data

    def _get_service_check_results(self, dev, check):
        service_query = self.icinga_socket.services.columns(
            # "host_name",
            "description",
            "state",
            # "last_check",
            # "check_type",
            # "state_type",
            # "last_state_change",
            # "plugin_output",
            # "display_name",
            # "current_attempt",
        )
        description = host_service_id_util.create_host_service_description_direct(
            dev.pk,
            check.pk,
            special_check_command_pk=check.mon_check_command_special_id,
            info=".*"
        )
        description = "^{}".format(description)  # need regex to force start to distinguish s_host_check and host_check

        service_query.filter("description", "~", description)  # ~ means regular expression match
        icinga_result = service_query.call()

        ret = []
        # this is usually only one except in case of special check commands
        for ir in icinga_result:
            try:
                service_info = host_service_id_util.parse_host_service_description(ir['description'])[2]
            except IndexError:
                service_info = None
            ret.append(
                KpiServiceObject(
                    result=KpiResult.from_numeric_icinga_service_status(int(ir['state'])),
                    host_name=dev.full_name,
                    host_pk=dev.pk,
                    service_id=check.pk,
                    service_info=service_info,
                )
            )
        # self.log("got service check results: {}".format(ret))
        return ret

    def _get_host_check_results(self, dev):
        host_query = self.icinga_socket.hosts.columns(
            "host_name",
            "state",
            # "address",
            # "last_check",
            # "check_type",
            # "state_type",
            # "last_state_change",
            # "plugin_output",
            # "display_name",
            # "current_attempt",
        )
        host_query.filter("host_name", "~", dev.name)
        icinga_result = host_query.call()

        ret = list(
            KpiObject(
                result=KpiResult.from_numeric_icinga_service_status(int(ir['state'])),
                host_name=dev.full_name,
                host_pk=dev.pk,
            )
            for ir in icinga_result
        )

        # self.log("got host check results: {}".format(ret))
        return ret

