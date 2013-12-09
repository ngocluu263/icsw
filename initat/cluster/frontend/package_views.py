#!/usr/bin/python-init -Otu
# package views

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.db.utils import IntegrityError
from django.utils.decorators import method_decorator
from django.views.generic import View
from initat.cluster.backbone.models import package_repo, package_search, user, \
     package_search_result, package, get_related_models, package_device_connection, \
     device, device_variable, to_system_tz
from initat.cluster.frontend.helper_functions import contact_server, xml_wrapper, get_listlist
from initat.core.render import render_me
from initat.cluster.frontend.forms import package_search_form
from lxml.builder import E # @UnresolvedImports
import logging
import logging_tools
import pprint
import re
import server_command
import time

logger = logging.getLogger("cluster.package")

class repo_overview(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(request, "package_repo_overview.html", {
            "package_search_form" : package_search_form(request=request),
            })()

def reload_searches(request):
    srv_com = server_command.srv_command(command="reload_searches")
    return contact_server(request, "tcp://localhost:8007", srv_com, timeout=5, log_result=False)

class retry_search(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        retry_pk = _post["pk"]
        try:
            cur_search = package_search.objects.get(Q(pk=retry_pk))
        except package_search.DoesNotExist:
            request.xml_response.error("search does not exist", logger)
            cur_search = None
        if cur_search is not None:
            if cur_search.current_state == "done":
                with transaction.atomic():
                    cur_search.current_state = "wait"
                    cur_search.save(update_fields=["current_state"])
                reload_searches(request)
            else:
                request.xml_response.warn("search is in wrong state '%s'" % (cur_search.current_state), logger)

class use_package(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        try:
            cur_sr = package_search_result.objects.get(Q(pk=_post["pk"]))
        except package_search_result.DoesNotExist:
            request.xml_response.error("package_result not found", logger)
        else:
            request.xml_response.info("copied package_result", logger)
            try:
                _new_p = cur_sr.create_package()
            except IntegrityError, what:
                request.xml_response.error("error modifying: %s" % (unicode(what)), logger)

class unuse_package(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        try:
            cur_p = package.objects.get(Q(pk=_post["pk"]))
        except package.DoesNotExist:
            request.xml_response.error("package not found", logger)
        else:
            num_ref = get_related_models(cur_p)
            if num_ref:
                request.xml_response.error("cannot remove: %s" % (logging_tools.get_plural("reference", num_ref)),
                            logger)
            else:
                cur_p.delete()
                request.xml_response.info("removed package", logger)

class install(View):
    @method_decorator(login_required)
    def get(self, request):
        return render_me(request, "package_install.html", {})()
    @method_decorator(xml_wrapper)
    def post(self, request):
        xml_resp = E.response(
            E.packages(
                *[cur_p.get_xml() for cur_p in package.objects.all()]
            ),
            E.target_states(
                *[E.target_state(key, pk=key) for key in ["keep", "install", "upgrade", "erase"]]
                ),
            E.package_repos(*[cur_r.get_xml() for cur_r in package_repo.objects.all()])
        )
        request.xml_response["response"] = xml_resp

class refresh(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        # print time.mktime(datetime.datetime.now().timetuple()), int(float(_post["cur_time"]))
        # pprint.pprint(_post)
        dev_list = [key.split("__")[1] for key in _post.getlist("sel_list[]")]
        xml_resp = E.response(
            E.package_device_connections(
                *[cur_pdc.get_xml() for cur_pdc in package_device_connection.objects.filter(Q(device__in=dev_list))]
            ),
            E.last_contacts(
                *[E.last_contact(device="%d" % (cur_var.device_id), when="%d" % (
                    time.mktime(to_system_tz(cur_var.val_date).timetuple())))
                    for cur_var in device_variable.objects.filter(Q(name="package_server_last_contact") & Q(device__pk__in=dev_list))]
            )
        )
        request.xml_response["response"] = xml_resp

class add_package(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        num_ok, num_error = (0, 0)
        new_entries = E.entries()
        for dev_pk_s, pack_pk_s in get_listlist(_post, "add_list", []):
            dev_pk, pack_pk = (
                int(dev_pk_s.split("__")[1]),
                int(pack_pk_s.split("__")[1]))
            try:
                _cur_pdc = package_device_connection.objects.get(Q(device=dev_pk) & Q(package=pack_pk))
            except package_device_connection.DoesNotExist:
                new_pdc = package_device_connection(
                    device=device.objects.get(Q(pk=dev_pk)),
                    package=package.objects.get(Q(pk=pack_pk)))
                new_pdc.save()
                new_entries.append(new_pdc.get_xml())
                num_ok += 1
            else:
                num_error += 1
        if num_ok:
            request.xml_response.info("added %s" % (logging_tools.get_plural("connection", num_ok)), logger)
        if num_error:
            request.xml_response.error("%s already existed" % (logging_tools.get_plural("connection", num_error)), logger)
        request.xml_response["result"] = new_entries

class remove_package(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        num_ok, num_error = (0, 0)
        for pdc_pk_s in _post.getlist("rem_list[]"):
            pdc_pk = int(pdc_pk_s.split("__")[1])
            try:
                cur_pdc = package_device_connection.objects.get(Q(pk=pdc_pk))
            except package_device_connection.DoesNotExist:
                num_error += 1
            else:
                cur_pdc.delete()
                num_ok += 1
        if num_ok:
            request.xml_response.info("%s removed" % (logging_tools.get_plural("connection", num_ok)), logger)
        if num_error:
            request.xml_response.error("%s not exists" % (logging_tools.get_plural("connection", num_error)), logger)

class change_target_state(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        cur_pdc = package_device_connection.objects.get(Q(pk=_post["pdc_key"].split("__")[1]))
        cur_pdc.target_state = _post["value"]
        cur_pdc.save()
        # signal package-server ?

class change_package_flag(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        cur_pdc = package_device_connection.objects.select_related("package").get(Q(pk=_post["pdc_key"].split("__")[1]))
        flag_name = _post["pdc_key"].split("__")[-1]
        # print flag_name
        value = True if int(_post["value"]) else False
        sflag_name = flag_name[:-5] if flag_name.endswith("_flag") else flag_name
        request.xml_response.info(
            "setting %s flag to %s for %s" % (
                sflag_name,
                "True" if value else "False",
                unicode(cur_pdc.package),
                ), logger)
        setattr(cur_pdc, flag_name, value)
        cur_pdc.save()
        # signal package-server ?

class get_pdc_status(View):
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        cur_pdc = package_device_connection.objects.get(Q(pk=_post["pdc_pk"]))
        request.xml_response["pdc_status"] = cur_pdc.response_str

class synchronize(View):
    @method_decorator(login_required)
    @method_decorator(xml_wrapper)
    def post(self, request):
        srv_com = server_command.srv_command(command="new_config")
        result = contact_server(request, "tcp://localhost:8007", srv_com, timeout=10, log_result=False)
        if result:
            # print result.pretty_print()
            request.xml_response.info("sent sync to server", logger)

