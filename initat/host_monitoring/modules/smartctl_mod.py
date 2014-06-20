# Copyright (C) 2001-2008,2014 Andreas Lang-Nevyjel, init.at
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

""" check smartctl status """

from initat.host_monitoring import hm_classes
from initat.host_monitoring import limits
import commands
import process_tools
import server_command

class _general(hm_classes.hm_module):
    def base_init(self):
        self.smartctl_bin = process_tools.find_file("smartctl")
    def init_module(self):
        self.devices = {}
        if self.smartctl_bin:
            _stat, _lines = self.smcall("--scan")
            if not _stat:
                for line in _lines:
                    line = line.strip().split("#")[0].strip()
                    _dev_name, _dev_opts = line.split(None, 1)
                    self.log("found device {} ({})".format(_dev_name, _dev_opts))
                    self.devices[_dev_name] = {
                        "opts"   : _dev_opts,
                        "device" : _dev_name,
                    }
        else:
            self.log("no smartctl binary found, no smart info available")
    def smcall(self, args):
        cmd_line = "{} {}".format(self.smartctl_bin, args)
        c_stat, c_out = commands.getstatusoutput(cmd_line)
        if c_stat:
            self.log("error calling {} ({:d}): {}".format(
                cmd_line,
                c_stat,
                c_out,
                ))
        return c_stat, c_out.split("\n")
    def update_smart(self, dev_list=[]):
        dev_list = dev_list or self.devices.keys()
        for dev in dev_list:
            c_stat, c_out = self.smcall("-a {} -q errorsonly".format(dev))
            self.devices[dev].update(
                {
                    "check_result" : c_stat,
                    "check_output" : c_out,
                }
            )

class smartstat_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True, arguments_name="interface")
    def __call__(self, srv_com, cur_ns):
        if "arguments:arg0" in srv_com:
            dev = srv_com["*arguments:arg0"]
            if dev in self.module.devices:
                self.module.update_smart([dev])
                srv_com["smartstat"] = [self.module.devices[dev]]
            else:
                srv_com.set_result(
                    "device '{}' not found".format(dev),
                    server_command.SRV_REPLY_STATE_ERROR,
                )
        else:
            srv_com["smartstat"] = [self.module.devices[_dev] for _dev in self.module.devices.keys()]
    def interpret(self, srv_com, cur_ns):
        smartstat = srv_com["*smartstat"]
        if smartstat:
            ret_state = limits.nag_STATE_OK
            ret_f = []
            for _dev in smartstat:
                if _dev["check_result"]:
                    ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                ret_f.append(
                    "{}: {}".format(
                        _dev["device"],
                        "\n".join(_dev["check_output"]) or "OK",
                        )
                    )
            ret_str = ", ".join(ret_f)
        else:
            ret_state, ret_str = limits.nag_STATE_WARNING, "no devices found"
        return ret_state, ret_str

