# Copyright (C) 2015 Bernhard Mallinger, init.at
#
# Send feedback to: <mallinger@init.at>
#
# this file is part of discovery-server
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
import re
import django.utils.timezone

from initat.tools import logging_tools, process_tools
from initat.cluster.backbone.models import device_variable
from initat.discovery_server.discovery_struct import ExtCom

from .event_log_scanner_base import EventLogPollerJobBase


__all__ = [
    'IpmiLogJob',
]


def strip_list_entries(l):
    return [elem.strip() for elem in l]


class IpmiLogJob(EventLogPollerJobBase):

    IPMI_USERNAME_VARIABLE_NAME = "IPMI_USERNAME"
    IPMI_PASSWORD_VARIABLE_NAME = "IPMI_PASSWORD"

    def __init__(self, log, db, target_device, target_ip, last_known_record_id):
        super(IpmiLogJob, self).__init__(log, db, target_device, target_ip)
        self.last_known_record_id = last_known_record_id

        self.username = device_variable.objects.get_device_variable_value(device=self.target_device,
                                                                          var_name=self.IPMI_USERNAME_VARIABLE_NAME)
        if not self.username:
            raise RuntimeError(
                "For IPMI event log scanning, the device {} must have a device variable "
                "called \"{}\" which contains the user name for IPMI on this device".format(
                    self.target_device, self.IPMI_USERNAME_VARIABLE_NAME
                )
            )
        self.password = device_variable.objects.get_device_variable_value(device=self.target_device,
                                                                          var_name=self.IPMI_PASSWORD_VARIABLE_NAME)
        if not self.password:
            raise RuntimeError(
                "For IPMI event log scanning, the device {} must have a device variable "
                "called \"{}\" which contains the user name for IPMI on this device".format(
                    self.target_device, self.IPMI_PASSWORD_VARIABLE_NAME
                )
            )

        self.current_phase = self.FindMaximumPhase()

    def __unicode__(self):
        return u"IpmiLogJob((dev={}, ip={})".format(self.target_device, self.target_ip)

    __repr__ = __unicode__

    def start(self):
        pass

    def periodic_check(self):
        do_continue = self.current_phase(self)
        return do_continue

    class FindMaximumPhase(object):
        def __init__(self):
            self.ext_com = None

        def __call__(self, job):
            if self.ext_com is None:
                # initial call, start the job
                cmd = (
                    process_tools.find_file("ipmitool"),
                    "-H", job.target_ip,
                    "-U", job.username,
                    "-P", job.password,
                    "sel",
                    "list",
                )
                self.ext_com = ExtCom(job.log, cmd, shell=False,
                                      debug=True)  # shell=False since args must not be parsed again
                self.ext_com.run()
            else:
                # job has been started, check
                exit_code = self.ext_com.finished()

                if exit_code is not None:

                    stdout_out, stderr_out = self.ext_com.communicate()

                    if stderr_out:
                        job._handle_stderr(stderr_out, "finding out maximum ipmi sel record id")

                    if exit_code != 0:
                        raise RuntimeError(
                            "IpmiLogJob FindMaximumPhase ipmitool command failed with code {}".format(exit_code)
                        )

                    # lines look like this (first is record id in hex):
                    #  67 | 06/17/2015 | 04:20:03 | Temperature #0x32 | Upper Non-critical going high
                    stdout_lines = stdout_out.split("\n")
                    record_ids_string = [line.split("|", 1)[0].strip() for line in stdout_lines]
                    record_ids_no_empty_ones = [entry for entry in record_ids_string if entry]
                    record_ids_int = [int(entry, base=16) for entry in record_ids_no_empty_ones]

                    max_record_id = max(record_ids_int)

                    job.log("Gathering records from {} to {} for {}".format(
                        job.last_known_record_id, max_record_id, job
                    ))
                    job.current_phase = IpmiLogJob.RetrieveEvents(job.last_known_record_id, max_record_id)

            return True  # do_continue

    class RetrieveEvents(object):
        def __init__(self, last_known_record_id, max_record_id):
            self.ext_com = None
            self.max_record_id = max_record_id
            self.current_record_id = last_known_record_id + 1 if last_known_record_id is not None else 1
            # 1 is first record id

        def __call__(self, job):
            if self.ext_com is not None:
                self.check_current_output(job)

            do_continue = self.current_record_id <= self.max_record_id

            # start next job if there are ids yet to get and if no job is running
            if do_continue and (self.ext_com is None or self.ext_com.finished() is not None):
                self.start_next_job(job)

            return do_continue

        def start_next_job(self, job):
            cmd = (
                process_tools.find_file("ipmitool"),
                "-H", job.target_ip,
                "-U", job.username,
                "-P", job.password,
                "sel",
                "get",
                hex(self.current_record_id),
            )
            self.ext_com = ExtCom(job.log, cmd, shell=False,
                                  debug=True)  # shell=False since args must not be parsed again
            self.ext_com.run()

        def check_current_output(self, job):
            exit_code = self.ext_com.finished()

            if exit_code is not None:

                stdout_out, stderr_out = self.ext_com.communicate()

                if stderr_out:
                    job._handle_stderr(stderr_out, "retrieving sel record {}".format(self.current_record_id))

                if exit_code != 0:
                    raise RuntimeError("IpmiLogJob ipmitool command failed with code {}".format(exit_code))

                # entries look like this:
                # SEL Record ID          : 0067
                #  Record Type           : 02
                #  Timestamp             : 06/17/2015 04:20:03
                # [...]
                #
                # Sensor ID              : Ambient Temp (0x32)
                #  Entity ID             : 12.1
                #  Sensor Type (Threshold)  : Temperature

                # sections are separated by empty lines (usually without whitespace in between, but handle anyway)
                sections_raw = re.compile("\n[ \t]*\n").split(stdout_out)
                sections_db_data = []
                for sec in sections_raw:
                    if sec:  # there might be an empty last entry
                        parsed = job._parse_section(sec)
                        if parsed:
                            sections_db_data.append(parsed)

                db_entry = {
                    'parse_date': django.utils.timezone.now(),
                    'record_id': self.current_record_id,
                    'sections': sections_db_data,
                    'device_pk': job.target_device.pk,
                }
                job.db.ipmi_event_log.insert(db_entry)
                job.log("feeding db: {}".format(db_entry))

                self.current_record_id += 1

    def _parse_section(self, section_string):
        lines = section_string.split("\n")
        print 'parsing', section_string, '\nlines', lines
        ret = None
        if lines:
            section_content = {}

            # parse first line of section
            if lines[0].startswith(" ") or ':' not in lines[0]:
                self.log("Section in ipmi sel does not have header: {}".format(lines[0]),
                         logging_tools.LOG_LEVEL_WARN)
            else:
                section_type, section_type_value = strip_list_entries(lines[0].split(":", 1))
                # can be something like:
                # SEL Record ID          : 0067
                # or
                # Sensor ID              : Ambient Temp (0x32)

                section_content[section_type] = section_type_value
                section_content["__icsw_ipmi_section_type"] = section_type

            # parse regular entries

            # lines[1:] looks like this:
            # Entity ID             : 19.1
            # Sensor Type (Discrete): Power Supply
            # States Asserted       : Redundancy State
            #                         [Fully Redundant]

            # we assume that lines with no keys belong to the last entry
            last_key = None
            for content_line in lines[1:]:
                if ':' not in content_line:
                    if last_key is None:
                        self.log("Invalid content line in ipmi sel: {}".format(content_line),
                                 logging_tools.LOG_LEVEL_WARN)
                    else:
                        section_content[last_key] = section_content[last_key] + ", " + content_line.strip()

                else:
                    key, value = strip_list_entries(content_line.split(":", 1))
                    section_content[key] = value

                    last_key = key

            ret = section_content
        else:
            self.log("Empty section in ipmi sel: {}".format(section_string),
                     logging_tools.LOG_LEVEL_WARN)
        return ret

    def _handle_stderr(self, stderr_out, context):
        self.log("impitool yielded error output in {}:".format(context), logging_tools.LOG_LEVEL_ERROR)
        for line in stderr_out.split("\n"):
            self.log(line, logging_tools.LOG_LEVEL_ERROR)
        self.log("end of errors", logging_tools.LOG_LEVEL_ERROR)