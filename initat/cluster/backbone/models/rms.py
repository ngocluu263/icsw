# Copyright (C) 2013-2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of cluster-backbone-sql
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
# -*- coding: utf-8 -*-
#
""" database definitions for RMS """

# from django.db.models import Q, signals, get_model
# from django.dispatch import receiver
from django.db import models
from initat.cluster.backbone.models.functions import cluster_timezone
import datetime
import time

__all__ = [
    "rms_job",
    "rms_job_run",
    "rms_pe_info",
    "rms_project",
    "rms_department",
    "rms_queue",
    "rms_pe",
    "ext_license",
    "ext_license_version",
    "ext_license_vendor",
    "ext_license_user",
    "ext_license_client",
    "ext_license_check",
    "ext_license_state",
    "ext_license_version_state",
    "ext_license_usage",
]


class rms_project(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    # oticket = models.FloatField(null=True, blank=True)
    # fshare = models.FloatField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.name

    class Meta:
        app_label = "backbone"


class rms_department(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    # oticket = models.FloatField(null=True, blank=True)
    # fshare = models.FloatField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return self.name

    class Meta:
        app_label = "backbone"


class rms_queue(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "queue {}".format(self.name)

    class Meta:
        app_label = "backbone"


class rms_pe(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "pe {}".format(self.name)

    class Meta:
        app_label = "backbone"


class rms_job(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    # id of job
    jobid = models.IntegerField()
    taskid = models.IntegerField(null=True)
    owner = models.CharField(max_length=255, default="")
    user = models.ForeignKey("backbone.user", null=True)
    date = models.DateTimeField(auto_now_add=True)

    @property
    def full_id(self):
        return "{:d}{}".format(
            self.jobid,
            ".{:d}".format(self.taskid) if self.taskid else "",
        )

    def add_job_run(self, _dev_name, _dev):
        new_run = rms_job_run(
            rms_job=self,
            device=_dev,
            hostname=_dev_name,
            start_time_py=cluster_timezone.localize(datetime.datetime.now()),
        )
        return new_run

    def get_latest_job_run(self):
        _runs = self.rms_job_run_set.all().order_by("-pk")
        if _runs.count():
            _latest_run = _runs[0]
        else:
            _latest_run = None
        return _latest_run

    def close_job_run(self):
        _latest_run = self.get_latest_job_run()
        if _latest_run:
            _latest_run.end_time_py = cluster_timezone.localize(datetime.datetime.now())
            _latest_run.save(update_fields=["end_time_py"])
        return _latest_run

    def __unicode__(self):
        return "job {}".format(self.full_id)

    class Meta:
        app_label = "backbone"


class rms_job_run(models.Model):
    idx = models.AutoField(primary_key=True)
    rms_job = models.ForeignKey(rms_job)
    # device, from hostname via qacct
    device = models.ForeignKey("backbone.device", null=True)
    rms_pe = models.ForeignKey("backbone.rms_pe", null=True)
    hostname = models.CharField(max_length=255)
    # from qacct
    rms_project = models.ForeignKey("backbone.rms_project", null=True)
    rms_department = models.ForeignKey("backbone.rms_department", null=True)
    granted_pe = models.CharField(max_length=192, default="")
    slots = models.IntegerField(null=True)
    priority = models.IntegerField(default=0)
    account = models.CharField(max_length=384, default="")
    failed = models.IntegerField(default=0)
    failed_str = models.CharField(max_length=255, default="")
    exit_status = models.IntegerField(default=0)
    exit_status_str = models.CharField(max_length=255, default="")
    queue_time = models.DateTimeField(null=True)
    # via qname
    rms_queue = models.ForeignKey("backbone.rms_queue")
    start_time = models.DateTimeField(null=True)
    end_time = models.DateTimeField(null=True)
    # end data from qacct
    start_time_py = models.DateTimeField(null=True)
    end_time_py = models.DateTimeField(null=True)
    # data set via qacct ?
    qacct_called = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

    def rms_pe_info(self):
        # used by serializer and rrd-grapher.initat.graph"
        return [
            {
                "device": _pe_info.device_id,
                "hostname": _pe_info.hostname,
                "slots": _pe_info.slots,
            } for _pe_info in self.rms_pe_info_set.all()
        ]

    def get_queue_time(self):
        return time.mktime(cluster_timezone.normalize(self.queue_time).timetuple()) if self.queue_time else ""

    def get_start_time(self):
        return time.mktime(cluster_timezone.normalize(self.start_time).timetuple()) if self.start_time else ""

    def get_end_time(self):
        return time.mktime(cluster_timezone.normalize(self.end_time).timetuple()) if self.end_time else ""

    def get_start_time_py(self):
        return time.mktime(cluster_timezone.normalize(self.start_time_py).timetuple()) if self.start_time_py else ""

    def get_end_time_py(self):
        return time.mktime(cluster_timezone.normalize(self.end_time_py).timetuple()) if self.end_time_py else ""

    def __unicode__(self):
        return "run for {} in {}".format(
            unicode(self.rms_job),
            unicode(self.rms_queue),
        )

    def _set_is_value(self, attr_name, value):
        if type(value) in [int, long]:
            setattr(self, attr_name, value)
            setattr(self, "{}_str".format(attr_name), "")
        else:
            _int, _str = value.strip().split(None, 1)
            setattr(self, attr_name, int(_int))
            setattr(self, "{}_str".format(attr_name), _str.strip())

    def feed_qacct_data(self, in_dict):
        self.priority = in_dict["priority"]
        self.rms_project = in_dict["project"]
        self.rms_department = in_dict["department"]
        self.account = in_dict["account"]
        self._set_is_value("failed", in_dict["failed"])
        self._set_is_value("exit_status", in_dict["exit_status"])
        if in_dict["start_time"]:
            self.start_time = in_dict["start_time"]
        if in_dict["end_time"]:
            self.end_time = in_dict["end_time"]
        if in_dict["qsub_time"]:
            self.queue_time = in_dict["qsub_time"]
        self.qacct_called = True
        self.save()

    class Meta:
        app_label = "backbone"


class rms_pe_info(models.Model):
    idx = models.AutoField(primary_key=True)
    rms_job_run = models.ForeignKey(rms_job_run)
    device = models.ForeignKey("backbone.device", null=True)
    hostname = models.CharField(max_length=255)
    slots = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"


# license models
class ext_license_base(models.Model):
    idx = models.AutoField(primary_key=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        app_label = "backbone"


class ext_license(ext_license_base):
    name = models.CharField(max_length="128", unique=True)


class ext_license_version(ext_license_base):
    ext_license = models.ForeignKey("backbone.ext_license")
    version = models.CharField(max_length=64, default="")


class ext_license_vendor(ext_license_base):
    name = models.CharField(max_length=64, default="", unique=True)


class ext_license_client(ext_license_base):
    long_name = models.CharField(max_length=256, default="")
    short_name = models.CharField(max_length=128, default="")
    device = models.ForeignKey("backbone.device", null=True, on_delete=models.SET_NULL)


class ext_license_user(ext_license_base):
    name = models.CharField(max_length=256, default="")
    user = models.ForeignKey("backbone.user", null=True, on_delete=models.SET_NULL)


class ext_license_check(ext_license_base):
    check_time = models.DateTimeField(auto_now_add=True)
    run_time = models.FloatField(default=0.0)


class ext_license_state(ext_license_base):
    ext_license_check = models.ForeignKey("backbone.ext_license_check")
    ext_license = models.ForeignKey("backbone.ext_license")
    used = models.IntegerField(default=0)
    reserved = models.IntegerField(default=0)
    free = models.IntegerField(default=0)
    issued = models.IntegerField(default=0)


class ext_license_version_state(ext_license_base):
    ext_license_check = models.ForeignKey("backbone.ext_license_check")
    ext_license_version = models.ForeignKey("backbone.ext_license_version")
    ext_license_state = models.ForeignKey("backbone.ext_license_state")
    is_floating = models.BooleanField(default=False)
    vendor = models.ForeignKey("backbone.ext_license_vendor")


class ext_license_usage(ext_license_base):
    ext_license_version_state = models.ForeignKey("backbone.ext_license_version_state")
    ext_license_client = models.ForeignKey("backbone.ext_license_client")
    ext_license_user = models.ForeignKey("backbone.ext_license_user")
    checkout_time = models.IntegerField(default=0)
    num = models.IntegerField(default=0)
