{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

{% verbatim %}

catalog_table_template = """
<h2>{{ config_catalogs.length }} catalogs, <input type="button" class="btn btn-sm btn-success" value="create new catalog" ng-click="catalog_edit.create($event)"></input></h2>
<table class="table table-condensed table-hover table-bordered" style="width:auto;">
    <thead>
        <tr>
            <th>name</th>
            <th>URL</th>
            <th>Author</th>
            <th>Version</th>
            <th>#configs<th>
            <th colspan="2">action</th>
        </tr>
    </thead>
    <tbody>
        <tr ng-repeat="catalog in config_catalogs">
            <td>{{ catalog.name }}</td>
            <td>{{ catalog.url }}</td>
            <td>{{ catalog.author }}</td>
            <td>{{ catalog.version }}</td>
            <td>{{ get_num_configs(catalog) }}</td>
            <td><input type="button" class="btn btn-primary btn-sm" ng-click="edit_catalog(catalog, $event)" value="modify"></input></td>
            <td><input type="button" ng-show="get_num_configs(catalog) == 0" class="btn btn-danger btn-sm" ng-click="delete_catalog(catalog)" value="delete"></input></td>
        </tr>
    </tbody>
</table>
"""

config_table_template = """
<h2>{{ entries.length }} configurations, shown: {{ pagSettings.conf.filtered_len }},
    <input type="button" class="btn btn-sm btn-success" value="create new config" ng-click="config_edit.create($event)">
    </input>
    <span ng-show="selected_objects.length">
    , {{ selected_objects.length }} selected,
    <input type="button" class="btn btn-sm btn-warning" value="clear selection" ng-click="unselect_objects()"></input>
    <input type="button" class="btn btn-sm btn-danger" value="delete selected" ng-click="delete_selected_objects()"></input>
    </span>
</h2>
<table class="table table-condensed table-hover table-bordered" style="width:auto;">
    <thead>
        <tr>
            <td colspan="13">
                <div class="row" style="width:900px;">
                    <div class="col-sm-4">
                        <div class="input-group">
                            <input ng-model="pagSettings.conf.filter_settings.filter_str" class="form-control" placeholder="filter">
                            </input>
                            <span class="input-group-btn">
                                <button class="btn btn-danger" type="button" ng-click="clear_filter()"><span title="clear selection" class="glyphicon glyphicon-ban-circle"></span></button>
                            </span>
                        </div>
                    </div>
                    <div class="col-sm-3">
                        <div class="input-group btn-group">
                            <input type="button" ng-class="get_filter_class('name')" value="name" ng-click="change_filter_setting('name')"></input>
                            <input type="button" ng-class="get_filter_class('script')" value="script" ng-click="change_filter_setting('script')"></input>
                            <input type="button" ng-class="get_filter_class('var')" value="var" ng-click="change_filter_setting('var')"></input>
                            <input type="button" ng-class="get_filter_class('mon')" value="mon" ng-click="change_filter_setting('mon')"></input>
                        </div>
                    </div>
                    <div class="col-sm-5" paginator entries="entries" pag_settings="pagSettings" per_page="15" paginator_filter="func" paginator-epp="15,30,100,200" paginator_filter_func="filter_conf">
                    </div>
                </div>
            </td>
        </tr>
        <tr>
            <th>Name</th>
            <th>Pri</th>
            <th>Catalog</th>
            <th>enabled</th>
            <th>Description</th>
            <th>parent</th>
            <th>var</th>
            <th>script</th>
            <th>mon</th>
            <th>cats</th>
            <th colspan="3">action</th>
        </tr>
    </thead>
    <tbody>
        <tr ng-repeat-start="config in pagSettings.filtered_list.slice(pagSettings.conf.start_idx, pagSettings.conf.end_idx + 1)" ng-class="get_config_row_class(config)">
            <td>
                <span ng-show="config_has_info(config)" class="pull-right">
                    <span class="glyphicon glyphicon-info-sign" title="{{ get_config_help_text(config) }}">
                    </span>
                </span>
                {{ config.name }}
            </td>
            <td class="text-right">{{ config.priority }}</td>
            <td>{{ config.config_catalog | array_lookup:this.config_catalogs:'name':'-' }}</td>
            <td class="text-center">{{ config.enabled | yesno1 }}</td>
            <td>{{ config.description }}</td>
            <td>{{ show_parent_config(config) }}</td>
            <td class="text-center">
                <span ng-class="get_label_class(config, 'var')" ng-click="toggle_expand(config, 'var')">
                    <span ng_class="get_expand_class(config, 'var')">
                    </span>
                    {{ config.var_num }}
                </span>&nbsp;
            </td>
            <td class="text-center">
                <span ng-class="get_label_class(config, 'script')" ng-click="toggle_expand(config, 'script')">
                    <span ng_class="get_expand_class(config, 'script')">
                    </span>
                    {{ config.script_num }}
                </span>
            </td>
            <td class="text-center">
                <span ng-class="get_label_class(config, 'mon')" ng-click="toggle_expand(config, 'mon')">
                    <span ng_class="get_expand_class(config, 'mon')">
                    </span>
                    {{ config.mon_num }}
                </span>
            </td>
            <td class="text-center">{{ get_num_cats(config) }}</td>
            <td>
                <input type="button" class="btn btn-sm btn-success" value="modify" ng-click="config_edit.edit(config, $event)"></input>
            </td>
            <td>
                <div class="input-group-btn">
                    <div class="btn-group">
                        <button type="button" class="btn btn-warning btn-sm dropdown-toggle" data-toggle="dropdown">
                            Create <span class="caret"></span>
                        </button>
                        <ul class="dropdown-menu">
                            <li ng-click="create_script(config, $event)"><a href="#">Script</a></li>
                            <li class="divider"></li>
                            <li ng-click="create_var(config, 'str', $event)"><a href="#">String var</a></li>
                            <li ng-click="create_var(config, 'int', $event)"><a href="#">Integer var</a></li>
                            <li ng-click="create_var(config, 'bool', $event)"><a href="#">Bool var</a></li>
                            <li class="divider"></li>
                            <li ng-click="create_mon(config, $event)"><a href="#">Check command</a></li>
                        </ul>
                    </div>
                </div>
            </td>
            <td class="text-center">
                <span ng-if="config.usecount" class="text-warning">
                    refs: {{ config.usecount }}
                </span>
                <span ng-if="!config.usecount">
                    <input type="button" class="btn btn-sm btn-danger" value="delete" ng-click="config_edit.delete_obj(config)"></input>
                </span>
            </td>
        </tr>
        <tr ng-show="config.var_expanded">
            <td colspan="13">
                <vartable></vartable>
            </td>
        </tr>
        <tr ng-show="config.script_expanded">
            <td colspan="13">
                <scripttable></scripttable>
            </td>
        </tr>
        <tr ng-repeat-end ng-show="config.mon_expanded">
            <td colspan="13">
                <montable></montable>
            </td>
        </tr>
    </tbody>
</table>
"""

var_table_template = """
<table ng-if="config.var_expanded" class="table table-condensed table-hover">
    <thead>
        <tr>
            <th>Name</th>
            <th>value</th>
            <th>descr</th>
            <th>type</th>
            <th colspan="2">Action</th>
        </tr>
    </thead>
    <tbody>
        <tr ng-repeat="obj in get_config_vars(config)">
            <td>
                <span ng-show="var_has_info(config, obj)" class="pull-right">
                    <span class="glyphicon glyphicon-info-sign" title="{{ get_var_help_text(config, obj) }}">
                    </span>
                </span>
                {{ obj.name }}
            </td>
            <td>{{ obj.value }}</td>
            <td>{{ obj.description }}</td>
            <td>{{ obj.v_type }}</td>
            <td><input type="button" ng-class="obj._selected && 'btn btn-primary btn-xs' || 'btn btn-xs'" value="sel" ng-click="select_object(obj)"></input>
            <td><input type="button" class="btn btn-success btn-xs" ng-click="edit_var(config, obj, $event)" value="modify"></input></td>
            <td><input type="button" class="btn btn-danger btn-xs" ng-click="delete_var(config, obj)" value="delete"></input></td>
        </tr>
    </tbody>
</table>
"""

script_table_template = """
<table ng-if="config.script_expanded" class="table table-condensed table-hover">
    <thead>
        <tr>
            <th>Name</th>
            <th>value</th>
            <th>descr</th>
            <th>priority</th>
            <th>enabled</th>
            <th colspan="2">Action</th>
        </tr>
    </thead>
    <tbody>
        <tr ng-repeat="obj in config.config_script_set">
            <td>{{ obj.name }}</td>
            <td style="font-family:monospace; width:480px;">
                <textarea ng-model="obj.value" class="form-control input-sm" rows="5" readonly>
                </textarea>
            </td>
            <td>{{ obj.description }}</td>
            <td>{{ obj.priority }}</td>
            <td>{{ obj.enabled | yesno1 }}</td>
            <td><input type="button" ng-class="obj._selected && 'btn btn-primary btn-xs' || 'btn btn-xs'" value="sel" ng-click="select_object(obj)"></input>
            <td><input type="button" class="btn btn-success btn-xs" ng-click="edit_script(config, obj, $event)" value="modify"></input></td>
            <td><input type="button" class="btn btn-danger btn-xs" ng-click="delete_script(config, obj)" value="delete"></input></td>
        </tr>
    </tbody>
</table>
"""

mon_table_template = """
<table ng-if="config.mon_expanded" class="table table-condensed table-hover">
    <thead>
        <tr>
            <th>Name</th>
            <th>template</th>
            <th>description</th>
            <th>command line</th>
            <th>vol</th>
            <th>perf</th>
            <th>is event</th>
            <th>event handler</th>
            <th>eh enabled</th>
            <th>cats</th>
            <th colspan="2">Action</th>
        </tr>
    </thead>
    <tbody>
        <tr ng-repeat="obj in config.mon_check_command_set | orderBy:'name'">
            <td>{{ obj.name }}</td>
            <td>{{ obj.mon_service_templ | array_lookup:this.mon_service_templ:'name':'-' }}</td>
            <td>{{ obj.description }}</td>
            <td title="{{ obj.command_line }}">
                <input
                    type="button"
                    title="expand / collapse full command line"
                    ng-class="obj._show_full_command && 'btn btn-xs btn-success' || 'btn btn-xs btn-default'"
                    value="e" ng-click="obj._show_full_command = !obj._show_full_command">
                </input>
                <span ng-if="!obj._show_full_command">{{ obj.command_line | limit_text:60:true }}</span>
                <span ng-if="obj._show_full_command">{{ obj.command_line }}</span>
            </td>
            <td>{{ obj.volatile | yesno1 }}</td>
            <td>{{ obj.enable_perfdata | yesno1 }}</td>
            <td>{{ obj.is_event_handler | yesno1 }}</td>
            <td>{{ obj.event_handler }}</td>
            <td>{{ obj.event_handler_enabled }}</td>
            <td>{{ get_num_cats(obj) }}</td>
            <td><input type="button" ng-class="obj._selected && 'btn btn-primary btn-xs' || 'btn btn-xs'" value="sel" ng-click="select_object(obj)"></input>
            <td><input type="button" class="btn btn-success btn-xs" ng-click="edit_mon(config, obj, $event)" value="modify"></input></td>
            <td><input type="button" class="btn btn-warning btn-xs" ng-click="copy_mon(config, obj, $event)" value="duplicate"></input></td>
            <td><input type="button" class="btn btn-danger btn-xs" ng-click="delete_mon(config, obj)" value="delete"></input></td>
        </tr>
    </tbody>
</table>
"""

{% endverbatim %}

config_module = angular.module("icsw.config", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular", "ui.codemirror"])

angular_module_setup([config_module])

config_ctrl = config_module.controller("config_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal) ->
        $scope.pagSettings = paginatorSettings.get_paginator("config_list", $scope)
        $scope.selected_objects = []
        $scope.pagSettings.conf.filter_settings = {
            "filter_str" : ""
            "filter_name" : true
            "filter_script" : false
            "filter_var" : false
            "filter_mon" : false
        }
        $scope.editorOptions = {
            lineWrapping : false
            lineNumbers: true
            mode: 
                name : "python"
                version : 2
            matchBrackets: true
            # codemirror 3.x, not working for 4.x
            #minHeight : "200px"
            #width: "800px"
            #height: "600px"
            styleActiveLine: true
            indentUnit : 4
        }
        $scope.pagSettings.conf.filter_changed = (ps) ->
            cf = $scope.pagSettings.conf.filter_settings
            f_val = cf.filter_str 
            if  f_val == ""
                $scope.filter_re = new RegExp("", "gi")
            else
                try
                    $scope.filter_re = new RegExp(f_val, "gi")
                catch
                    $scope.filter_re = new RegExp("^$", "gi")
            if not cf.filter_name and not cf.filter_script and not cf.filter_var and not cf.filter_mon
                cf.filter_name = true
        $scope.entries = []
        $scope.config_catalogs = []
        $scope.get_filter_class = (name) ->
            if $scope.pagSettings.conf.filter_settings["filter_#{name}"]
                return "btn btn-sm btn-success"
            else
                return "btn btn-sm"
        $scope.change_filter_setting = (name) ->
            $scope.pagSettings.conf.filter_settings["filter_#{name}"] = ! $scope.pagSettings.conf.filter_settings["filter_#{name}"]
        # config edit
        $scope.config_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular)
        $scope.config_edit.create_template = "config_template.html"
        $scope.config_edit.edit_template = "config_template.html"
        $scope.config_edit.create_rest_url = Restangular.all("{% url 'rest:config_list'%}".slice(1))
        $scope.config_edit.modify_rest_url = "{% url 'rest:config_detail' 1 %}".slice(1).slice(0, -2)
        $scope.config_edit.create_list = $scope.entries
        $scope.config_edit.new_object_at_tail = false
        $scope.config_edit.change_signal = "icsw.new_config"
        $scope.config_edit.new_object = (scope) ->
            new_obj = {
                "name" : "new config", "description" : "", "priority" : 0, "mon_check_command_set" : [], "config_script_set" : [],
                "config_str_set" : [], "config_int_set" : [], "config_blob_set" : [], "config_bool_set" : [], "enabled" : true,
                "parent_config" : undefined, "categories" : [],
                "config_catalog" : (entry.idx for entry in scope.config_catalogs)[0]
            }
            return new_obj
        # catalog edit
        $scope.catalog_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular, $q)
        $scope.catalog_edit.create_template = "config_catalog_template.html"
        $scope.catalog_edit.edit_template = "config_catalog_template.html"
        $scope.catalog_edit.create_rest_url = Restangular.all("{% url 'rest:config_catalog_list'%}".slice(1))
        $scope.catalog_edit.modify_rest_url = "{% url 'rest:config_catalog_detail' 1 %}".slice(1).slice(0, -2)
        $scope.catalog_edit.create_list = $scope.config_catalogs
        $scope.catalog_edit.new_object_at_tail = false
        $scope.catalog_edit.use_promise = true
        $scope.catalog_edit.new_object = (scope) ->
            new_obj = {
                "name" : "new catalog", "author" : "{{ request.user }}", "url" : "http://localhost/",
            }
            return new_obj
        $scope.var_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular, $q)
        $scope.var_edit.use_promise = true
        $scope.var_edit.new_object_at_tail = false
        $scope.script_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular, $q)
        $scope.script_edit.create_template = "config_script_template.html"
        $scope.script_edit.edit_template = "config_script_template.html"
        $scope.script_edit.create_rest_url = Restangular.all("{% url 'rest:config_script_list'%}".slice(1))
        $scope.script_edit.modify_rest_url = "{% url 'rest:config_script_detail' 1 %}".slice(1).slice(0, -2)
        $scope.script_edit.use_promise = true
        $scope.script_edit.new_object_at_tail = false
        $scope.script_edit.min_width = "1000px"
        $scope.mon_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular, $q)
        $scope.mon_edit.create_template = "mon_check_command_template.html"
        $scope.mon_edit.edit_template = "mon_check_command_template.html"
        $scope.mon_edit.create_rest_url = Restangular.all("{% url 'rest:mon_check_command_list'%}".slice(1))
        $scope.mon_edit.modify_rest_url = "{% url 'rest:mon_check_command_detail' 1 %}".slice(1).slice(0, -2)
        $scope.mon_edit.use_promise = true
        $scope.mon_edit.new_object_at_tail = false
        $scope.mon_edit.min_width = "820px"
        #$scope.config_edit.change_signal = "icsw.new_config"
        $scope.reload = () ->
            wait_list = [
                restDataSource.reload(["{% url 'rest:config_list' %}", {}]),
                restDataSource.reload(["{% url 'rest:mon_service_templ_list' %}", {}]),
                restDataSource.reload(["{% url 'rest:category_list' %}", {}]),
                restDataSource.reload(["{% url 'rest:config_catalog_list' %}", {}]),
                restDataSource.reload(["{% url 'rest:config_hint_list' %}", {}]),
            ]
            $q.all(wait_list).then((data) ->
                $scope.mon_service_templ = data[1]
                $scope.categories = data[2]
                #console.log data
                ($scope._set_fields(entry, true) for entry in data[0])
                $scope.entries = data[0]
                $scope.config_catalogs = data[3]
                $scope.config_edit.create_list = $scope.entries
                $scope.config_edit.delete_list = $scope.entries
                $scope.catalog_edit.create_list = $scope.config_catalogs
                $scope.catalog_edit.delete_list = $scope.config_catalogs
                $scope.config_hints = {}
                for entry in data[4]
                    $scope.config_hints[entry.config_name] = entry
                    entry.var_lut = {}
                    for vh in entry.config_var_hint_set
                        entry.var_lut[vh.var_name] = vh
            )
        $scope._set_fields = (entry, init=false) ->
            entry.script_sel = 0
            entry.script_num = entry.config_script_set.length
            entry.var_sel = 0
            entry.var_num = entry.config_str_set.length + entry.config_int_set.length + entry.config_bool_set.length + entry.config_blob_set.length
            entry.mon_sel = 0
            entry.mon_num = entry.mon_check_command_set.length
            if init
                entry.script_expanded = false
                entry.var_expanded = false
                entry.mon_expanded = false
            else
                for _type in ["var", "script", "mon"]
                    if not entry["#{_type}_num"]
                        entry["#{_type}_expanded"] = false
        $scope.filter_conf = (entry, scope) ->
            show = false
            scope._set_fields(entry)
            cf = scope.pagSettings.conf.filter_settings
            f_re = scope.filter_re
            if cf.filter_name
                if entry.name.match(f_re) or entry.description.match(f_re)
                    show = true
            if cf.filter_script
                entry.script_sel = (true for _scr in entry.config_script_set when _scr.name.match(f_re) or _scr.description.match(f_re) or _scr.value.match(f_re)).length
                if entry.script_sel
                    show = true
            if cf.filter_mon
                entry.mon_sel = (true for _mon in entry.mon_check_command_set when _mon.name.match(f_re) or _mon.command_line.match(f_re) or _mon.description.match(f_re)).length
                if entry.mon_sel
                    show = true
            if cf.filter_var
                for var_type in ["str", "int", "bool", "blob"]
                    sub_set = entry["config_#{var_type}_set"]
                    entry.var_sel += (true for _var in sub_set when _var.name.match(f_re) or _var.description.match(f_re) or String(_var.value).match(f_re)).length
                if entry.var_sel
                    show = true
            return show
        $scope.clear_filter = () ->
            $scope.pagSettings.conf.filter_settings.filter_str = ""
        $scope.delete_selected_objects = () ->
            if confirm("really delete #{$scope.selected_objects.length} objects ?")
                $.blockUI
                for obj in $scope.selected_objects
                    conf = (entry for entry in $scope.entries when entry.idx == obj.config)[0]
                    if obj.object_type == "mon"
                        ref_f = conf.mon_check_command_set
                    else
                        ref_f = conf["config_#{obj.object_type}_set"]
                    ref_f = (_rv for _rv in ref_f when _rv.idx != obj.idx)
                    if obj.object_type == "mon"
                        conf.mon_check_command_set = ref_f
                    else
                        conf["config_#{obj.object_type}_set"] = ref_f
                    $scope._set_fields(conf)
                call_ajax
                    url     : "{% url 'config:delete_objects' %}"
                    data    :
                        "obj_list" : angular.toJson(([entry.object_type, entry.idx] for entry in $scope.selected_objects))
                    success : (xml) =>
                        parse_xml_response(xml)
                        $.unblockUI()
                $scope.selected_objects = []
        $scope.unselect_objects = () ->
            # unselect all selected objects
            idx = 0
            while $scope.selected_objects.length
                prev_len = $scope.selected_objects.length
                idx++
                entry = $scope.selected_objects[0]
                $scope.unselect_object($scope.selected_objects[0])
                # unable to unselect, exit loop
                if $scope.selected_objects.length == prev_len
                    console.log "problem unselect..."
                    break
        $scope.unselect_object = (obj) ->
            obj._selected = false
            $scope.selected_objects = (entry for entry in $scope.selected_objects when entry != obj)
        $scope.select_object = (obj) ->
            if obj._selected
                $scope.unselect_object(obj)
            else
                obj._selected = true
                $scope.selected_objects.push(obj)
        # hint functions
        $scope.get_config_hints = () ->
            return (entry for entry of $scope.config_hints)
        $scope.get_config_var_hints = (config) ->
            if config and config.name of $scope.config_hints
                return (entry for entry of $scope.config_hints[config.name].var_lut)
            else
                return []
        $scope.config_has_info = (config) ->
            return config.name of $scope.config_hints
        $scope.get_config_help_text = (config) ->
            if $scope.config_has_info(config) 
                return $scope.config_hints[config.name].help_text_short or "no short help"
            else
                return ""
        $scope.var_has_info = (config, cvar) ->
            if config.name of $scope.config_hints
                return cvar.name of $scope.config_hints[config.name].var_lut
            else
                return false
        $scope.get_var_help_text = (config, cvar) ->
            if $scope.var_has_info(config, cvar)
                return $scope.config_hints[config.name].var_lut[cvar.name].help_text_short or "no short help"
            else
                return ""
        $scope.show_config_help = () ->
            if $scope._edit_obj.name of $scope.config_hints
                return $scope.config_hints[$scope._edit_obj.name].help_text_html
            else
                return ""
        $scope.show_config_var_help = () ->
            if $scope._edit_obj.config and $scope._config.name of $scope.config_hints
                ch = $scope.config_hints[$scope._config.name]
                if $scope._edit_obj.name of ch.var_lut
                    return ch.var_lut[$scope._edit_obj.name].help_text_html or ""
                else
                    return ""
            else
                return ""
        $scope.get_label_class = (entry, s_type) ->
            num = entry["#{s_type}_num"]
            sel = entry["#{s_type}_sel"]
            if sel and $scope.pagSettings.conf.filter_settings.filter_str
                return "label label-success"
            else if num
                return "label label-primary"
            else
                return "label label-default"
        $scope.get_expand_class = (config, _type) ->
            if config["#{_type}_num"]
                if config["#{_type}_expanded"]
                    return "glyphicon glyphicon-chevron-down"
                else
                    return "glyphicon glyphicon-chevron-right"
            else
                return "glyphicon"
        $scope.toggle_expand = (config, _type) ->
            if config["#{_type}_num"]
                config["#{_type}_expanded"] = not config["#{_type}_expanded"]
        $scope.get_num_cats = (config) ->
            return if config.categories.length then "#{config.categories.length}" else "-"
        $scope.get_valid_parents = () ->
            return (entry for entry in $scope.entries when entry.enabled)
        $scope.$on("icsw.new_config", (args) ->
            $scope.pagSettings.set_entries($scope.entries)
        )
        $scope.show_parent_config = (config) ->
            if config.parent_config
                return (entry.name for entry in $scope.entries when entry.idx == config.parent_config)[0]
            else
                return "-"
        $scope.get_config_row_class = (config) ->
            return if config.enabled then "" else "danger"
        $scope.get_config_vars = (config) ->
            r_val = []
            for v_type in ["str", "int", "bool", "blob"]
                for entry in config["config_#{v_type}_set"]
                    entry.v_type = v_type
                    r_val.push(entry)
            r_val.sort((_a, _b) ->
                if _a.name > _b.name
                    return 1
                else if _a.name < _b.name
                    return -1
                else
                    return 0 
            )
            return r_val
        $scope.delete_var = (config, _var) ->
            v_type = _var.v_type
            $scope.var_edit.delete_list = config["config_#{v_type}_set"]
            $scope.var_edit.modify_rest_url = {
                "str" : "{% url 'rest:config_str_detail' 1 %}"
                "int" : "{% url 'rest:config_int_detail' 1 %}"
                "bool" : "{% url 'rest:config_bool_detail' 1 %}"
                "blob" : "{% url 'rest:config_blob_detail' 1 %}"
            }[v_type].slice(1).slice(0, -2)
            $scope.var_edit.delete_obj(_var).then((res) ->
                if res
                    $scope.unselect_object(_var)
                    $scope.filter_conf(config, $scope)
            )
        $scope.edit_var = (config, obj, event) ->
            v_type = obj.v_type
            $scope._config = config
            if ! obj.description
                obj.description = "descr"
            $scope.var_edit.edit_template = "config_#{v_type}_template.html"
            $scope.var_edit.modify_rest_url = {
                "str" : "{% url 'rest:config_str_detail' 1 %}"
                "int" : "{% url 'rest:config_int_detail' 1 %}"
                "bool" : "{% url 'rest:config_bool_detail' 1 %}"
            }[v_type].slice(1).slice(0, -2)
            $scope.var_edit.create_list = config["config_#{v_type}_set"]
            $scope.var_edit.edit(obj, event).then(
                (mod_obj) ->
                    if mod_obj != false
                        $scope.filter_conf(config, $scope)
            )
        $scope.create_var = (config, v_type, event) ->
            $scope._config = config
            $scope.var_edit.create_template = "config_#{v_type}_template.html"
            $scope.var_edit.create_rest_url = Restangular.all({
                "str" : "{% url 'rest:config_str_list'%}"
                "int" : "{% url 'rest:config_int_list'%}"
                "bool" : "{% url 'rest:config_bool_list'%}"
            }[v_type].slice(1))
            $scope.var_edit.create_list = config["config_#{v_type}_set"]
            $scope.var_edit.new_object = (scope) ->
                return {
                    "config" : config.idx
                    "name" : "new #{v_type} var"
                    "description" : "new variable (type #{v_type})"
                    "value" : {"str" : "", "int" : 0, "bool" : 1}[v_type]
                }
            $scope.var_edit.create(event).then(
                (new_obj) ->
                    if new_obj != false
                        $scope.filter_conf(config, $scope)
            ) 
        $scope.delete_script = (config, _script) ->
            $scope.script_edit.delete_list = config.config_script_set
            $scope.script_edit.delete_obj(_script).then((res) ->
                if res
                    $scope.unselect_object(_script)
                    $scope.filter_conf(config, $scope)
            )
        $scope.edit_script = (config, obj, event) ->
            $scope.script_edit.create_list = config.config_script_set
            obj.edit_value = obj.value
            $scope.$watch(
                () -> 
                    return obj.edit_value
                (new_val) ->
                    if typeof(new_val) == "string" and new_val.length
                        obj.value = new_val
            )
            $scope.script_edit.edit(obj, event).then(
                (mod_obj) ->
                    if mod_obj != false
                        $scope.filter_conf(config, $scope)
            )
        $scope.create_script = (config, event) ->
            $scope.script_edit.create_list = config.config_script_set
            $scope.script_edit.new_object = (scope) ->
                return {
                    "config"   : config.idx
                    "name"     : "new script"
                    "priority" : 0
                    "enabled"  : true
                    "description" : "new config script"
                    "edit_value"  : "# config script (" + moment().format() + ")\n#\n"
                }
            $scope.$watch(
                () -> 
                    return $scope._edit_obj.edit_value
                (new_val) ->
                    if typeof(new_val) == "string" and new_val.length
                        $scope._edit_obj.value = new_val
            )
            $scope.script_edit.create(event).then(
                (new_obj) ->
                    if new_obj != false
                        $scope.filter_conf(config, $scope)
            ) 
        $scope.delete_mon = (config, _mon) ->
            $scope.mon_edit.delete_list = config.mon_check_command_set
            $scope.mon_edit.delete_obj(_mon).then((res) ->
                if res
                    $scope.unselect_object(_mon)
                    $scope.filter_conf(config, $scope)
            )
        $scope.edit_mon = (config, obj, event) ->
            $scope.mon_edit.create_list = config.mon_check_command_set
            $scope.mon_edit.edit(obj, event).then(
                (mod_obj) ->
                    if mod_obj != false
                        $scope.filter_conf(config, $scope)
            )
        $scope.copy_mon = (config, obj, event) ->
            call_ajax
                url     : "{% url 'config:copy_mon' %}"
                data    :
                    "config" : config.idx
                    "mon"    : obj.idx
                success : (xml) =>
                    if parse_xml_response(xml)
                        new_moncc = angular.fromJson($(xml).find("value[name='mon_cc']").text())
                        config.mon_check_command_set.push(new_moncc)
                        $scope.$apply(() ->
                            $scope._set_fields(config)
                        )
        $scope.create_mon = (config, event) ->
            $scope.mon_edit.create_list = config.mon_check_command_set
            $scope.mon_edit.new_object = (scope) ->
                return {
                    "config" : config.idx
                    "name" : "c_command"
                    "description" : "Check command"
                    "command_line" : "$USER2$ -m $HOSTADDRESS$ uptime"
                    "categories" : []
                }
            $scope.mon_edit.create(event).then(
                (new_obj) ->
                    if new_obj != false
                        $scope.filter_conf(config, $scope)
            ) 
        $scope.get_event_handlers = (edit_obj) ->
            ev_handlers = []
            for entry in $scope.entries
                for cc in entry.mon_check_command_set
                    if cc.is_event_handler and cc.idx != edit_obj.idx
                        ev_handlers.push(cc)
            return ev_handlers
        $scope.download_selected = () ->
            hash = angular.toJson((entry.idx for entry in $scope.pagSettings.filtered_list))
            window.location = "{% url 'config:download_configs' 1 %}".slice(0, -1) + hash
        $scope.get_num_configs = (cat) ->
            return (entry for entry in $scope.entries when entry.config_catalog == cat.idx).length 
        $scope.edit_catalog = (cat, event) ->
            $scope.catalog_edit.edit(cat, event).then(
                (mod_obj) ->
            )
        $scope.delete_catalog = (cat) ->
            $scope.catalog_edit.delete_obj(cat).then((res) ->
            )
        $scope.reload()
]).directive("catalogtable", ($templateCache, $compile, $modal, Restangular) ->
    return {
        restrict : "EA"
        template : $templateCache.get("catalog_table.html")
    }
).directive("configtable", ($templateCache, $compile, $modal, Restangular) ->
    return {
        restrict : "EA"
        template : $templateCache.get("config_table.html")
    }
).directive("vartable", ($templateCache, $compile, $modal, Restangular) ->
    return {
        restrict : "EA"
        template : $templateCache.get("var_table.html")
    }
).directive("scripttable", ($templateCache, $compile, $modal, Restangular) ->
    return {
        restrict : "EA"
        template : $templateCache.get("script_table.html")
    }
).directive("montable", ($templateCache, $compile, $modal, Restangular) ->
    return {
        restrict : "EA"
        template : $templateCache.get("mon_table.html")
    }
).directive("category", ($templateCache, $compile, $modal, Restangular, restDataSource) ->
    return {
        restrict : "EA"
        template : "<tree treeconfig='cat_tree'></tree></div>"
        link : (scope, el, attrs) ->
            scope.cat_tree = new cat_tree(scope)
            cat_tree_lut = {}
            if attrs["mode"] == "conf"
                sel_cat = scope._edit_obj.categories
                top_cat_re = new RegExp(/^\/config/)
            else if attrs["mode"] == "mon"
                # mon
                sel_cat = scope._edit_obj.categories
                top_cat_re = new RegExp(/^\/mon/)
            for entry in scope.categories
                if entry.full_name.match(top_cat_re)
                    t_entry = scope.cat_tree.new_node({folder:false, obj:entry, expand:entry.depth < 2, selected: entry.idx in sel_cat})
                    cat_tree_lut[entry.idx] = t_entry
                    if entry.parent and entry.parent of cat_tree_lut
                        cat_tree_lut[entry.parent].add_child(t_entry)
                    else
                        # hide selection from root nodes
                        t_entry._show_select = false
                        scope.cat_tree.add_root_node(t_entry)
            scope.cat_tree_lut = cat_tree_lut
            scope.cat_tree.show_selected(true)
            scope.new_selection = (new_sel) ->
                scope._edit_obj.categories = new_sel
    }
).run(($templateCache) ->
    $templateCache.put("simple_confirm.html", simple_modal_template)
    $templateCache.put("config_table.html", config_table_template)
    $templateCache.put("catalog_table.html", catalog_table_template)
    $templateCache.put("var_table.html", var_table_template)
    $templateCache.put("script_table.html", script_table_template)
    $templateCache.put("mon_table.html", mon_table_template)
)

class cat_tree extends tree_config
    constructor: (@scope, args) ->
        super(args)
        @show_selection_buttons = false
        @show_icons = false
        @show_select = true
        @show_descendants = false
        @show_childs = false
    get_name : (t_entry) ->
        obj = t_entry.obj
        if obj.comment
            return "#{obj.name} (#{obj.comment})"
        else
            return obj.name 
    selection_changed: () =>
        sel_list = @get_selected((node) ->
            if node.selected
                return [node.obj.idx]
            else
                return []
        )
        @scope.new_selection(sel_list)

add_tree_directive(config_ctrl)

{% endinlinecoffeescript %}

</script>
