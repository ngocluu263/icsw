# -*- coding: utf-8 -*-
"""
Checks related to pgpool-II >= 3.0 via SQL interface.
"""

from ConfigParser import SafeConfigParser
from initat.host_monitoring import limits
from initat.host_monitoring.hm_classes import hm_command, hm_module
from initat.host_monitoring.server import server_command
import cPickle
import os
import psycopg2

CONFIG_DIR = "/etc/sysconfig/host-monitoring.d/"
CONFIG_FILE = "database.config"
SECTION = "pgpool"

DEFAULTS = {
    "HOST": "",
    "PORT": "5432",
    "USER": "postgres",
    "PASSWORD": "",
    "DATABASE": "template1"
}

# Key used in srv_com dictionary like objects
KEY = "pgpool"

NODE_UP_NO_CONN = 1 # Node is up. No connections yet.
NODE_UP = 2 # Node is up. Connections are pooled.
NODE_DOWN = 3 # Node is down.

class _general(hm_module):
    pass

class ArgumentError(Exception):
    pass

class PgPoolCommand(hm_command):
    sql = NotImplemented
    key = NotImplemented
    def read_config(self):
        self.config = {}
        parser = SafeConfigParser()
        if os.path.isfile(os.path.join(CONFIG_DIR, CONFIG_FILE)):
            parser.read(os.path.join(CONFIG_DIR, CONFIG_FILE))
        if parser.has_section(SECTION):
            self.config["host"] = parser.get(SECTION, "HOST")
            self.config["port"] = parser.get(SECTION, "PORT")
            self.config["user"] = parser.get(SECTION, "USER")
            self.config["password"] = parser.get(SECTION, "PASSWORD")
            self.config["database"] = parser.get(SECTION, "DATABASE")
        else:
            for key, value in DEFAULTS.iteritems():
                self.config[key.lower()] = value
        # Access via UNIX socket
        if not self.config["host"]:
            del self.config["host"]
    def query(self, sql=None):
        """ Passing in sql overrrides self.sql """
        cursor = psycopg2.connect(**self.config).cursor()
        if sql:
            cursor.execute(sql)
        else:
            cursor.execute(self.sql)
        return cursor.fetchall()
    def pack(self, value):
        """ Since dicts are passed through use pack and unpack to pass arbitrary objects """
        d = {}
        d["result"] = cPickle.dumps(value)
        return d
    def unpack(self, packed_dict):
        value = packed_dict["result"]
        return cPickle.loads(value)
    def __call__(self, srv_com, cur_ns):
        try:
            result = self.query()
        except (psycopg2.DatabaseError, psycopg2.InterfaceError):
            error_info = {
                "reply": "Error executing '%s'" % self.sql,
                "state": str(server_command.SRV_REPLY_STATE_ERROR)
            }
            srv_com["result"].attrib.update(error_info)
        else:
            srv_com[self.key] = self.pack(result)

"""
# Not really that useful as a check - just dumps the config info
class pgpool_status_command(PgPoolCommand):
    info_str = "Display pgpool status info"
    sql = "SHOW pool_status;"
    key = KEY
"""


class pgpool_nodes_command(PgPoolCommand):
    info_str = ("Check if the correct node count is returned and all nodes are not "
               "in status NODE_DOWN")
    sql = "SHOW pool_nodes;"
    key = KEY
    def __init__(self, name):
        super(PgPoolCommand, self).__init__(name, positional_arguments=True)
        self.read_config()
    def interpret(self, srv_com, cur_ns):
        result = self.unpack(srv_com[self.key])
        node_count = len(result)
        nodes_down = [_line[0] for _line in result if int(_line[3]) == NODE_DOWN]
        if cur_ns.arguments:
            t_nc = int(cur_ns.arguments[0])
            if node_count != t_nc:
                state = limits.nag_STATE_CRITICAL
                text = "pgpool node count out of range: %d expected %d" % (node_count, t_nc)
            elif nodes_down:
                state = limits.nag_STATE_CRITICAL
                text = "pgpool: some nodes down: %s" % ", ".join(["node_%s" % i for i in nodes_down])
            else:
                state = limits.nag_STATE_OK
                text = "pgpool node count: %d and all nodes UP" % node_count
        else:
            state, text = (limits.nag_STATE_CRITICAL, "number of nodes not specified")
        return state, text

class pgpool_processes_command(PgPoolCommand):
    info_str = "Check for the correct count of pgpool processes"
    sql = "SHOW pool_processes;"
    key = KEY
    def __init__(self, name):
        super(PgPoolCommand, self).__init__(name, positional_arguments=True)
        self.parser.add_argument("--min", dest="min", type=int, default=0)
        self.parser.add_argument("--max", dest="max", type=int, default=0)
        self.read_config()
    def interpret(self, srv_com, cur_ns):
        result = self.unpack(srv_com[self.key])
        process_count = len(result)
        if not cur_ns.min <= process_count <= cur_ns.max:
            state = limits.nag_STATE_CRITICAL
            text = "pgpool process count out of range: %d not in [%d, %d]" % (
                process_count,
                cur_ns.min, cur_ns.max)
        else:
            state = limits.nag_STATE_OK
            text = "pgpool process count: %d" % process_count
        return state, text


class pgpool_pools_command(PgPoolCommand):
    info_str = "Check for the correct count of pgpool pools"
    sql = "SHOW pool_pools;"
    key = KEY
    # Minimum and maximum count of pgpool pools - most likely to be used with min == max
    def __init__(self, name):
        super(PgPoolCommand, self).__init__(name, positional_arguments=True)
        self.parser.add_argument("--min", dest="min", type=int, default=0)
        self.parser.add_argument("--max", dest="max", type=int, default=0)
        self.read_config()
    def interpret(self, srv_com, cur_ns):
        result = self.unpack(srv_com[self.key])
        pool_count = len(result)
        if not cur_ns.min <= pool_count <= cur_ns.max:
            state = limits.nag_STATE_CRITICAL
            text = "pgpool pool count out of range: %d not in [%d, %d]" % (
                pool_count,
                cur_ns.min,
                cur_ns.max,
                )
        else:
            state = limits.nag_STATE_OK
            text = "pgpool pool count: %d" % pool_count
        return state, text


class pgpool_version_command(PgPoolCommand):
    info_str = "Check for a specific version of pgpool"
    sql = "SHOW pool_version;"
    key = KEY
    def __init__(self, name):
        super(PgPoolCommand, self).__init__(name, positional_arguments=True)
        self.read_config()
    def interpret(self, srv_com, cur_ns):
        result = self.unpack(srv_com[self.key])[0][0]
        if cur_ns.arguments:
            t_vers = cur_ns.arguments[0]
            if t_vers != result:
                state = limits.nag_STATE_CRITICAL
                text = "Version mismatch: %s != %s" % (t_vers, result)
            else:
                state, text = (limits.nag_STATE_OK, "versions match (%s)" % (t_vers))
        else:
            state, text = (limits.nag_STATE_CRITICAL, "no target version specified")
        return state, text

