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

import logging_tools
import datetime
import itertools
import pprint  # @UnusedImport
from collections import defaultdict

from django.db.models.query_utils import Q

from initat.md_config_server.config import global_config
from initat.cluster.backbone.models.monitoring import mon_check_command,\
    mon_icinga_log_raw_host_alert_data, mon_icinga_log_raw_service_alert_data, mon_icinga_log_file,\
    mon_icinga_log_last_read, mon_icinga_log_raw_service_flapping_data,\
    mon_icinga_log_raw_service_notification_data,\
    mon_icinga_log_raw_host_notification_data, mon_icinga_log_raw_host_flapping_data, mon_icinga_log_aggregated_host_data,\
    mon_icinga_log_aggregated_host_data, mon_icinga_log_aggregated_timespan, mon_icinga_log_raw_base,\
    mon_icinga_log_aggregated_service_data
from initat.cluster.backbone.models import duration
from initat.cluster.backbone.models.functions import cluster_timezone
from django.db import connection
from django.db.models.aggregates import Max

__all__ = [
]


# itertools recipe
def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = itertools.tee(iterable)
    next(b, None)
    return itertools.izip(a, b)


class icinga_log_aggregator(object):
    def __init__(self, log):
        self.log = log

    def update(self):

        relevant_serv_alerts = mon_icinga_log_raw_service_alert_data.objects.filter(device_independent=False)
        self._serv_alert_keys_cache = relevant_serv_alerts.values_list("device", "service", "service_info").distinct()


        for duration_type in (duration.Day, duration.Week, duration.Month, duration.Year):
        #for duration_type in (duration.Day,):
            self.log("updating icinga log aggregates for {}".format(duration_type.__name__))
            # hosts
            try:
                last_entry = mon_icinga_log_aggregated_timespan.objects.filter(duration_type=duration_type.ID).latest("start_date")
                next_start_time = last_entry.end_date
                self.log("last icinga aggregated entry for {} from {} to {}".format(duration_type.__name__, last_entry.start_date, last_entry.end_date))
            except mon_icinga_log_aggregated_timespan.DoesNotExist:
                earliest_date1 = mon_icinga_log_raw_host_alert_data.objects.earliest("date").date
                earliest_date2 = mon_icinga_log_raw_service_alert_data.objects.earliest("date").date
                earliest_date = min(earliest_date1, earliest_date2)
                next_start_time = duration_type.get_time_frame_start(earliest_date)
                self.log("no archive data for duration type {}, starting new data at {}".format(duration_type.__name__, next_start_time))

            do_loop = True
            i = 0
            while do_loop:
                i+=1
                if i == 4:
                    #return
                    pass
                next_end_time = duration_type.get_end_time_for_start(next_start_time)
                last_read_obj = mon_icinga_log_last_read.objects.get_last_read()  # @UndefinedVariable
                if last_read_obj and next_end_time < datetime.datetime.fromtimestamp(last_read_obj.timestamp, cluster_timezone):  # have sufficient data
                    self.log("creating entry for {} starting at {}".format(duration_type.__name__, next_start_time))
                    self._create_timespan_entry(next_start_time, next_end_time, duration_type)
                else:
                    self.log("not sufficient data for entry from {} to {}".format(next_start_time, next_end_time))
                    do_loop = False

                next_start_time = next_end_time

            #pprint.pprint(sorted(connection.queries, key=lambda x:x['time']))
            #import pdb; pdb.set_trace()

    def _create_timespan_entry(self, start_time, end_time, duration_type):
        timespan_seconds = (end_time - start_time).total_seconds()

        timespan_db = mon_icinga_log_aggregated_timespan.objects.create(
            start_date=start_time,
            end_date=end_time,
            duration=(end_time-start_time).total_seconds(),
            duration_type=duration_type.ID,
        )

        # get flappings of timespan (can't use db in inner loop)
        def preprocess_flapping_data(flapping_model, key_fun):
            cache = defaultdict(lambda: [])  # this is sorted by time
            aux_start_times = {}
            for flap_data in mon_icinga_log_raw_service_flapping_data.objects.filter().order_by('date'):
                key = key_fun(flap_data)
                if key not in aux_start_times and flap_data.flapping_state == mon_icinga_log_raw_base.FLAPPING_START:
                    # proper start
                    if flap_data.date <= end_time:  # discard newer flappings
                        aux_start_times[key] = flap_data.date
                if key in aux_start_times and flap_data.flapping_state == mon_icinga_log_raw_base.FLAPPING_STOP:
                    # a proper stop
                    start_date = aux_start_times.pop(key)
                    if flap_data.date >= start_time:  # only use flappings which are in this timespan
                        cache[key].append((start_date, flap_data.date))
            return dict(cache)  # make into regular dict
        service_flapping_cache = preprocess_flapping_data(mon_icinga_log_raw_service_flapping_data,
                                                          lambda flap_data: (flap_data.device_id, flap_data.service_id, flap_data.service_info))
        host_flapping_cache = preprocess_flapping_data(mon_icinga_log_raw_host_flapping_data,
                                                       lambda flap_data: flap_data.device_id)

        def calc_service_alert_cache():
            try:
                latest_dev_independent_service_alert = mon_icinga_log_raw_service_alert_data.objects\
                    .filter(date__lte=start_time, device_independent=True).latest('date')
            except mon_icinga_log_raw_service_alert_data.DoesNotExist:
                latest_dev_independent_service_alert = None

            # get last service alert of each service before the start time
            last_service_alert_cache = {}
            for data in mon_icinga_log_raw_service_alert_data.objects\
                    .filter(date__lte=start_time, device_independent=False)\
                    .values("device_id", "service_id", "service_info", "state", "state_type")\
                    .annotate(max_date=Max('date')):
                # prefer latest info if there is dev independent one
                if latest_dev_independent_service_alert and latest_dev_independent_service_alert.date > data['max_date']:
                    state, state_type = latest_dev_independent_service_alert.state, latest_dev_independent_service_alert.state_type
                else:
                    state, state_type = data['state'], data['state_type']
                key = data['device_id'], data['service_id'], data['service_info']

                # the query above is not perfect, it should group only by device and service 
                # this seems to be hard in django: http://stackoverflow.com/questions/19923877/django-orm-get-latest-for-each-group
                # so we do the last grouping by this key here manually
                if key not in last_service_alert_cache or last_service_alert_cache[key][1] < data['max_date']:
                    last_service_alert_cache[key] = (state, state_type), data['max_date']
            return last_service_alert_cache
        last_service_alert_cache = calc_service_alert_cache()

        # regular changes in time span
        def calc_weighted_states(relevant_entries, state_description_before):
            weighted_states = defaultdict(lambda: 0.0)
            for raw_entry1, raw_entry2 in pairwise(relevant_entries):
                entry_timespan_seconds = (raw_entry2.date - raw_entry1.date).total_seconds()
                entry_weight = entry_timespan_seconds / timespan_seconds

                weighted_states[(raw_entry1.state, raw_entry1.state_type)] += entry_weight

            # first/last
            if not relevant_entries:
                # always state before
                weighted_states[state_description_before] += 1.0
            else:
                # at least one entry
                # first
                first_entry_timespan_seconds = (relevant_entries[0].date - start_time).total_seconds()
                first_entry_weight = first_entry_timespan_seconds / timespan_seconds

                weighted_states[state_description_before] += first_entry_weight

                # last
                last_entry = relevant_entries[len(relevant_entries)-1]
                last_entry_timespan_seconds = (end_time - last_entry.date).total_seconds()
                last_entry_weight = last_entry_timespan_seconds / timespan_seconds

                weighted_states[(last_entry.state, last_entry.state_type)] += last_entry_weight
            return weighted_states

        # flapping
        # check if we start in flapping state
        def calc_flapping_ratio(cache, key):
            flapping_seconds = 0.0
            for flapping in cache.get(key, []):
                flap_start = max(flapping[0], start_time)
                flap_end = min(flapping[1], end_time)
                flapping_seconds += (flap_end - flap_start).total_seconds()
            return flapping_seconds / timespan_seconds

        def process_service_alerts():
            service_db_rows = []
            # don't consider alerts for any machine, they are added below
            for device_id, service_id, service_info in self._serv_alert_keys_cache:
                # need to find last state
                service_db_identification = Q(device=device_id, service=service_id, service_info=service_info)
                service_db_identification_w_downtime = service_db_identification | Q(device_independent=True)

                state_description_before = last_service_alert_cache.get((device_id, service_id, service_info), (None, None))[0]
                if not state_description_before:
                    state_description_before = mon_icinga_log_raw_base.STATE_UNDETERMINED, mon_icinga_log_raw_base.STATE_UNDETERMINED

                relevant_entries = mon_icinga_log_raw_service_alert_data.objects.filter(service_db_identification_w_downtime, date__range=(start_time, end_time)).order_by('date')
                weighted_states = calc_weighted_states(relevant_entries, state_description_before)

                flapping_ratio = calc_flapping_ratio(service_flapping_cache, (device_id, service_id, service_info))
                if flapping_ratio != 0.0:
                    weighted_states[(mon_icinga_log_aggregated_service_data.STATE_FLAPPING, mon_icinga_log_aggregated_service_data.STATE_FLAPPING)] = flapping_ratio

                for ((state, state_type), value) in weighted_states.iteritems():
                    service_db_rows.append(
                        mon_icinga_log_aggregated_service_data(
                            state=state,
                            state_type=state_type,
                            value=value,
                            timespan=timespan_db,
                            device_id=device_id,
                            service_id=service_id,
                            service_info=service_info,
                        )
                    )

                essential_weighted_states = sum(val for (state, state_type), val in weighted_states.iteritems() if state != mon_icinga_log_aggregated_service_data.STATE_FLAPPING)
                if abs(essential_weighted_states-1.0) > 0.01:
                    self.log("missing icinga log entries for device {} between {} and {} ({}), amounts sum to {}".format(device_id, start_time, end_time,
                                                                                                                         duration_type.__name__, essential_weighted_states))
            mon_icinga_log_aggregated_service_data.objects.bulk_create(service_db_rows)

        def process_host_alerts():
            host_db_rows = []

            # don't consider alerts for any machine, they are added below
            relevant_host_alerts = mon_icinga_log_raw_host_alert_data.objects.filter(device_independent=False)
            for device_id in relevant_host_alerts.values_list("device", flat=True).distinct():
                dev_db_identification = Q(device=device_id) | Q(device_independent=True)
                # need to find last state
                try:
                    latest_earlier_entry = mon_icinga_log_raw_host_alert_data.objects.filter(dev_db_identification, date__lte=start_time).latest('date')
                    state_description_before = latest_earlier_entry.state, latest_earlier_entry.state_type
                except mon_icinga_log_raw_host_alert_data.DoesNotExist:
                    state_description_before = mon_icinga_log_raw_base.STATE_UNDETERMINED, mon_icinga_log_raw_base.STATE_UNDETERMINED
                relevant_entries = mon_icinga_log_raw_host_alert_data.objects.filter(dev_db_identification, date__range=(start_time, end_time)).order_by('date')
                weighted_states = calc_weighted_states(relevant_entries, state_description_before)
                flapping_ratio = calc_flapping_ratio(host_flapping_cache, device_id)
                if flapping_ratio != 0.0:
                    weighted_states[(mon_icinga_log_aggregated_host_data.STATE_FLAPPING, mon_icinga_log_aggregated_host_data.STATE_FLAPPING)] = flapping_ratio

                for ((state, state_type), value) in weighted_states.iteritems():
                    host_db_rows.append(
                        mon_icinga_log_aggregated_host_data(
                            state=state,
                            state_type=state_type,
                            value=value,
                            timespan=timespan_db,
                            device_id=device_id,
                        )
                    )

                essential_weighted_states_sum = sum(val for (state, state_type), val in weighted_states.iteritems() if state != mon_icinga_log_aggregated_host_data.STATE_FLAPPING)
                if abs(essential_weighted_states_sum-1.0) > 0.01:
                    self.log("missing icinga log entries for device {} between {} and {} ({}), amounts sum to {}".format(device_id, start_time, end_time,
                                                                                                                         duration_type.__name__, essential_weighted_states_sum))

            mon_icinga_log_aggregated_host_data.objects.bulk_create(host_db_rows)

        process_service_alerts()
        process_host_alerts()

