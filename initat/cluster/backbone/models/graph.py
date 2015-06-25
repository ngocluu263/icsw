# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
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
""" graph models for NOCTUA, CORVUS and NESTOR """

from django.db import models
from django.db.models import signals
from django.dispatch import receiver
from initat.cluster.backbone.signals import SensorThresholdChanged

__all__ = [
    "MachineVector",
    "MVStructEntry",
    "MVValueEntry",
    "SensorAction",
    "SensorThreshold",
]


"""
XML structure on icinga.init.at (27.2.2015):

top levels: ['machine_vector']
[machine_vector (store_name) ->
    [pde (active, file_name, host, init_time, last_update, name, type_instance) ->
        [value (base, factor, index, info, key, name, unit, v_type) ->
        ]
    ]
    [mvl (active, file_name, info, init_time, last_update, name, sane_name) ->
        [value (base, factor, index, info, key, name, unit, v_type) ->
        ]
    ]
    [mve (active, base, factor, file_name, full, info, init_time, last_update, name, sane_name, unit, v_type) ->
    ]
]

"""


class MachineVector(models.Model):
    idx = models.AutoField(primary_key=True)
    # link to device
    device = models.ForeignKey("device")
    # src_file name, for later reference
    src_file_name = models.CharField(max_length=256, default="", blank=True)
    # directory under cache_dir, in most cases the UUID
    dir_name = models.CharField(max_length=128, default="")
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return u"MachineVector for device {}".format(unicode(self.device))


class MVStructEntry(models.Model):
    # structural entry for machine_vector, references an RRD-file on disk
    idx = models.AutoField(primary_key=True)
    machine_vector = models.ForeignKey("MachineVector")
    file_name = models.CharField(max_length=256, default="")
    # needed ?
    se_type = models.CharField(
        max_length=6,
        choices=[
            ("pde", "pde"),
            ("mvl", "mvl"),
            ("mve", "mve"),
        ],
    )
    # we ignore the 'host' field for pdes because it seems to be a relict from the original PerformanceData sent from icinga
    # info is set for mvl structural entries, is now ignored
    # info = models.CharField(max_length=256, default="")
    # type instance is set for certains PDEs (for instance windows disk [C,D,E,...], SNMP netifaces [eth0,eth1,...])
    type_instance = models.CharField(max_length=16, default="")
    # position in RRD-tree this nodes resides in, was name
    key = models.CharField(max_length=256)
    # is active
    is_active = models.BooleanField(default=True)
    # last update
    last_update = models.DateTimeField(auto_now=True)
    # was init_time
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return u"MVStructEntry ({}, {}), file is {}".format(
            self.se_type,
            self.key,
            self.file_name,
        )

    class Meta:
        ordering = ("key",)


class MVValueEntry(models.Model):
    # value entry for machine_vector
    idx = models.AutoField(primary_key=True)
    mv_struct_entry = models.ForeignKey("MVStructEntry")
    # base for generating {k,M,G,T} values, in most cases 1000 or 1024
    base = models.IntegerField(default=1024)
    # factor, a simple multiplicator to get to a sane value (in most cases 1)
    factor = models.IntegerField(default=1)
    # unit
    unit = models.CharField(max_length=16, default="")
    # variable type
    v_type = models.CharField(max_length=3, choices=[("i", "int"), ("f", "float")], default="f")
    # info string
    info = models.CharField(max_length=256, default="")
    # key, string describing the last part of the position (was also called name), not necessarily a single value
    # (for instance request.time.connect for HTTP perfdata)
    # the full key is mv_struct_entry.key + "." + mv_value.key
    # may be empty in case of mve entries (full key is stored in mv_struct_entry)
    key = models.CharField(max_length=128, default="")
    # full key for this value, stored for faster reference
    full_key = models.CharField(max_length=128, default="")
    # name, required to look up the correct row in the RRD in case of perfdata
    # otherwise this entry is forced to be empty (otherwise we have problems in rrd-grapher)
    # (no longer valid: we don't store the name which was the last part of key)
    name = models.CharField(max_length=64, default="")
    # we also don't store the index because this fields was omitted some time ago (still present in some XMLs)
    # full is also not stored because full is always equal to name
    # sane_name is also ignored because this is handled by collectd to generate filesystem-safe filenames ('/' -> '_sl_')
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return u"MVValueEntry ({}{}, '{}'), '{}' b/f={:d}/{:d} ({})".format(
            self.key or "NONE",
            ", name={}".format(self.name) if self.name else "",
            self.info,
            self.unit,
            self.base,
            self.factor,
            self.v_type,
        )

    def copy_and_modify(self, mod_dict):
        # return a copy of the current MVValueEntry and set the attributes according to mod_dict
        new_mv = MVValueEntry(
            mv_struct_entry=self.mv_struct_entry,
            base=self.base,
            factor=self.factor,
            unit=self.unit,
            v_type=self.v_type,
            info=self.info,
            key=self.key,
            full_key=self.full_key,
            date=self.date
        )
        for _key, _value in mod_dict.iteritems():
            if _key not in set(["key", "full_key"]):
                setattr(new_mv, _key, _value)
        return new_mv

    class Meta:
        ordering = ("key",)


class SensorAction(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=64, unique=True)
    description = models.CharField(max_length=256, default="")
    send_email = models.BooleanField(default=False)
    action = models.CharField(
        max_length=64,
        default="none",
        choices=[
            ("none", "do nothing"),
            ("reboot", "restart device"),
            ("halt", "halt device"),
        ]
    )
    # action on device via soft- or hardware
    hard_control = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "SensorAction {}".format(self.name)


class SensorThreshold(models.Model):
    idx = models.AutoField(primary_key=True)
    # name of Threshold
    name = models.CharField(max_length=64, default="")
    mv_value_entry = models.ForeignKey("MVValueEntry")
    value = models.FloatField(default=0.0)
    hysteresis = models.FloatField(default=0.0)
    sensor_action = models.ForeignKey("SensorAction")
    limit_class = models.CharField(
        max_length=2,
        choices=[
            ("u", "upper"),
            ("l", "lower"),
        ]
    )
    # which users to notify
    notify_users = models.ManyToManyField("user")
    # device selection
    device_selection = models.ForeignKey("DeviceSelection", null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "SensorThreshold '{}' [{}, {:.4f}@{:.4f} '{}' for {}, action is {}".format(
            self.name,
            self.limit_class,
            self.value,
            self.hysteresis,
            self.name,
            unicode(self.mv_value_entry),
            unicode(self.sensor_action),
        )


@receiver(signals.pre_save, sender=SensorThreshold)
def SensorThresholdPreSave(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        _cur_inst.hysteresis = abs(_cur_inst.hysteresis)


@receiver(signals.post_save, sender=SensorThreshold)
def SensorThresholdPostSave(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        SensorThresholdChanged.send(sender=_cur_inst, sensor_threshold=_cur_inst, cause="SensorThreshold saved")


@receiver(signals.post_delete, sender=SensorThreshold)
def SensorThresholdPostDelete(sender, **kwargs):
    print "pd"
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]
        print "send"
        SensorThresholdChanged.send(sender=_cur_inst, sensor_threshold=_cur_inst, cause="SensorThreshold deleted")
