# rms views

from django.http import HttpResponse
from init.cluster.frontend import render_tools
from init.cluster.frontend.helper_functions import init_logging, logging_pool
from django.conf import settings
import json
import sge_tools
import threading
from lxml import etree

class tl_sge_info(sge_tools.sge_info):
    # sge_info object with thread lock layer
    def __init__(self):
        self.lock = threading.Lock()
        self.__logger = logging_pool.get_logger("sge_info")
        sge_tools.sge_info.__init__(
            self,
            server="127.0.0.1",
            default_pref=["server"],
            never_direct=True,
            initial_update=False,
            log_command=self.__logger.log,
            verbose=settings.DEBUG
        )
    def update(self):
        self.lock.acquire()
        try:
            sge_tools.sge_info.update(self)
            sge_tools.sge_info.build_luts(self)
        finally:
            self.lock.release()

my_sge_info = tl_sge_info()

def get_job_options(request):
    return sge_tools.get_empty_job_options()

def get_node_options(request):
    return sge_tools.get_empty_node_options(merge_node_queue=True)

@init_logging
def overview(request):
    return render_tools.render_me(request, "rms_overview.html", {
        "run_job_headers"  : sge_tools.get_running_headers(get_job_options(request)),
        "wait_job_headers" : sge_tools.get_waiting_headers(get_job_options(request)),
        "node_headers"     : sge_tools.get_node_headers(get_node_options(request))
    })()

def _node_to_value(in_node):
    if in_node.get("type", "string") == "float":
        return float(in_node.text)
    else:
        return in_node.text
    
def _value_to_str(in_value):
    if type(in_value) == float:
        return "%.2f" % (in_value)
    else:
        return in_value
    
def _sort_list(in_list, _post):
    #for key in sorted(_post):
    #    print key, _post[key]
    start_idx = int(_post["iDisplayStart"])
    num_disp  = int(_post["iDisplayLength"])
    total_data_len = len(in_list)
    # interpet nodes according to optional type attribute, TODO: use format from attrib to reformat later
    in_list = [[_node_to_value(sub_node) for sub_node in row] for row in in_list]
    s_str = _post.get("sSearch", "").strip()
    if s_str:
        in_list = [row for row in in_list if any([cur_text.count(s_str) for cur_text in row])]
    filter_data_len = len(in_list)
    for sort_key in [key for key in _post.keys() if key.startswith("sSortDir_")]:
        sort_dir = _post[sort_key]
        sort_idx = int(_post["iSortCol_%s" % (sort_key.split("_")[-1])])
        if sort_dir == "asc":
            in_list = sorted(in_list, cmp=lambda x,y: cmp(x[sort_idx], y[sort_idx]))
        else:
            in_list = sorted(in_list, cmp=lambda x,y: cmp(y[sort_idx], x[sort_idx]))
    # reformat
    show_list = [[_value_to_str(value) for value in line] for line in in_list[start_idx : start_idx + num_disp]]
    return {"sEcho"                : int(_post["sEcho"]),
            "iTotalRecords"        : total_data_len,
            "iTotalDisplayRecords" : filter_data_len,
            "aaData"               : show_list}

@init_logging
def get_run_jobs_xml(request):
    _post = request.POST
    my_sge_info.update()
    run_job_list  = sge_tools.build_running_list(my_sge_info, get_job_options(request))
    json_resp = _sort_list(run_job_list, _post)
    return HttpResponse(json.dumps(json_resp), mimetype="application/json")

@init_logging
def get_wait_jobs_xml(request):
    _post = request.POST
    my_sge_info.update()
    wait_job_list  = sge_tools.build_waiting_list(my_sge_info, get_job_options(request))
    json_resp = _sort_list(wait_job_list, _post)
    return HttpResponse(json.dumps(json_resp), mimetype="application/json")

@init_logging
def get_node_xml(request):
    _post = request.POST
    my_sge_info.update()
    node_list     = sge_tools.build_node_list(my_sge_info, get_node_options(request))
    json_resp = _sort_list(node_list, _post)
    return HttpResponse(json.dumps(json_resp), mimetype="application/json")
