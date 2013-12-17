#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2012,2013 Andreas Lang-Nevyjel
#
# this file is part of package-server
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
""" package server """

import os
import datetime
import logging_tools
import server_command
import subprocess
import time
from lxml import etree # @UnresolvedImport
from lxml.builder import E # @UnresolvedImport
from django.db.models import Q
from initat.cluster.backbone.models import package_repo, cluster_timezone, \
     package_search_result, device_variable, device, package_device_connection
from initat.package_install.server.config import global_config, CONFIG_NAME, \
    PACKAGE_VERSION_VAR_NAME, LAST_CONTACT_VAR_NAME
class repository(object):
    def __init__(self):
        pass

class rpm_repository(repository):
    pass

class repo_type(object):
    def __init__(self, master_process):
        self.master_process = master_process
        self.log_com = master_process.log
        self.log("repository type is %s (%s)" % (self.REPO_TYPE_STR,
                                                 self.REPO_SUBTYPE_STR))
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.log_com("[rt] %s" % (what), log_level)
    def init_search(self, s_struct):
        cur_search = s_struct.run_info["stuff"]
        cur_search.last_search_string = cur_search.search_string
        cur_search.num_searches += 1
        cur_search.results = 0
        cur_search.current_state = "run"
        cur_search.save(update_fields=["last_search_string", "current_state", "num_searches", "results"])

class repo_type_rpm_yum(repo_type):
    REPO_TYPE_STR = "rpm"
    REPO_SUBTYPE_STR = "yum"
    SCAN_REPOS = "yum repolist all"
    REPO_CLASS = rpm_repository
    def search_package(self, s_string):
        return "yum -q --showduplicates search %s" % (s_string)
    def repo_scan_result(self, s_struct):
        self.log("got repo scan result")
        cur_mode = 0
        new_repos = []
        found_repos = []
        old_repos = set(package_repo.objects.all().values_list("name", flat=True))
        for line in s_struct.read().split("\n"):
            if line.startswith("repo id"):
                cur_mode = 1
            elif line.startswith("repolist:"):
                cur_mode = 0
            else:
                if cur_mode == 1:
                    parts = line.strip().replace("enabled:", "enabled").split()
                    while parts[-1] not in ["disabled", "enabled"]:
                        parts.pop(-1)
                    repo_name = parts.pop(0)
                    repo_enabled = True if parts.pop(-1) == "enabled" else False
                    repo_info = " ".join(parts)
                    # print repo_name, repo_enabled, repo_info
                    try:
                        cur_repo = package_repo.objects.get(Q(name=repo_name))
                    except package_repo.DoesNotExist:
                        cur_repo = package_repo(name=repo_name)
                        new_repos.append(cur_repo)
                    found_repos.append(cur_repo)
                    old_repos -= set([cur_repo.name])
                    cur_repo.alias = repo_info
                    cur_repo.enabled = repo_enabled
                    cur_repo.gpg_check = False
                    cur_repo.save()
        self.log("found %s" % (logging_tools.get_plural("new repository", len(new_repos))))
        if old_repos:
            self.log("found %s: %s" % (logging_tools.get_plural("old repository", len(old_repos)),
                                       ", ".join(sorted(old_repos))), logging_tools.LOG_LEVEL_ERROR)
            if global_config["DELETE_MISSING_REPOS"]:
                self.log(" ... removing them from DB", logging_tools.LOG_LEVEL_WARN)
                package_repo.objects.filter(Q(name__in=old_repos)).delete()
        # if s_struct.src_id:
        #    self.master_process.send_pool_message(
        #        "delayed_result",
        #        s_struct.src_id,
        #        "rescanned %s" % (logging_tools.get_plural("repository", len(found_repos))),
        #        server_command.SRV_REPLY_STATE_OK)
        self.master_process._reload_searches()
    def search_result(self, s_struct):
        cur_mode = 0
        found_packs = []
        for line in s_struct.read().split("\n"):
            if line.startswith("===="):
                cur_mode = 1
            elif not line.strip():
                cur_mode = 2
            else:
                if cur_mode == 1:
                    p_name = line.split()[0].strip()
                    if p_name and p_name != ":":
                        found_packs.append(p_name)
        cur_search = s_struct.run_info["stuff"]
        cur_search.current_state = "done"
        cur_search.results = len(found_packs)
        cur_search.last_search = cluster_timezone.localize(datetime.datetime.now())
        cur_search.save(update_fields=["last_search", "current_state", "results"])
        self.log("found for %s: %d" % (cur_search.search_string, cur_search.results))
        for p_name in found_packs:
            parts = p_name.split("-")
            rel_arch = parts.pop(-1)
            arch = rel_arch.split(".")[-1]
            release = rel_arch[:-(len(arch) + 1)]
            version = parts.pop(-1)
            name = "-".join(parts)
            new_sr = package_search_result(
                name=name,

                arch=arch,
                version="%s-%s" % (version, release),
                package_search=cur_search,
                copied=False,
                package_repo=None)
            new_sr.save()

class repo_type_rpm_zypper(repo_type):
    REPO_TYPE_STR = "rpm"
    REPO_SUBTYPE_STR = "zypper"
    SCAN_REPOS = "zypper --xml lr"
    REPO_CLASS = rpm_repository
    def search_package(self, s_string):
        return "zypper --xml search -s %s" % (s_string)
    def repo_scan_result(self, s_struct):
        self.log("got repo scan result")
        repo_xml = etree.fromstring(s_struct.read())
        new_repos = []
        found_repos = []
        old_repos = set(package_repo.objects.all().values_list("name", flat=True))
        for repo in repo_xml.xpath(".//repo-list/repo"):
            try:
                cur_repo = package_repo.objects.get(Q(name=repo.attrib["name"]))
            except package_repo.DoesNotExist:
                cur_repo = package_repo(name=repo.attrib["name"])
                new_repos.append(cur_repo)
            found_repos.append(cur_repo)
            old_repos -= set([cur_repo.name])
            cur_repo.alias = repo.attrib["alias"]
            cur_repo.repo_type = repo.attrib.get("type", "unknown")
            cur_repo.enabled = True if int(repo.attrib["enabled"]) else False
            cur_repo.autorefresh = True if int(repo.attrib["autorefresh"]) else False
            cur_repo.gpg_check = True if int(repo.attrib["gpgcheck"]) else False
            cur_repo.url = repo.findtext("url")
            cur_repo.save()
        self.log("found %s" % (logging_tools.get_plural("new repository", len(new_repos))))
        if old_repos:
            self.log("found %s: %s" % (logging_tools.get_plural("old repository", len(old_repos)),
                                       ", ".join(sorted(old_repos))), logging_tools.LOG_LEVEL_ERROR)
            if global_config["DELETE_MISSING_REPOS"]:
                self.log(" ... removing them from DB", logging_tools.LOG_LEVEL_WARN)
                package_repo.objects.filter(Q(name__in=old_repos)).delete()
        if s_struct.src_id:
            self.master_process.send_pool_message(
                "delayed_result",
                s_struct.src_id,
                "rescanned %s" % (logging_tools.get_plural("repository", len(found_repos))),
                server_command.SRV_REPLY_STATE_OK)
        self.master_process._reload_searches()
    def search_result(self, s_struct):
        res_xml = etree.fromstring(s_struct.read())
        cur_search = s_struct.run_info["stuff"]
        cur_search.current_state = "done"
        cur_search.results = len(res_xml.xpath(".//solvable"))
        cur_search.last_search = cluster_timezone.localize(datetime.datetime.now())
        cur_search.save(update_fields=["last_search", "current_state", "results"])
        # all repos
        repo_dict = dict([(cur_repo.name, cur_repo) for cur_repo in package_repo.objects.all()])
        # delete previous search results
        cur_search.package_search_result_set.all().delete()
        self.log("found for %s: %d" % (cur_search.search_string, cur_search.results))
        for result in res_xml.xpath(".//solvable"):
            if result.attrib["repository"] in repo_dict:
                new_sr = package_search_result(
                    name=result.attrib["name"],
                    kind=result.attrib["kind"],
                    arch=result.attrib["arch"],
                    version=result.attrib["edition"],
                    package_search=cur_search,
                    copied=False,
                    package_repo=repo_dict[result.attrib["repository"]])
                new_sr.save()
            else:
                self.log("unknown repository '%s' for package '%s'" % (
                    result.attrib["repository"],
                    result.attrib["name"],
                    ), logging_tools.LOG_LEVEL_ERROR)

class subprocess_struct(object):
    run_idx = 0
    class Meta:
        max_usage = 2
        max_runtime = 300
        use_popen = True
        verbose = False
    def __init__(self, master_process, src_id, com_line, **kwargs):
        self.log_com = master_process.log
        subprocess_struct.run_idx += 1
        self.run_idx = subprocess_struct.run_idx
        # copy Meta keys
        for key in dir(subprocess_struct.Meta):
            if not key.startswith("__") and not hasattr(self.Meta, key):
                setattr(self.Meta, key, getattr(subprocess_struct.Meta, key))
        if "verbose" in kwargs:
            self.Meta.verbose = kwargs["verbose"]
        self.src_id = src_id
        self.command_line = com_line
        self.multi_command = type(self.command_line) == list
        self.com_num = 0
        self.popen = None
        self.pre_cb_func = kwargs.get("pre_cb_func", None)
        self.post_cb_func = kwargs.get("post_cb_func", None)
        self._init_time = time.time()
        if kwargs.get("start", False):
            self.run()
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.log_com("[ss %d/%d] %s" % (self.run_idx, self.com_num, what), log_level)
    def run(self):
        run_info = {"stuff" : None}
        if self.multi_command:
            if self.command_line:
                cur_cl, add_stuff = self.command_line[self.com_num]
                if type(cur_cl) == type(()):
                    # in case of tuple
                    run_info["comline"] = cur_cl[0]
                else:
                    run_info["comline"] = cur_cl
                run_info["stuff"] = add_stuff
                run_info["command"] = cur_cl
                run_info["run"] = self.com_num
                self.com_num += 1
            else:
                run_info["comline"] = None
        else:
            run_info["comline"] = self.command_line
        self.run_info = run_info
        if run_info["comline"]:
            if self.Meta.verbose:
                self.log("popen '%s'" % (run_info["comline"]))
            self.current_stdout = ""
            if self.pre_cb_func:
                self.pre_cb_func(self)
            self.popen = subprocess.Popen(run_info["comline"], shell=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
    def read(self):
        if self.popen:
            self.current_stdout = "%s%s" % (self.current_stdout, self.popen.stdout.read())
            return self.current_stdout
        else:
            return None
    def process_result(self):
        if self.post_cb_func:
            self.post_cb_func(self)
    def finished(self):
        if self.run_info["comline"] is None:
            self.run_info["result"] = 0
            # empty list of commands
            fin = True
        else:
            self.run_info["result"] = self.popen.poll()
            if self.Meta.verbose:
                if self.run_info["result"] is None:
                    self.log("pending")
                else:
                    self.log("finished with %s" % (str(self.run_info["result"])))
            fin = False
            if self.run_info["result"] is not None:
                self.process_result()
                if self.multi_command:
                    if self.com_num == len(self.command_line):
                        # last command
                        fin = True
                    else:
                        # next command
                        self.run()
                else:
                    fin = True
            else:
                self.current_stdout = "%s%s" % (self.current_stdout, self.popen.stdout.read())
        return fin

class client(object):
    all_clients = {}
    name_set = set()
    def __init__(self, c_uid, name):
        self.uid = c_uid
        self.name = name
        self.__version = ""
        self.device = device.objects.get(Q(name=self.name))
        self.__log_template = None
        self.__last_contact = None
    def create_logger(self):
        if self.__log_template is None:
            self.__log_template = logging_tools.get_logger(
                "%s.%s" % (global_config["LOG_NAME"],
                           self.name.replace(".", r"\.")),
                global_config["LOG_DESTINATION"],
                zmq=True,
                context=client.srv_process.zmq_context,
                init_logger=True)
            self.log("added client")
    @staticmethod
    def init(srv_process):
        client.srv_process = srv_process
        client.uid_set = set()
        client.name_set = set()
        client.lut = {}
        if not os.path.exists(CONFIG_NAME):
            file(CONFIG_NAME, "w").write(etree.tostring(E.package_clients(), pretty_print=True))
        client.xml = etree.fromstring(file(CONFIG_NAME, "r").read())
        for client_el in client.xml.xpath(".//package_client"):
            client.register(client_el.text, client_el.attrib["name"])
    @staticmethod
    def get(key):
        return client.lut[key]
    @staticmethod
    def register(uid, name):
        if uid not in client.uid_set:
            try:
                new_client = client(uid, name)
            except device.DoesNotExist:
                client.srv_process.log("no client with name '%s' found" % (name), logging_tools.LOG_LEVEL_ERROR)
                if name.count("."):
                    s_name = name.split(".")[0]
                    client.srv_process.log("trying with short name '%s'" % (s_name), logging_tools.LOG_LEVEL_WARN)
                    try:
                        new_client = client(uid, s_name)
                    except:
                        new_client = None
                    else:
                        client.srv_process.log("successfull with short name", logging_tools.LOG_LEVEL_WARN)
            if client is not None:
                client.uid_set.add(uid)
                client.name_set.add(name)
                client.lut[uid] = new_client
                client.lut[name] = new_client
                client.srv_process.log("added client %s (%s)" % (name, uid))
                cur_el = client.xml.xpath(".//package_client[@name='%s']" % (name))
                if not len(cur_el):
                    client.xml.append(E.package_client(uid, name=name))
                    file(CONFIG_NAME, "w").write(etree.tostring(client.xml, pretty_print=True))
    def close(self):
        if self.__log_template is not None:
            self.__log_template.close()
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.create_logger()
        self.__log_template.log(level, what)
    def send_reply(self, srv_com):
        self.srv_process.send_reply(self.uid, srv_com)
    def __unicode__(self):
        return u"%s (%s)" % (self.name,
                             self.uid)
    def _modify_device_variable(self, var_name, var_descr, var_type, var_value):
        try:
            cur_var = device_variable.objects.get(Q(device=self.device) & Q(name=var_name))
        except device_variable.DoesNotExist:
            cur_var = device_variable(
                device=self.device,
                name=var_name)
        cur_var.description = var_descr
        cur_var.set_value(var_value)
        cur_var.save()
    def _set_version(self, new_vers):
        if new_vers != self.__version:
            self.log("changed version from '%s' to '%s'" % (self.__version,
                                                            new_vers))
            self.__version = new_vers
            self._modify_device_variable(
                PACKAGE_VERSION_VAR_NAME,
                "actual version of the client",
                "s",
                self.__version)
    def _expand_var(self, var):
        return var.replace("%{ROOT_IMPORT_DIR}", global_config["ROOT_IMPORT_DIR"])
    def _get_package_list(self, srv_com):
        resp = srv_com.builder(
            "packages",
            *[cur_pdc.get_xml(with_package=True) for cur_pdc in package_device_connection.objects.filter(Q(device=self.device)).select_related("package")]
        )
        srv_com["package_list"] = resp
    def _get_repo_list(self, srv_com):
        repo_list = package_repo.objects.filter(Q(publish_to_nodes=True))
        send_ok = [cur_repo for cur_repo in repo_list if cur_repo.distributable]
        self.log("%s, %d to send" % (
            logging_tools.get_plural("publish repo", len(repo_list)),
            len(send_ok),
            ))
        resp = srv_com.builder(
            "repos",
            *[cur_repo.get_xml() for cur_repo in send_ok]
        )
        srv_com["repo_list"] = resp
    def _package_info(self, srv_com):
        pdc_xml = srv_com.xpath(None, ".//package_device_connection")[0]
        info_xml = srv_com.xpath(None, ".//result")
        if len(info_xml):
            info_xml = info_xml[0]
            cur_pdc = package_device_connection.objects.select_related("package").get(Q(pk=pdc_xml.attrib["pk"]))
            cur_pdc.response_type = pdc_xml.attrib["response_type"]
            self.log("got package_info for %s (type is %s)" % (unicode(cur_pdc.package), cur_pdc.response_type))
            cur_pdc.response_str = etree.tostring(info_xml)
            cur_pdc.interpret_response()
            cur_pdc.save(update_fields=["response_type", "response_str", "installed"])
        else:
            self.log("got package_info without result", logging_tools.LOG_LEVEL_WARN)
    def new_command(self, srv_com):
        s_time = time.time()
        self.__last_contact = s_time
        cur_com = srv_com["command"].text
        if "package_client_version" in srv_com:
            self._set_version(srv_com["package_client_version"].text)
        self._modify_device_variable(LAST_CONTACT_VAR_NAME, "last contact of the client", "d", datetime.datetime(*time.localtime()[0:6]))
        srv_com.update_source()
        send_reply = False
        if cur_com == "get_package_list":
            srv_com["command"] = "package_list"
            self._get_package_list(srv_com)
            send_reply = True
        elif cur_com == "get_repo_list":
            srv_com["command"] = "repo_list"
            self._get_repo_list(srv_com)
            send_reply = True
        elif cur_com == "package_info":
            self._package_info(srv_com)
        else:
            self.log("unknown command '%s'" % (cur_com),
                     logging_tools.LOG_LEVEL_ERROR)
        if send_reply:
            self.send_reply(srv_com)
        e_time = time.time()
        self.log("handled command %s in %s" % (
            cur_com,
            logging_tools.get_diff_time_str(e_time - s_time)))

