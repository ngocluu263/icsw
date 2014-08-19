{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

{% verbatim %}

running_table = """
<table class="table table-condensed table-hover table-striped" style="width:auto;">
    <thead>
        <tr>
            <td colspan="20" paginator entries="run_list" pag_settings="pagRun" per_page="20" paginator_filter="simple" paginator-epp="10,20,50,100,1000"></td>
        </tr>
        <tr headers struct="running_struct" class="info"></tr>
    </thead>
    <tbody>
        <tr rmsrunline ng-repeat-start="data in run_list | paginator2:this.pagRun" >
        </tr>
        <tr ng-repeat-end ng-show="data.files.value != '0' && running_struct.toggle['files']">
            <td colspan="99"><fileinfo job="data" files="files" fis="fis"></fileinfo></td>
        </tr>
    </tbody>
    <tfoot>
        <tr headertoggle ng-show="header_filter_set" struct="running_struct"></tr>
    </tfoot>
</table>
"""

waiting_table = """
<table class="table table-condensed table-hover table-striped" style="width:auto;">
    <thead>
        <tr>
            <td colspan="20" paginator entries="wait_list" pag_settings="pagWait" per_page="20" paginator_filter="simple" paginator-epp="10,20,50,100,1000"></td>
        </tr>
        <tr headers struct="waiting_struct" class="info"></tr>
    </thead>
    <tbody>
        <tr rmswaitline ng-repeat="data in wait_list | paginator2:this.pagWait"></tr>
    </tbody>
    <tfoot>
        <tr headertoggle ng-show="header_filter_set" struct="waiting_struct"></tr>
    </tfoot>
</table>
"""

done_table ="""
<table class="table table-condensed table-hover table-striped" style="width:auto;">
    <thead>
        <tr>
            <td colspan="20" paginator entries="done_list" pag_settings="pagDone" per_page="20" paginator_filter="simple" paginator-epp="10,20,50,100,1000"></td>
        </tr>
        <tr headers struct="done_struct" class="info"></tr>
    </thead>
    <tbody>
        <tr rmsdoneline ng-repeat="data in done_list | paginator2:this.pagDone"></tr>
    </tbody>
    <tfoot>
        <tr headertoggle ng-show="header_filter_set" struct="done_struct"></tr>
    </tfoot>
</table>
"""

node_table = """
<table class="table table-condensed table-hover" style="width:auto;">
    <thead>
        <tr>
            <td colspan="20" paginator entries="node_list" pag_settings="pagNode" per_page="20" paginator_filter="simple" paginator-epp="10,20,50,100,1000"></td>
        </tr>
        <tr headers struct="node_struct" class="info"></tr>
    </thead>
    <tbody>
        <tr rmsnodeline ng-repeat="data in node_list | paginator2:this.pagNode" ng-class="get_class(data)"></tr>
    </tbody>
    <tfoot>
        <tr headertoggle ng-show="header_filter_set" struct="node_struct"></tr>
    </tfoot>
</table>
"""

iostruct = """
    <h4>
        {{ io_struct.get_file_info() }}, 
        <input type="button" class="btn btn-sm btn-warning" value="close" ng-click="close_io(io_struct)"></input>
        <input type="button" ng-class="io_struct.update && 'btn btn-sm btn-success' || 'btn btn-sm'" value="update" ng_click="io_struct.update = !io_struct.update"></input>
    </h4>
    <div ng-show="io_struct.valid"> 
        <tt>
            <textarea ui-codemirror="editorOptions" ng-model="io_struct.text">
            </textarea>
        </tt>
    </div>
"""

headers = """
<th ng-repeat="entry in struct.display_headers()" colspan="{{ struct.get_span(entry) }}">{{ entry }}</th>
"""

header_toggle = """
<th colspan="{{ struct.headers.length }}">
    <form class="inline">
        <input
            ng-repeat="entry in struct.headers"
            type="button"
            ng-class="struct.get_btn_class(entry)"
            value="{{ entry }}"
            ng-click="struct.change_entry(entry)"
            ng-show="struct.header_not_hidden(entry)"
        ></input>
    </form>
</th>
"""

filesinfo = """
<div ng-repeat="file in jfiles">
    <div>
        <input
            type="button"
            ng-class="fis[file[0]].show && 'btn btn-xs btn-success' || 'btn btn-xs'"
            ng-click="fis[file[0]].show = !fis[file[0]].show"
            ng-value="fis[file[0]].show && 'hide' || 'show'"></input>
        {{ file[0] }}, {{ file[2] }} Bytes
    </div>
    <div ng-show="fis[file[0]].show">
        <textarea rows="{{ file[4] }}" cols="120" readonly="readonly">{{ file[1] }}</textarea>
    </div>
</div>
"""

rmsnodeline = """
<td ng-show="node_struct.toggle['host']">
    {{ data.host.value }}&nbsp;<button type="button" class="pull-right btn btn-xs btn-primary" ng-show="has_rrd(data.host)" ng-click="show_node_rrd($event, data)">
        <span class="glyphicon glyphicon-pencil"></span>
    </button>
</td>
<td ng-show="node_struct.toggle['queues']">
    <queuestate operator="rms_operator" host="data"></queuestate>
</td>
<td ng-show="node_struct.toggle['complex']">
    {{ data.complex.value }}
</td>
<td ng-show="node_struct.toggle['pe_list']">
    {{ data.pe_list.value }}
</td>
<td ng-show="node_struct.toggle['load']">
    <span ng-switch on="valid_load(data.load)">
        <span ng-switch-when="1">
            <div class="row">
                <div class="col-sm-3"><b>{{ data.load.value }}</b>&nbsp;</div>
                <div class="col-sm-9" style="width:140px; height:20px;">
                    <progressbar value="get_load(data.load)" animate="false"></progressbar>
                </div>
            </div>
        </span>
        <span ng-switch-when="0">
            <b>{{ data.load.value }}</b>
        </span>    
    </span>
</td>
<td ng-show="node_struct.toggle['slots_used']">
    <div ng-repeat="entry in data.load_vector" class="row">
         <div class="col-sm-12" style="width:140px; height:20px;">
             <progressbar max="entry[0]" value="entry[1]" animate="false" type="info"><span style="color:black;">{{ entry[1] }} / {{ entry[0] }}</span></progressbar>
         </div>
    </div>
</td>
<td ng-show="node_struct.toggle['slots_used']">
    {{ data.slots_used.value }}
</td>
<td ng-show="node_struct.toggle['slots_reserved']">
    {{ data.slots_reserved.value }}
</td>
<td ng-show="node_struct.toggle['slots_total']">
    {{ data.slots_total.value }}
</td>
<td ng-show="node_struct.toggle['jobs']">
    {{ data.jobs.value }}
</td>
"""

queuestateoper = """
<div ng-repeat="(queue, state) in get_states()" ng-show="queues_defined()" class="row">
    <div class="col-sm-12 btn-group">
        <button type="button" class="btn btn-xs dropdown-toggle" ng-class="get_queue_class(state, 'btn')" data-toggle="dropdown">
            {{ queue }} : {{ state }} <span class="caret"></span>
        </button>
        <ul class="dropdown-menu">
            <li ng-show="enable_ok(state)" ng-click="queue_control('enable', queue)">
                <a href="#">Enable {{ queue }}@{{ host.host.value }}</a>
            </li>
            <li ng-show="disable_ok(state)" ng-click="queue_control('disable', queue)">
                <a href="#">Disable {{ queue }}@{{ host.host.value }}</a>
            </li>
            <li ng-show="clear_error_ok(state)" ng-click="queue_control('clear_error', queue)">
                <a href="#">Clear error on {{ queue }}@{{ host.host.value }}</a>
            </li>
        </ul>
    </div>
</div>
<span ng-show="!queues_defined()">
    N/A
</span>
"""

queuestate = """
<div>
    <span class="label" ng-class="get_queue_class(state, 'label')" ng-repeat="(queue, state) in get_states()">
        {{ queue }} : {{ state }}
    </span>
</div>    
"""

jobactionoper = """
<div>
    <div class="btn-group">
        <button type="button" class="btn btn-xs dropdown-toggle btn-primary" data-toggle="dropdown">
            Action <span class="caret"></span>
        </button>
        <ul class="dropdown-menu">
            <li ng-click="job_control('delete', false)">
                <a href="#">Delete</a>
            </li>
            <li ng-click="job_control('delete', true)">
                <a href="#">force Delete</a>
            </li>
        </ul>
    </div>
</div>
"""

jobaction = """
<div>
---
</div>
"""

rmsdoneline = """
<td ng-show="done_struct.toggle['job_id']">
    {{ data.rms_job.jobid }}&nbsp;<button type="button" class="pull-right btn btn-xs btn-primary" ng-show="has_rrd(data)" ng-click="show_done_rrd($event, data)">
        <span class="glyphicon glyphicon-pencil"></span>
    </button>
</td>
<td ng-show="done_struct.toggle['task_id']">
    {{ data.rms_job.taskid }}
</td>
<td ng-show="done_struct.toggle['name']">
    {{ data.rms_job.name }}
</td>
<td ng-show="done_struct.toggle['granted_pe']">
    {{ data.granted_pe }}<span ng-show="data.granted_pe">({{ data.slots }})</span>
</td>
<td ng-show="done_struct.toggle['owner']">
    {{ data.rms_job.owner }}
</td>
<td ng-show="done_struct.toggle['queue_time']">
    {{ get_datetime(data.rms_job.queue_time) }}
</td>
<td ng-show="done_struct.toggle['start_time']">
    {{ get_datetime(data.start_time) }}
</td>
<td ng-show="done_struct.toggle['end_time']">
    {{ get_datetime(data.end_time) }}
</td>
<td ng-show="done_struct.toggle['queue']">
    {{ data.rms_queue.name }}
</td>
<td ng-show="done_struct.toggle['exit_status']">
    {{ data.exit_status }} {{ data.exit_status_str }}
</td>
<td ng-show="done_struct.toggle['failed']">
    {{ data.failed }} {{ data.failed_str }}
</td>
<td ng-show="done_struct.toggle['nodelist']">
    {{ show_pe_info(data) }}
</td>
"""

rmswaitline = """
<td ng-show="waiting_struct.toggle['job_id']">
    {{ data.job_id.value }}
</td>
<td ng-show="waiting_struct.toggle['task_id']">
    {{ data.task_id.value }}
</td>
<td ng-show="waiting_struct.toggle['name']">
    {{ data.name.value }}
</td>
<td ng-show="waiting_struct.toggle['requested_pe']">
    {{ data.requested_pe.value }}
</td>
<td ng-show="waiting_struct.toggle['owner']">
    {{ data.owner.value }}
</td>
<td ng-show="waiting_struct.toggle['state']">
    <b>{{ data.state.value }}</b>
</td>
<td ng-show="waiting_struct.toggle['complex']">
    {{ data.complex.value }}
</td>
<td ng-show="waiting_struct.toggle['queue']">
    {{ data.queue.value }}
</td>
<td ng-show="waiting_struct.toggle['queue_time']">
    {{ data.queue_time.value }}
</td>
<td ng-show="waiting_struct.toggle['wait_time']">
    {{ data.wait_time.value }}
</td>
<td ng-show="waiting_struct.toggle['left_time']">
    {{ data.left_time.value }}
</td>
<td ng-show="waiting_struct.toggle['priority']">
    {{ data.priority.value }}
</td>
<td ng-show="waiting_struct.toggle['depends']">
    {{ data.depends.value || '---' }}
</td>
<td ng-show="waiting_struct.toggle['action']">
    <jobaction job="data" operator="rms_operator"></jobaction>
</td>
"""

rmsrunline = """
<td ng-show="running_struct.toggle['job_id']">
    {{ data.job_id.value }}&nbsp;<button type="button" class="btn btn-xs btn-primary" ng-show="has_rrd(data.nodelist)" ng-click="show_job_rrd($event, data)">
        <span class="glyphicon glyphicon-pencil"></span>
    </button>
</td>
<td ng-show="running_struct.toggle['task_id']">
    {{ data.task_id.value }}
</td>
<td ng-show="running_struct.toggle['name']">
    {{ data.name.value }}
</td>
<td ng-show="running_struct.toggle['real_user']">
    {{ data.real_user.value }}
</td>
<td ng-show="running_struct.toggle['granted_pe']">
    {{ data.granted_pe.value }}
</td>
<td ng-show="running_struct.toggle['owner']">
    {{ data.owner.value }}
</td>
<td ng-show="running_struct.toggle['state']">
    <b>{{ data.state.value }}</b>
</td>
<td ng-show="running_struct.toggle['complex']">
    {{ data.complex.value }}
</td>
<td ng-show="running_struct.toggle['queue_name']">
    {{ data.queue_name.value }}
</td>
<td ng-show="running_struct.toggle['start_time']">
    {{ data.start_time.value }}
</td>
<td ng-show="running_struct.toggle['run_time']">
    {{ data.run_time.value }}
</td>
<td ng-show="running_struct.toggle['left_time']">
    {{ data.left_time.value }}
</td>
<td ng-show="running_struct.toggle['load']">
    {{ data.load.value }}
</td>
<td ng-show="running_struct.toggle['stdout']">
    <span ng-switch on="valid_file(data.stdout.value)">
        <input type="button" ng-class="get_io_link_class(data, 'stdout')" ng-value="data.stdout.value" ng-click="activate_io(data, 'stdout')"></input>
    </span>
</td>
<td ng-show="running_struct.toggle['stderr']">
    <span ng-switch on="valid_file(data.stderr.value)">
        <input type="button" ng-class="get_io_link_class(data, 'stderr')" ng-value="data.stderr.value" ng-click="activate_io(data, 'stderr')"></input>
    </span>
</td>
<td ng-show="running_struct.toggle['files']">
    {{ data.files.value }}
</td>
<td ng-show="running_struct.toggle['nodelist']">
    {{ get_nodelist(data) }}
</td>
<td ng-show="running_struct.toggle['action']">
    <jobaction job="data" operator="rms_operator"></jobaction>
</td>
"""

{% endverbatim %}

rms_module = angular.module("icsw.rms", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular", "ui.codemirror"])

angular_module_setup([rms_module])

LOAD_RE = /(\d+.\d+).*/

class header_struct
    constructor: (@table, header_struct, @hidden_headers) ->
        _dict = {}
        @headers = []
        @attributes = {}
        for entry in header_struct
            @headers.push(entry[0])
            @attributes[entry[0]] = entry[1]
            _dict[entry[0]] = true
        @toggle = _dict
        @build_cache()
    set_disabled : (in_list) =>
        for entry in in_list
            @toggle[entry] = false
        @build_cache()
    build_cache : () =>
        _c = []
        for entry in @headers
            if @toggle[entry]
                _c.push([true, entry])
            else
                _c.push([false, entry])
        @togglec = _c
    change_entry : (entry) =>
        @toggle[entry] = ! @toggle[entry]
        call_ajax
            url      : "{% url 'rms:set_user_setting' %}"
            dataType : "json"
            data:
                "data" : angular.toJson({"table" : @table, "row" : entry, "enabled" : @toggle[entry]})
            success  : (json) =>
        @build_cache()
    display_headers : () =>
        return (v[0] for v in _.zip.apply(null, [@headers, @togglec]) when v[1][0] and v[0] not in @hidden_headers)
    add_headers : (data) =>
        # get display list
        return ([v[1][1], v[0]] for v in _.zip.apply(null, [data, @togglec]))
    display_data : (data) =>
        # get display list
        return (v[0] for v in _.zip.apply(null, [data, @togglec]) when v[1][0])
    get_btn_class : (entry) ->
        if @toggle[entry]
            return "btn btn-sm btn-success"
        else
            return "btn btn-sm"
    map_headers : (simple_list) =>
        return (_.zipObject(@headers, _line) for _line in simple_list)
    header_not_hidden : (entry) ->
        return entry not in @hidden_headers
    get_span: (entry) ->
        if @attributes[entry].span?
            return @attributes[entry].span
        else
            return 1
        
class io_struct
    constructor : (@job_id, @task_id, @type) ->
        @resp_xml = undefined
        @text = ""
        # is set to true as soon as we got any data
        @valid = false
        @waiting = true
        @refresh = 0
        @update = true
    get_name : () =>
        if @task_id
            return "#{@job_id}.#{@task_id} (#{@type})"
        else
            return "#{@job_id} (#{@type})"
    get_id : () ->
        return "#{@job_id}.#{@task_id}.#{@type}"
    file_name : () ->
        return @resp_xml.attr("name")
    file_lines : () ->
        return @resp_xml.attr("lines")
    file_size : () ->
        return @resp_xml.attr("size_str")
    get_file_info : () ->
        if @valid
            return "File " + @file_name() + " (" + @file_size() + " in " + @file_lines() + " lines)"
        else if @waiting
            return "waiting for data"
        else
            return "nothing found"
    feed : (xml) => 
        @waiting = false
        found_xml = $(xml).find("response file_info[id='" + @get_id() + "']")
        if found_xml.length
            @valid = true
            @resp_xml = found_xml
            if @text != @resp_xml.text()
                @text = @resp_xml.text()
                @refresh++
        else
            @update = false
            @refresh++
          
rms_module.value('ui.config', {
    codemirror : {
        mode : 'text/x-php'
        lineNumbers: true
        matchBrackets: true
    }
})

class device_info
    constructor: (@name, in_list) ->
        @pk = in_list[0]
        @has_rrd = in_list[1]
        # not needed right now?
        @full_name = in_list[2]

class slot_info
    constructor: () ->
        @reset()
    reset: () =>
        @total = 0
        @used = 0
        @reserved = 0
    feed_vector: (in_vec) =>
        @total += in_vec[0]
        @used += in_vec[1]
        @reserved += in_vec[2]
        
DT_FORM = "D. MMM YYYY, HH:mm:ss"

rms_module.controller("rms_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service", "$timeout", "$sce", 
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service, $timeout, $sce) ->
        access_level_service.install($scope)
        $scope.rms_headers = {{ RMS_HEADERS | safe }}
        $scope.pagRun = paginatorSettings.get_paginator("run", $scope)
        $scope.pagWait = paginatorSettings.get_paginator("wait", $scope)
        $scope.pagDone = paginatorSettings.get_paginator("done", $scope)
        $scope.pagNode = paginatorSettings.get_paginator("node", $scope)
        $scope.header_filter_set = false
        $scope.editorOptions = {
            lineWrapping : false
            lineNumbers : true
            readOnly : true
            styleActiveLine: true
            indentUnit : 4
        }
        $scope.io_dict = {}
        $scope.io_list = []
        $scope.run_list = []
        $scope.wait_list = []
        $scope.node_list = []
        $scope.done_list = []
        $scope.device_dict = {}
        $scope.device_dict_set = false
        # slot info
        $scope.slot_info = new slot_info()
        $scope.running_slots = 0
        $scope.waiting_slots = 0
        # set to false to avoid destroying of subscopes (graphs)
        $scope.refresh = true
        # fileinfostruct
        $scope.fis = {}
        $scope.running_struct = new header_struct("running", $scope.rms_headers.running_headers, [])
        $scope.waiting_struct = new header_struct("waiting", $scope.rms_headers.waiting_headers, [])
        $scope.done_struct = new header_struct("done", $scope.rms_headers.done_headers, [])
        $scope.node_struct = new header_struct("node", $scope.rms_headers.node_headers, ["state"])
        $scope.rms_operator = false
        $scope.structs = {
            "running" : $scope.running_struct
            "waiting" : $scope.waiting_struct
            "done" : $scope.done_struct
            "node" : $scope.node_struct
        }
        $scope.$on("icsw.disable_refresh", () ->
            $scope.refresh = false
        )
        $scope.$on("icsw.enable_refresh", () ->
            $scope.refresh = true
        )
        $scope.reload = () ->
            $scope.rms_operator = $scope.acl_modify(null, "backbone.user.rms_operator")
            if $scope.update_info_timeout
                $timeout.cancel($scope.update_info_timeout)
            # refresh every 10 seconds
            $scope.update_info_timeout = $timeout($scope.reload, 10000)
            if $scope.refresh
                call_ajax
                    url      : "{% url 'rms:get_rms_json' %}"
                    dataType : "json"
                    success  : (json) =>
                        $scope.$apply(() ->
                            # reset counter
                            $scope.running_slots = 0
                            $scope.waiting_slots = 0
                            $scope.files = json.files
                            $scope.run_list = $scope.running_struct.map_headers(json.run_table)
                            $scope.wait_list = $scope.waiting_struct.map_headers(json.wait_table)
                            $scope.node_list = $scope.node_struct.map_headers(json.node_table)
                            $scope.done_list = json.done_table
                            # calculate max load
                            valid_loads = (parseFloat(entry.load.value) for entry in $scope.node_list when entry.load.value.match(LOAD_RE))
                            if valid_loads.length
                                $scope.max_load = _.max(valid_loads)
                                # round to next multiple of 4
                                $scope.max_load = 4 * parseInt(($scope.max_load + 3.9999  ) / 4)
                            else
                                $scope.max_load = 4
                            if $scope.max_load == 0
                                $scope.max_load = 4
                            $scope.slot_info.reset()
                            for entry in $scope.node_list
                                _total = (parseInt(_val) for _val in entry.slots_total.value.split("/"))
                                _used = (parseInt(_val) for _val in entry.slots_used.value.split("/"))
                                _reserved = (parseInt(_val) for _val in entry.slots_reserved.value.split("/"))
                                _size = _.max([_total.length, _used.length, _reserved.length])
                                if _total.length < _size
                                    _total = (_total[0] for _idx in _.range(_size))
                                if _used.length < _size
                                    _used = (_used[0] for _idx in _.range(_size))
                                if _reserved.length < _size
                                    _reserved = (_reserved[0] for _idx in _.range(_size))
                                entry.load_vector = _.zip(_total, _used, _reserved)
                                for _lv in entry.load_vector
                                    $scope.slot_info.feed_vector(_lv)
                            # get slot info
                            for _job in $scope.run_list
                                if _job.granted_pe.value == "-"
                                    $scope.running_slots += 1
                                else
                                    $scope.running_slots += parseInt(_job.granted_pe.value.split("(")[1].split(")")[0])
                            for _job in $scope.wait_list
                                if _job.requested_pe.value == "-"
                                    $scope.waiting_slots += 1
                                else
                                    $scope.waiting_slots += parseInt(_job.requested_pe.value.split("(")[1].split(")")[0])
                        )
                        if not $scope.device_dict_set
                            node_names = (entry[0].value for entry in json.node_table)
                            $scope.device_dict_set = true
                            call_ajax
                                url      : "{% url 'rms:get_node_info' %}"
                                data     :
                                    devnames : angular.toJson(node_names)
                                dataType : "json"
                                success  : (json) =>
                                    $scope.$apply(() ->
                                        for name of json
                                            _new_di = new device_info(name, json[name])
                                            $scope.device_dict[name] = _new_di
                                            $scope.device_dict[_new_di.pk] = _new_di
                                    )
                        # fetch file ids
                        fetch_list = []
                        for _id in $scope.io_list
                            if $scope.io_dict[_id].update
                                fetch_list.push($scope.io_dict[_id].get_id())
                        if fetch_list.length
                            call_ajax
                                url     : "{% url 'rms:get_file_content' %}"
                                data    :
                                    "file_ids" : angular.toJson(fetch_list)
                                success : (xml) =>
                                    parse_xml_response(xml)
                                    xml = $(xml)
                                    for _id in $scope.io_list
                                        $scope.io_dict[_id].feed(xml)
                                    $scope.$digest()
        $scope.get_io_link_class = (job, io_type) ->
            io_id = "#{job.job_id.value}.#{job.task_id.value}.#{io_type}"
            if io_id in $scope.io_list
                return "btn btn-xs btn-success"
            else
                return "btn btn-xs"
        $scope.activate_io = (job, io_type) ->
            io_id = "#{job.job_id.value}.#{job.task_id.value}.#{io_type}"
            if io_id not in $scope.io_list
                # create new tab
                $scope.io_list.push(io_id)
                $scope.io_dict[io_id] = new io_struct(job.job_id.value, job.task_id.value, io_type)
            # activate tab
            $scope.io_dict[io_id].active = true
            # reload
            $scope.reload()
        $scope.close_io = (io_struct) ->
            $scope.io_list = (entry for entry in $scope.io_list when entry != io_struct.get_id())
            delete $scope.io_dict[io_struct.get_id()]
        $scope.$on("queue_control", (event, host, command, queue) ->
            call_ajax
                url      : "{% url 'rms:control_queue' %}"
                data     : {
                    "queue"   : queue
                    "host"    : host.host.value
                    "command" : command 
                }
                success  : (xml) =>
                    parse_xml_response(xml)
        )
        $scope.$on("job_control", (event, job, command, force) ->
            call_ajax
                url      : "{% url 'rms:control_job' %}"
                data     : {
                    "job_id"  : job.job_id.value
                    "task_id" : job.task_id.value
                    "command" : command 
                }
                success  : (xml) =>
                    parse_xml_response(xml)
        )
        $scope.get_running_info = () ->
            return "running (#{$scope.run_list.length} jobs, #{$scope.running_slots} slots)"
        $scope.get_waiting_info = () ->
            return "waiting (#{$scope.wait_list.length} jobs, #{$scope.waiting_slots} slots)"
        $scope.get_done_info = () ->
            return "done (#{$scope.done_list.length} jobs)"
        $scope.get_node_info = () ->
            return "node (#{$scope.node_list.length} nodes, #{$scope.slot_info.used} of #{$scope.slot_info.total} slots used)"
        $scope.show_rrd = (event, name_list, start_time, end_time) ->
            dev_pks = ($scope.device_dict[name].pk for name in name_list).join(",")
            start_time = if start_time then start_time else 0
            end_time = if end_time then end_time else 0
            rrd_txt = """
<div class="panel panel-default">
    <div class="panel-body">
        <h2>Device #{name}</h2>
        <div ng-controller='rrd_ctrl'>
            <rrdgraph
                devicepk='#{dev_pks}'
                selectkeys="load.*,net.all.*,mem.used.phys$,^swap.*"
                draw="1"
                mergedevices="0"
                graphsize="240x100"
                fromdt="#{start_time}"
                todt="#{end_time}"
            >
            </rrdgraph>
        </div>
    </div>
</div>
"""
            # disable refreshing
            $scope.refresh = false
            $scope.rrd_div = angular.element(rrd_txt)
            $compile($scope.rrd_div)($scope)
            $scope.rrd_div.simplemodal
                opacity      : 50
                position     : [event.pageY, event.pageX]
                autoResize   : true
                autoPosition : true
                minWidth     : "1280px"
                minHeight   : "800px"
                onShow: (dialog) -> 
                    dialog.container.draggable()
                    #$("#simplemodal-container").css("height", "auto")
                    #$("#simplemodal-container").css("width", "auto")
                onClose: =>
                    # destroy scopes
                    $scope.refresh = true
                    $.simplemodal.close()
        call_ajax
            url      : "{% url 'rms:get_user_setting' %}"
            dataType : "json"
            success  : (json) =>
                for key, value of json
                    $scope.structs[key].set_disabled(value)
                $scope.$apply(() ->
                    $scope.header_filter_set = true
                )
                $scope.reload()
]).directive("running", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("running_table.html")
        link : (scope, el, attrs) ->
            if "filter" of attrs
                scope.pagRun.conf.filter = attrs["filter"]
    }
).directive("waiting", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("waiting_table.html")
        link : (scope, el, attrs) ->
            if "filter" of attrs
                scope.pagRun.conf.filter = attrs["filter"]
    }
).directive("done", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("done_table.html")
        link : (scope, el, attrs) ->
            if "filter" of attrs
                scope.pagRun.conf.filter = attrs["filter"]
    }
).directive("node", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("node_table.html")
        link : (scope, el, attrs) ->
            scope.get_class = (data) ->
                parts = data.state.raw.join("").split("")
                if _.indexOf(parts, "a") >= 0 or _.indexOf(parts, "u") >= 0
                    return "danger"
                else if _.indexOf(parts, "d") >= 0
                    return "warning"
                else
                    return ""
    }
).directive("iostruct", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("iostruct.html")
        link : (scope, el, attrs) ->
    }
).directive("headers", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("headers.html")
        scope:
            struct : "="
        link : (scope, el, attrs) ->
    }
).directive("rmsdoneline", ($templateCache, $sce) ->
    return {
        restrict : "EA"
        template : $templateCache.get("rmsdoneline.html")
        link : (scope, el, attrs) ->
            scope.struct_name = attrs["struct"]
            scope.get_datetime = (dt) ->
                if dt
                    return moment.unix(dt).format(DT_FORM)
                else
                    return "---"
            scope.get_display_data = (data) ->
                return scope[scope.struct_name].display_data(data)
            scope.show_pe_info = (data) ->
                if data.rms_pe_info.length
                    r_list = []
                    for _entry in data.rms_pe_info
                        r_list.push("#{_entry.hostname} (#{_entry.slots})")
                    return r_list.join(",")
                else
                    if data.device of scope.device_dict
                        return scope.device_dict[data.device].full_name
                    else
                        return "---"
            scope.has_rrd = (data) ->
                if data.rms_pe_info.length
                    any_rrd = false
                    for _entry in data.rms_pe_info
                        if _entry.device of scope.device_dict
                            if scope.device_dict[_entry.device].has_rrd
                                any_rrd = true
                    return any_rrd
                else
                    if data.device of scope.device_dict
                        return scope.device_dict[data.device].has_rrd
                    else
                        return false    
            scope.get_rrd_nodes = (nodelist) ->
                rrd_nodes = (scope.device_dict[entry].name for entry in nodelist when entry of scope.device_dict and scope.device_dict[entry].has_rrd)
                return rrd_nodes
            scope.show_done_rrd = (event, data) ->
                if data.rms_pe_info.length
                    nodelist = (entry.device for entry in data.rms_pe_info)
                else
                    nodelist = [data.device]
                rrd_nodes = scope.get_rrd_nodes(nodelist)
                scope.show_rrd(event, rrd_nodes, data.start_time, data.end_time)
                
    }
).directive("rmswaitline", ($templateCache, $sce) ->
    return {
        restrict : "EA"
        template : $templateCache.get("rmswaitline.html")
        link : (scope, el, attrs) ->
            scope.struct_name = attrs["struct"]
            scope.get_display_data = (data) ->
                return scope[scope.struct_name].display_data(data)
    }
).directive("rmsrunline", ($templateCache, $sce) ->
    return {
        restrict : "EA"
        template : $templateCache.get("rmsrunline.html")
        link : (scope, el, attrs) ->
            scope.valid_file = (std_val) ->
                # to be improved, transfer raw data (error = -1, 0 = no file, > 0 = file with content)
                if std_val == "---" or std_val == "err" or std_val == "error" or std_val == "0 B"
                    return 0
                else
                    return 1
            scope.get_nodelist = (job) ->
                nodes = job.nodelist.value.split(",")
                r_list = []
                _.forEach(_.countBy(nodes), (key, value) ->
                    if key == 1
                        r_list.push(value)
                    else
                        r_list.push("#{value}(#{key})")
                )
                return r_list.join(",")
            scope.get_rrd_nodes = (nodelist) ->
                rrd_nodes = (entry for entry in nodelist.devs when entry of scope.device_dict and scope.device_dict[entry].has_rrd)
                return rrd_nodes
            scope.has_rrd = (nodelist) ->
                rrd_nodes = scope.get_rrd_nodes(nodelist.raw)
                return if rrd_nodes.length then true else false
            scope.show_job_rrd = (event, job) ->
                rrd_nodes = scope.get_rrd_nodes(job.nodelist.raw)
                scope.show_rrd(event, rrd_nodes, job.start_time.raw, undefined)
    }
).directive("rmsnodeline", ($templateCache, $sce, $compile) ->
    return {
        restrict : "EA"
        template : $templateCache.get("rmsnodeline.html")
        link : (scope, el, attrs) ->
            scope.valid_load = (load) ->
                # return 1 or 0, not true or false
                return if load.value.match(LOAD_RE) then 1 else 0
            scope.get_load = (load) ->
                cur_m = load.value.match(LOAD_RE)
                if cur_m
                    return String((100 * parseFloat(load.value)) / scope.max_load)
                else
                    return 0
            scope.has_rrd = (name) ->
                if name.value of scope.device_dict
                    return scope.device_dict[name.value].has_rrd
                else
                    return false
            scope.show_node_rrd = (event, node) ->
                scope.show_rrd(event, [node.host.value], undefined, undefined)
    }
).directive("headertoggle", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("header_toggle.html")
        scope:
            struct : "="
        link : (scope, el, attrs) ->
    }
).directive("jobaction", ($compile, $templateCache) ->
    return {
        restrict : "EA"
        #template : $templateCache.get("queue_state.html")
        scope:
            job : "="
            operator : "="
        replace : true
        compile : (tElement, tAttr) ->
            return (scope, el, attrs) ->
                scope.job_control = (command, force) ->
                    scope.$emit("job_control", scope.job, command, force)
                if scope.operator
                    is_oper = true
                else if scope.job.real_user == '{{ user.login }}'
                    is_oper = true
                else
                    is_oper = false
                el.append($compile($templateCache.get(if is_oper then "job_action_oper.html" else "job_action.html"))(scope))
      
    }
).directive("queuestate", ($compile, $templateCache) ->
    return {
        restrict : "EA"
        #template : $templateCache.get("queue_state.html")
        scope:
            host : "="
            operator : "="
        replace : true
        compile : (tElement, tAttr) ->
            return (scope, el, attrs) ->
                scope.get_states = () ->
                    states = scope.host.state.value.split("/")
                    queues = scope.host.queues.value.split("/")
                    if queues.length != states.length
                        states = (states[0] for queue in queues)
                    return _.zipObject(queues, states)
                scope.queues_defined = () ->
                    return if scope.host.state.value.length then true else false
                scope.enable_ok = (state) ->
                    return if state.match(/d/g) then true else false
                scope.disable_ok = (state) ->
                    return if not state.match(/d/g) then true else false
                scope.clear_error_ok = (state) ->
                    return if state.match(/e/gi) then true else false
                scope.get_queue_class = (state, prefix) ->
                    if state.match(/a|u/gi)
                        return "#{prefix}-danger"
                    else if state.match(/d/gi)
                        return "#{prefix}-warning"
                    else
                        return "#{prefix}-success"
                scope.queue_control = (command, queue) ->
                    scope.$emit("queue_control", scope.host, command, queue)
                el.append($compile($templateCache.get(if scope.operator then "queue_state_oper.html" else "queue_state.html"))(scope))
      
    }
).directive("fileinfo", ($compile, $templateCache) ->
    return {
        restrict : "EA"
        scope:
            job   : "="
            files : "="
            fis   : "="
        template : $templateCache.get("files_info.html")
        link : (scope, el, attrs) ->
            full_id = if scope.job.task_id then "#{scope.job.job_id}.#{scope.job.task_id}" else scope.job.job_id
            scope.full_id = full_id
            if full_id of scope.files
                scope.jfiles = scope.files[full_id]
                for file in scope.jfiles
                    if not scope.fis[file[0]]?
                        scope.fis[file[0]] = {
                            "show" : true
                        }
            else
                scope.jfiles = []
    }
).run(($templateCache) ->
    $templateCache.put("running_table.html", running_table)
    $templateCache.put("waiting_table.html", waiting_table)
    $templateCache.put("done_table.html", done_table)
    $templateCache.put("node_table.html", node_table)
    $templateCache.put("headers.html", headers)
    $templateCache.put("rmswaitline.html", rmswaitline)
    $templateCache.put("rmsdoneline.html", rmsdoneline)
    $templateCache.put("rmsrunline.html", rmsrunline)
    $templateCache.put("rmsnodeline.html", rmsnodeline)
    $templateCache.put("header_toggle.html", header_toggle)
    $templateCache.put("iostruct.html", iostruct)
    $templateCache.put("queue_state_oper.html", queuestateoper)
    $templateCache.put("queue_state.html", queuestate)
    $templateCache.put("job_action_oper.html", jobactionoper)
    $templateCache.put("job_action.html", jobaction)
    $templateCache.put("files_info.html", filesinfo)
)

add_rrd_directive(rms_module)

{% endinlinecoffeescript %}

</script>

