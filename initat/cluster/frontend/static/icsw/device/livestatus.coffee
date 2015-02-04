device_livestatus_module = angular.module("icsw.device.livestatus", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular"])

get_service_state_string = (entry) ->
    return {
        0: "OK"
        1: "Warning"
        2: "Critical"
        3: "Unknown"
    }[entry.state]

get_host_state_string = (entry) ->
    return {
        0: "OK"
        1: "Critical"
        2: "Unreachable"
    }[entry.state]

get_service_state_class = (entry) ->
    return {
        0: "success"
        1: "warning"
        2: "danger"
        3: "danger"
    }[entry.state]

get_host_state_class = (entry) ->
    return {
        0: "success"
        1: "danger"
        2: "danger"
    }[entry.state]

show_attempt_info = (entry) ->
    try
        if parseInt(entry.current_attempt) == 1
            return false
        else
            return true
    catch error
       return true

get_attempt_info = (entry, force=false) ->
    if entry.max_check_attempts == null
        return "N/A"
    try
        max = parseInt(entry.max_check_attempts)
        cur = parseInt(entry.current_attempt)
        if cur == 1 and not force
            return ""
        else
            if cur == max
                return "#{cur}"
            else
                return "#{cur} / #{max}"
    catch error
        return "e"

get_state_type = (entry) ->
    return {
        null : "???"
        0 : "soft"
        1 : "hard"
    }[entry.state_type]

get_check_type = (entry) ->
    return {
        null : "???"
        0 : "active"
        1 : "passive"
    }[entry.check_type]

class hs_node
    # hierarchical structure node
    constructor: (@name, @depth=0) ->
        @value = 1
        @root = @
        @children = []
        @show = true
        @clicked = false
    add_child: (entry) ->
        entry.root = @
        entry.depth = @depth + 1
        entry.parent = @
        @children.push(entry)
    iter_childs: (cb_f) ->
        cb_f(@)
        (_entry.iter_childs(cb_f) for _entry in @children)
    get_childs: (filter_f) ->
        _field = []
        if filter_f(@)
            _field.push(@)
        for _entry in @children
            _field = _field.concat(_entry.get_childs(filter_f))
        return _field
    clear_clicked: () ->
        # clear all clicked flags
        @clicked = false
        @show = true
        (_entry.clear_clicked() for _entry in @children)
    any_clicked: () ->
        res = @clicked
        if not res
            for _entry in @children
                res = res || _entry.any_clicked()
        return res
    handle_clicked: () ->
        # find clicked entry
        _clicked = @get_childs((obj) -> return obj.clicked)[0]
        @iter_childs((obj) -> obj.show = false)
        parent = _clicked
        while parent?
            parent.show = true
            parent = parent.parent
        _clicked.iter_childs((obj) -> obj.show = true)
    
device_livestatus_module.controller("livestatus_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "$timeout", "icswTools", "ICSW_URLS", "icswDeviceLivestatusCategoryTreeService",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, $timeout, icswTools, ICSW_URLS, icswDeviceLivestatusCategoryTreeService) ->
        $scope.host_entries = []
        $scope.entries = []
        $scope.order_name = "host_name"
        $scope.order_dir = true
        $scope.md_filter_str = ""
        # not needed
        #$scope.cur_timeout = undefined
        # focused
        $scope.focusService = null
        # flag to trigger redraw of sunburst
        $scope.redrawSunburst = 0
        # flat to trigger recalc of sunburst visibility
        $scope.recalcSunburst = 0
        $scope.cat_tree_show = false
        $scope.burst_show = true
        $scope.burstData = undefined
        $scope.map_show = true
        $scope.table_show = true
        # location gfx list
        $scope.location_gfx_list = []
        $scope.$watch("focusService", (as) ->
            $scope.focus_service = as
        )
        $scope.$watch("recalcSunburst", (red) ->
            $scope.md_filter_changed()
        )
        # workaround: pull outer devicepk into inner scope
        $scope.$watch(
                () -> $scope.$parent.devicepk_livestatus_ctrl
                () -> $scope.devicepk = $scope.$parent.devicepk_livestatus_ctrl
        )
        # paginator settings
        $scope.pagSettings = paginatorSettings.get_paginator("device_tree_base", $scope)
        # category tree
        $scope.cat_tree = new icswDeviceLivestatusCategoryTreeService($scope, {})
        # selected categories
        $scope.selected_mcs = []
        $scope.master_cat_pk = 0
        $scope.show_unspec_cat = true
        $scope.show_options = [
            # 1 ... option local name
            # 2 ... option display name
            # 3 ... default value
            # 4 ... enable sort
            ["host_name"    , "node name", true, true],
            ["state"        , "state", true, true],
            ["description"  , "description", true, true],
            ["cats"         , "categories", false, false],
            ["state_type"   , "state type", false, false],
            ["last_check"   , "last check", true, false],
            ["last_change"  , "last change", false, false],
            ["plugin_output", "result", true, true],
        ]
        # int_state, str_state, default
        $scope.md_states = [
            [0, "O", true, "show OK states"]
            [1, "W", true, "show warning states"]
            [2, "C", true, "show critcal states"]
            [3, "U", true, "show unknown states"]
        ]
        $scope.sh_states = [
            [0, "S", true, "show soft states"]
            [1, "H", true, "show hard states"]
        ]
        $scope.so_enabled = {}
        for entry in $scope.show_options
            $scope.so_enabled[entry[0]] = entry[2]
        $scope.mds_enabled = {}
        for entry in $scope.md_states
            $scope.mds_enabled[entry[0]] = entry[2]
        $scope.shs_enabled = {}
        for entry in $scope.sh_states
            $scope.shs_enabled[entry[0]] = entry[2]
        $scope.get_so_class = (short) ->
            return if $scope.so_enabled[short] then "btn btn-xs btn-success" else "btn btn-xs"
        $scope.toggle_so = (short) ->
            $scope.so_enabled[short] = !$scope.so_enabled[short]
        $scope.get_mds_class = (int_state) ->
            return if $scope.mds_enabled[int_state] then "btn btn-xs " + {0 : "btn-success", 1 : "btn-warning", 2 : "btn-danger", 3 : "btn-danger"}[int_state] else "btn btn-xs"
        $scope.get_shs_class = (int_state) ->
            return if $scope.shs_enabled[int_state] then "btn btn-xs btn-primary" else "btn btn-xs"
        $scope.toggle_mds = (int_state) ->
            $scope.mds_enabled[int_state] = !$scope.mds_enabled[int_state]
            $scope.md_filter_changed()
        $scope.toggle_shs = (int_state) ->
            $scope.shs_enabled[int_state] = !$scope.shs_enabled[int_state]
            $scope.md_filter_changed()
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            #pre_sel = (dev.idx for dev in $scope.devices when dev.expanded)
            #restDataSource.reset()
            $scope.devsel_list = _dev_sel
            $scope.load_static_data()
        $scope.toggle_order = (name) ->
            if $scope.order_name == name
                $scope.order_dir = not $scope.order_dir
            else
                $scope.order_name = name
                $scope.order_dir = true
        $scope.new_mc_selection = (new_sel) ->
            $scope.selected_mcs = new_sel
            $scope.show_unspec_cat = $scope.master_cat_pk in $scope.selected_mcs
            $scope.md_filter_changed()
        $scope.get_header_class = (entry) ->
            return "nowrap"
        $scope.get_order = () ->
            return (if $scope.order_dir then "" else "-") + $scope.order_name
        $scope.get_order_glyph = (name) ->
            if $scope.order_name == name
                if $scope.order_dir 
                    _class = "glyphicon glyphicon-chevron-down"
                else
                    _class = "glyphicon glyphicon-chevron-up"
            else
                _class = "glyphicon glyphicon-chevron-right"
            return _class
        $scope.load_static_data = () ->
            wait_list = [
                restDataSource.reload([ICSW_URLS.REST_CATEGORY_LIST, {}])
                restDataSource.reload([ICSW_URLS.REST_DEVICE_TREE_LIST, {"with_meta_devices" : false, "ignore_cdg" : true}])
                restDataSource.reload([ICSW_URLS.REST_LOCATION_GFX_LIST, {"device_mon_location__device__in": angular.toJson($scope.devsel_list), "_distinct": true}])
                restDataSource.reload([ICSW_URLS.REST_DEVICE_MON_LOCATION_LIST, {"device__in": angular.toJson($scope.devsel_list)}])
            ]
            $q.all(wait_list).then((data) ->
                $scope.location_gfx_list = data[2]
                gfx_lut = {}
                for entry in $scope.location_gfx_list
                    gfx_lut[entry.idx] = entry
                    entry.dml_list = []
                # lut: device_idx -> list of dml_entries
                dev_gfx_lut = {}
                for entry in data[3]
                    if entry.device not of dev_gfx_lut
                        dev_gfx_lut[entry.device] = []
                    dev_gfx_lut[entry.device].push(entry)
                    entry.redraw = 0
                    gfx_lut[entry.location_gfx].dml_list.push(entry)
                $scope.dev_gfx_lut = dev_gfx_lut
                cat_tree_lut = {}
                $scope.cat_tree.clear_root_nodes()
                $scope.selected_mcs = []
                for entry in data[0]
                    if entry.full_name.match(/^\/mon/)
                        entry.short_name = entry.full_name.substring(5)
                        t_entry = $scope.cat_tree.new_node({folder:false, obj:entry, expand:entry.depth < 1, selected: true})
                        cat_tree_lut[entry.idx] = t_entry
                        if entry.parent and entry.parent of cat_tree_lut
                            cat_tree_lut[entry.parent].add_child(t_entry)
                        else
                            # hide selection from root nodes
                            $scope.master_cat_pk = entry.idx
                            $scope.cat_tree.add_root_node(t_entry)
                        $scope.selected_mcs.push(entry.idx)
                $scope.cat_tree_lut = cat_tree_lut
                $scope.cat_tree.show_selected(false)
                $scope.dev_tree_lut = icswTools.build_lut(data[1])
                $scope.load_data()
            )
        $scope.load_data = (mode) ->
            $scope.cur_timeout = $timeout($scope.load_data, 20000)#20000)
            $scope.cur_xhr = call_ajax
                url  : ICSW_URLS.MON_GET_NODE_STATUS
                data : {
                    "pk_list" : angular.toJson($scope.devsel_list)
                },
                success : (xml) =>
                    if parse_xml_response(xml)
                        service_entries = []
                        $(xml).find("value[name='service_result']").each (idx, node) =>
                            service_entries = service_entries.concat(angular.fromJson($(node).text()))
                        host_entries = []
                        $(xml).find("value[name='host_result']").each (idx, node) =>
                            host_entries = host_entries.concat(angular.fromJson($(node).text()))
                        $scope.$apply(
                            used_cats = []
                            $scope.entries = service_entries
                            $scope.host_entries = host_entries
                            $scope.host_lut = {}
                            for entry in host_entries
                                # sanitize entries
                                $scope._sanitize_entries(entry)
                                # list of checks for host
                                entry.checks = []
                                entry.ct = "host"
                                entry.custom_variables = $scope.parse_custom_variables(entry.custom_variables)
                                $scope.host_lut[entry.host_name] = entry
                                $scope.host_lut[entry.custom_variables.device_pk] = entry
                            for entry in service_entries
                                # sanitize entries
                                $scope._sanitize_entries(entry)
                                entry.custom_variables = $scope.parse_custom_variables(entry.custom_variables)
                                entry.description = entry.display_name  # this is also what icinga displays
                                entry.ct = "service"
                                # populate list of checks
                                $scope.host_lut[entry.custom_variables.device_pk].checks.push(entry)
                                if entry.custom_variables and entry.custom_variables.cat_pks?
                                    used_cats = _.union(used_cats, entry.custom_variables.cat_pks)
                            for pk of $scope.cat_tree_lut
                                entry = $scope.cat_tree_lut[pk]
                                if parseInt(pk) in used_cats
                                    entry._show_select = true 
                                else
                                    entry.selected = false
                                    entry._show_select = false 
                            $scope.build_sunburst()
                            $scope.md_filter_changed()
                        )
        $scope.build_sunburst = () ->
            # build burst data
            _bdat = new hs_node("System")
            _bdat.check = {"state" : 0, "type" : "system", "idx" : 0, "ct": "system"}
            _devg_lut = {}
            # lut: dev idx to hs_nodes
            dev_hs_lut = {}
            for entry in $scope.host_entries
                if entry.custom_variables.device_pk of $scope.dev_tree_lut
                    _dev = $scope.dev_tree_lut[entry.custom_variables.device_pk]
                    if _dev.device_group_name not of _devg_lut
                        # we use the same index for devicegroups and services ...
                        _devg = new hs_node(_dev.device_group_name)
                        _devg.check = {
                            "ct"    : "group"
                            "state" : 0
                            "type"  : "group"
                            "group_name" : _dev.device_group_name
                        }
                        _devg_lut[_devg.name] = _devg
                        _bdat.add_child(_devg)
                    else
                        _devg = _devg_lut[_dev.device_group_name]
                    # sunburst struct for device
                    entry.group_name = _dev.device_group_name
                    _dev_sbs = new hs_node(_dev.full_name)
                    _dev_sbs.check = entry
                    _devg.add_child(_dev_sbs)
                    # set devicegroup state
                    _devg.check.state = Math.max(_devg.check.state, _dev_sbs.check.state)
                    # set system state
                    _bdat.check.state = Math.max(_bdat.check.state, _devg.check.state)
                    dev_hs_lut[_dev.idx] = [_dev_sbs]
                    # create sunburst for mon locations
                    if _dev.idx of $scope.dev_gfx_lut
                        for dml in $scope.dev_gfx_lut[_dev.idx]
                            dml_sb = new hs_node(_dev.full_name)
                            dml_sb.check = entry
                            dev_hs_lut[_dev.idx].push(dml_sb)
                            # link sunburst with dml
                            dml.sunburst = dml_sb
            for entry in $scope.entries
                # sanitize entries
                if entry.custom_variables.device_pk of $scope.dev_tree_lut
                    _srv_node = new hs_node(entry.description)
                    _srv_node.check = entry
                    for node in dev_hs_lut[entry.custom_variables.device_pk]
                        _srv_node = new hs_node(entry.description)
                        _srv_node.check = entry
                        node.add_child(_srv_node)
            # remove empty devices
            for _devg in _bdat.children
                _devg.children = (entry for entry in _devg.children when entry.children.length)
            _bdat.children = (entry for entry in _bdat.children when entry.children.length)
            $scope.burstData = _bdat
        $scope._sanitize_entries = (entry) ->
            entry.state = parseInt(entry.state)
            if entry.state_type in ["0", "1"]
                entry.state_type = parseInt(entry.state_type)
            else
                entry.state_type = null
            if entry.check_type in ["0", "1"]
                entry.check_type = parseInt(entry.check_type)
            else
                entry.check_type = null
        $scope.parse_custom_variables = (cvs) ->
            _cv = {}
            if cvs
                first = true
                for _entry in cvs.split("|")
                    if first
                        key = _entry.toLowerCase()
                        first = false
                    else
                        parts = _entry.split(",")
                        _cv[key] = parts
                        key = parts.pop().toLowerCase()
                # append key of last '|'-split to latest parts
                parts.push(key)
                for single_key in ["check_command_pk", "device_pk"]
                    if single_key of _cv
                        _cv[single_key] = parseInt(_cv[single_key][0])
                for int_mkey in ["cat_pks"]
                    if int_mkey of _cv
                        _cv[int_mkey] = (parseInt(_sv) for _sv in _cv[int_mkey])
            return _cv
        $scope.md_filter_changed = () ->
            get_filter = (node) ->
               if node.check?
                   # filter for services
                   return node.check.ct == "service"
               else
                   return false
            if $scope.burstData?
                if $scope.burstData.any_clicked()
                    $scope.burstData.handle_clicked()
                srv_entries = $scope.burstData.get_childs(
                    (node) ->
                       if node.check?
                           return node.check.ct == "service"
                       else
                           return false
                )
                # called when new entries are set or a filter rule has changed
                ($scope._check_filter(entry) for entry in srv_entries)
                # filter dml
                for dev_idx of $scope.dev_gfx_lut
                    for dml in $scope.dev_gfx_lut[dev_idx]
                        if dml.sunburst?
                            ($scope._check_filter(entry) for entry in dml.sunburst.get_childs(get_filter))
                            dml.redraw++
                $scope.redrawSunburst++
        $scope._check_filter = (entry) ->
            show = entry.show
            _check = entry.check
            if not $scope.mds_enabled[_check.state]
                show = false
            if not $scope.shs_enabled[_check.state_type]
                show = false
            if $scope.md_filter_str
                if not $filter("filter")([_check], $scope.md_filter_str).length
                    show = false
            if show
                if not $scope.selected_mcs.length
                   show = false
                else
                    if _check.custom_variables and _check.custom_variables.cat_pks?
                        # only show if there is an intersection
                        show = if _.intersection($scope.selected_mcs, _check.custom_variables.cat_pks).length then true else false
                    else
                        # show entries with unset / empty category
                        show = $scope.show_unspec_cat
            _check._show = show
            entry.value = if show then 1 else 0
        $scope.filter_mdr = (entry, scope) ->
            return entry._show
        $scope.$on("$destroy", () ->
            if $scope.cur_timeout?
                $timeout.cancel($scope.cur_timeout)
            if $scope.cur_xhr?
                $scope.cur_xhr.abort()
        )
]).service("icswDeviceLivestatusCategoryTreeService", () ->
    class category_tree extends tree_config
        constructor: (@scope, args) ->
            super(args)
            #@show_selection_buttons = false
            @show_icons = false
            @show_select = true
            @show_descendants = false
            @show_childs = false
        selection_changed: () =>
            sel_list = @get_selected((node) ->
                if node.selected
                    return [node.obj.idx]
                else
                    return []
            )
            @scope.new_mc_selection(sel_list)
        get_name : (t_entry) ->
            cat = t_entry.obj
            if cat.depth > 1
                r_info = "#{cat.full_name} (#{cat.name})"
                #if cat.num_refs
                #    r_info = "#{r_info} (refs=#{cat.num_refs})"
                return r_info # + "#{cat.idx}"
            else if cat.depth
                return cat.full_name
            else
                return "TOP"
).directive("icswDeviceLivestatusServiceInfo", ["$templateCache", ($templateCache) ->
    return {
        restrict : "E"
        template : $templateCache.get("ICSW.device.livestatus.serviceinfo")
        scope : {
            type : "=type"
            service : "=service"
        }
        link : (scope, element) ->
            scope.get_service_state_string = (entry) ->
                return get_service_state_string(entry)
            scope.get_host_state_string = (entry) ->
                return get_host_state_string(entry)
            scope.get_host_state_class = (entry) ->
                return "label label-#{get_host_state_class(entry)} pull-right"
            scope.get_service_state_class = (entry) ->
                return "label label-#{get_service_state_class(entry)} pull-right"
            scope.get_attempt_info = (entry) ->
                return get_attempt_info(entry, true)
            scope.get_state_type = (entry) ->
                return get_state_type(entry)
            scope.get_check_type = (entry) ->
                return get_check_type(entry)
    }
]).directive("newburst", ["$compile", "$templateCache", ($compile, $templateCache) ->
    return {
        restrict : "E"
        replace: true
        templateNamespace: "svg"
        template: $templateCache.get("ICSW.device.livestatus.network_graph")
        scope:
            data: "=data"
            redraw_burst: "=redraw"
            recalc_burst: "=recalc"
            service_focus: "=servicefocus"
        link: (scope, element, attrs) ->
            scope.nodes = []
            scope.inner = parseInt(attrs["innerradius"] or 20)
            scope.outer = parseInt(attrs["outerradius"] or 120)
            scope.zoom = parseInt(attrs["zoom"] or 0)
            scope.font_stroke = parseInt(attrs["fontstroke"] or 0)
            scope.show_name = parseInt(attrs["showname"] or 0)
            scope.noninteractive = attrs["noninteractive"]  # defaults to false
            scope.hidegroup = attrs["hidegroup"]  # defaults to false
            scope.create_node = (name, settings) ->
                ns = 'http://www.w3.org/2000/svg'
                node = document.createElementNS(ns, name)
                for attr of settings
                    value = settings[attr]
                    if value?
                        node.setAttribute(attr, value)
                return node
            scope.get_children = (node, depth, struct) ->
                _num = 0
                if node.children.length
                    for _child in node.children
                        _num += scope.get_children(_child, depth+1, struct)
                else
                    if node.value?
                        _num = node.value
                node.width = _num
                if not struct[depth]?
                    struct[depth] = []
                struct[depth].push(node)
                return _num
            scope.$watch("data", (data) ->
                if data?
                    data_ok = true
                    if scope.hidegroup
                        if data.children.length > 0  # if not proper livestatus is available, data does not have any children
                            # skip first two levels
                            data = data.children[0].children[0]
                        else
                            data_ok = false

                    if data_ok
                        scope.set_focus_service(null)
                        scope.sunburst_data = data
                        scope.name = scope.sunburst_data.name
                        scope.draw_data()
                )
            scope.$watch("redraw_burst", (data) ->
                if scope.sunburst_data?
                    scope.draw_data()
            )
            scope.set_focus_service = (srvc) ->
                if "servicefocus" of attrs
                    scope.service_focus = srvc
            scope.force_recalc = () ->
                if "recalc" of attrs
                    scope.recalc_burst++
            scope.draw_data = () ->
                # struct: dict of concentric circles, beginning with the innermost
                struct = {}
                _size = scope.get_children(scope.sunburst_data, 0, struct)
                scope.max_depth = (idx for idx of struct).length
                scope.nodes = []
                for idx of struct
                    if struct[idx].length
                        scope.add_circle(parseInt(idx), struct[idx])
            scope.add_circle = (idx, nodes) ->
                _len = _.reduce(
                    nodes,
                    (sum, obj) ->
                        return sum + obj.width
                    0
                )
                outer = scope.get_inner(idx)
                inner = scope.get_outer(idx)
                if not _len
                    # create a dummy part
                    dummy_part = {}
                    dummy_part.children = {}
                    dummy_part.path = "M#{outer},0 " + \
                        "A#{outer},#{outer} 0 1,1 #{-outer},0 " + \
                        "A#{outer},#{outer} 0 1,1 #{outer},0 " + \
                        "L#{outer},0 " + \
                        "M#{inner},0 " + \
                        "A#{inner},#{inner} 0 1,0 #{-inner},0 " + \
                        "A#{inner},#{inner} 0 1,0 #{inner},0 " + \
                        "L#{inner},0 " + \
                        "Z"
                    scope.nodes.push(dummy_part)
                else
                    end_arc = 0
                    end_num = 0
                    # legend radii
                    inner_legend = (outer + inner) / 2
                    outer_legend = scope.outer * 1.125
                    for part in nodes
                        if part.width
                            start_arc = end_arc #+ 1 * Math.PI / 180
                            start_sin = Math.sin(start_arc)
                            start_cos = Math.cos(start_arc)
                            end_num += part.width
                            end_arc = 2 * Math.PI * end_num / _len
                            mean_arc = (start_arc + end_arc) / 2
                            mean_sin = Math.sin(mean_arc)
                            mean_cos = Math.cos(mean_arc)
                            end_sin = Math.sin(end_arc)
                            end_cos = Math.cos(end_arc)
                            if end_arc > start_arc + Math.PI
                                _large_arc_flag = 1
                            else
                                _large_arc_flag = 0
                            if mean_cos < 0
                                legend_x = -outer_legend * 1.2
                                part.legend_anchor = "end"
                            else
                                legend_x = outer_legend * 1.2
                                part.legend_anchor = "start"
                            part.legend_x = legend_x
                            part.legend_y = mean_sin * outer_legend
                            part.legendpath = "#{mean_cos * inner_legend},#{mean_sin * inner_legend} #{mean_cos * outer_legend},#{mean_sin * outer_legend} " + \
                                "#{legend_x},#{mean_sin * outer_legend}"
                            if part.width == _len
                                # trick: draw 2 semicircles
                                part.path = "M#{outer},0 " + \
                                    "A#{outer},#{outer} 0 1,1 #{-outer},0 " + \
                                    "A#{outer},#{outer} 0 1,1 #{outer},0 " + \
                                    "L#{outer},0 " + \
                                    "M#{inner},0 " + \
                                    "A#{inner},#{inner} 0 1,0 #{-inner},0 " + \
                                    "A#{inner},#{inner} 0 1,0 #{inner},0 " + \
                                    "L#{inner},0 " + \
                                    "Z"
                            else
                                part.path = "M#{start_cos * inner},#{start_sin * inner} L#{start_cos * outer},#{start_sin * outer} " + \
                                    "A#{outer},#{outer} 0 #{_large_arc_flag} 1 #{end_cos * outer},#{end_sin * outer} " + \
                                    "L#{end_cos * inner},#{end_sin * inner} " + \
                                    "A#{inner},#{inner} 0 #{_large_arc_flag} 0 #{start_cos * inner},#{start_sin * inner} " + \
                                    "Z"
                            scope.nodes.push(part)
            scope.get_inner = (idx) ->
                _inner = scope.inner + (scope.outer - scope.inner) * idx / scope.max_depth
                return _inner
            scope.get_outer = (idx) ->
                _outer = scope.inner + (scope.outer - scope.inner) * (idx + 1) / scope.max_depth
                return _outer
            scope.get_fill_color = (part) ->
                if part.check?
                    if part.check.ct == "host"
                        color = {
                            0 : "#66dd66"
                            1 : "#ff7777"
                            2 : "#ff0000"
                        }[part.check.state]
                    else
                        color = {
                            0 : "#66dd66"
                            1 : "#dddd88"
                            2 : "#ff7777"
                            3 : "#ff0000"
                        }[part.check.state]
                else
                    color = "#dddddd"
                return color
            scope.get_fill_opacity = (part) ->
                if part.mouseover? and part.mouseover
                    return 0.4
                else
                    return 0.8
            scope.mouse_enter = (part) ->
                if !scope.noninteractive
                    scope.set_focus_service(part.check)
                    if part.children.length
                        for _entry in part.children
                            if _entry.value
                                _entry.legend_show = true
                    else
                        if part.value
                            part.legend_show = true
                    scope.set_mouseover(part, true)
            scope.mouse_click = (part) ->
                if scope.zoom and !scope.noninteractive
                    scope.sunburst_data.clear_clicked()
                    part.clicked = true
                    scope.force_recalc()
            scope.mouse_leave = (part) ->
                if !scope.noninteractive
                    if part.children.length
                        for _entry in part.children
                            _entry.legend_show = false
                    else
                        part.legend_show = false
                    scope.set_mouseover(part, false)
            scope.set_mouseover = (part, flag) ->
                while true
                    part.mouseover = flag
                    if part.parent?
                        part = part.parent
                    else
                        break
    }
]).directive("livestatus", ($templateCache, msgbus) ->
    return {
        restrict : "EA"
        template : $templateCache.get("ICSW.device.livestatus.overview")
        link : (scope, el, attrs) ->
            if attrs.devicepk?
                scope.$watch(attrs["devicepk"], (new_val) ->
                    if new_val and new_val.length
                        scope.new_devsel(new_val)
                )
            else
                msgbus.emit("devselreceiver")
                msgbus.receive("devicelist", scope, (name, args) ->
                    scope.new_devsel(args[0])                    
                )
            scope.get_state_class = (entry) ->
                state_class = {
                    0 : "success"
                    1 : "warning"
                    2 : "danger"
                    3 : "danger"
                }[entry.state]
                return "#{state_class} nowrap"
            scope.get_last_check = (entry) ->
                return scope.get_diff_time(entry.last_check)
            scope.get_last_change = (entry) ->
                return scope.get_diff_time(entry.last_state_change)
            scope.get_diff_time = (ts) ->
                if parseInt(ts)
                    return moment.unix(ts).fromNow(true)
                else
                    return "never"
            scope.get_categories = (entry) ->
                if entry.custom_variables
                    if entry.custom_variables.cat_pks?
                        return (scope.cat_tree_lut[_pk].obj.short_name for _pk in entry.custom_variables.cat_pks).join(", ")
                    else
                        return "---"
                else
                    return "N/A"
            scope.get_state_type = (entry) ->
                return get_state_type(entry)
            scope.get_check_type = (entry) ->
                return get_check_type(entry)
            scope.host_is_passive_checked = (entry) ->
                if entry.host_name of scope.host_lut
                    return if scope.host_lut[entry.host_name].check_type then true else false 
                else
                    return false                  
            scope.is_passive_check = (entry) ->
                return if entry.check_type then true else false 
            scope.get_host_class = (entry) ->
                if entry.host_name of scope.host_lut
                    h_state = scope.host_lut[entry.host_name].state
                    h_state_str = {
                        0 : "success"
                        1 : "danger"
                        2 : "danger"
                    }[h_state]
                else
                    h_state_str = "warning"
                return "#{h_state_str} nowrap"
            scope.get_host_state_string = (entry) -> 
                return get_host_state_string(entry)
            scope.get_host_state_class = (entry) -> 
                return get_host_state_class(entry) + " nowrap"
            scope.get_service_state_string = (entry) -> 
                return get_service_state_string(entry)
            scope.get_service_state_class = (entry) -> 
                return get_service_state_class(entry) + " nowrap"
            scope.show_host_attempt_info = (srv_entry) ->
                return scope.show_attempt_info(scope.host_lut[srv_entry.host_name])
            scope.show_attempt_info = (entry) ->
                return show_attempt_info(entry)
            scope.get_host_attempt_info = (srv_entry) ->
                return scope.get_attempt_info(scope.host_lut[srv_entry.host_name])
            scope.get_attempt_info = (entry) ->
                return get_attempt_info(entry)
    }
).directive("livestatusBrief", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("ICSW.device.livestatus.brief")
        link : (scope, element, attrs) ->
            scope.$watch(("devicepk"), (data) ->
                if data
                    scope.new_devsel([scope.devicepk], [])
            )
    }
).directive("monmap", ["$templateCache", "$compile", "$modal", "Restangular", ($templateCache, $compile, $modal, Restangular) ->
    return {
        restrict : "EA"
        template: $templateCache.get("ICSW.device.livestatus.map_overview")
        scope:
            gfx : "=gfx"
        link : (scope, element, attrs) ->
            scope.loc_gfx = undefined
            scope.$watch("gfx", (new_val) ->
                scope.loc_gfx = new_val
            )
    }
]).directive("devnode", ($compile, $templateCache) ->
    return {
        restrict : "EA"
        replace: true
        template: $templateCache.get("ICSW.device.livestatus.device_node")
        link: (scope, element, attrs) ->
            dml = scope.dml
            scope.data_source = ""
            scope.transform = "translate(#{dml.pos_x},#{dml.pos_y})"
            scope.$watch("dml.sunburst", (dml) ->
                if dml?
                    scope.data_source = "b"
            )
    }    
)

class mc_table
    constructor : (@xml, paginatorSettings) ->
        @name = @xml.prop("tagName")
        @short_name = @name.replace(/_/g, "").replace(/list$/, "")
        @attr_list = new Array()
        @entries = []
        @columns_enabled = {}
        @xml.children().each (idx, entry) =>
            for attr in entry.attributes
                if attr.name not in @attr_list
                    @attr_list.push(attr.name)
                    @columns_enabled[attr.name] = true
            @entries.push(@_to_json($(entry)))
        @pagSettings = paginatorSettings.get_paginator("device_tree_base")
        @order_name = "name"
        @order_dir = true
    toggle_column: (attr) ->
        @columns_enabled[attr] = !@columns_enabled[attr]
    _to_json : (entry) =>
        _ret = new Object()
        for attr_name in @attr_list
            _ret[attr_name] = entry.attr(attr_name)
        return _ret
    toggle_order : (name) =>
        if @order_name == name
            @order_dir = not @order_dir
        else
            @order_name = name
            @order_dir = true
    get_order : () =>
        return (if @order_dir then "" else "-") + @order_name
    get_order_glyph : (name) =>
        if @order_name == name
            if @order_dir 
                _class = "glyphicon glyphicon-chevron-down"
            else
                _class = "glyphicon glyphicon-chevron-up"
        else
            _class = "glyphicon"
        return _class
        
device_livestatus_module.controller("monconfig_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "$timeout", "access_level_service", "ICSW_URLS",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, $timeout, access_level_service, ICSW_URLS) ->
        access_level_service.install($scope)
        $scope.hint_edit = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular, $q, "nd")
        $scope.hint_edit.edit_template = "monitoring_hint_form.html"
        $scope.hint_edit.modify_rest_url = ICSW_URLS.REST_MONITORING_HINT_DETAIL.slice(1).slice(0, -2)
        $scope.hint_edit.modify_data_before_put = (hint) ->
            $scope.restore_values(hint, true)
        $scope.hint_edit.new_object_at_tail = false
        $scope.hint_edit.use_promise = true
        $scope.reload_pending = false
        $scope.monconfig_open = true
        $scope.monhint_open = true
        $scope.new_devsel = (_dev_sel, _devg_sel) ->
            $scope.devsel_list = _dev_sel
            $scope.load_data("ALWAYS")
        $scope.toggle_order = (name) ->
            if $scope.order_name == name
                $scope.order_dir = not $scope.order_dir
            else
                $scope.order_name = name
                $scope.order_dir = true
        $scope.get_order = () ->
            return (if $scope.order_dir then "" else "-") + $scope.order_name
        $scope.get_order_glyph = (name) ->
            if $scope.order_name == name
                if $scope.order_dir 
                    _class = "glyphicon glyphicon-chevron-down"
                else
                    _class = "glyphicon glyphicon-chevron-up"
            else
                _class = "glyphicon glyphicon-chevron-right"
            return _class
        $scope.get_long_attr_name = (name) ->
            return name.replace(/_/g, " ")
        $scope.get_short_attr_name = (name) ->
            _parts = name.split("_")
            return (_str.slice(0, 1) for _str in _parts).join("").toUpperCase()
        $scope.load_data = (mode) ->
            $scope.reload_pending = true
            $scope.cur_xhr = call_ajax
                url  : ICSW_URLS.MON_GET_NODE_CONFIG
                data : {
                    "pk_list" : angular.toJson($scope.devsel_list)
                    "mode"    : mode
                },
                success : (xml) =>
                    if parse_xml_response(xml)
                        mc_tables = []
                        $(xml).find("config > *").each (idx, node) => 
                            new_table = new mc_table($(node), paginatorSettings)
                            mc_tables.push(new_table)
                        $scope.$apply(
                            $scope.mc_tables = mc_tables
                        )
                        restDataSource.reset()
                        wait_list = restDataSource.add_sources([
                            [ICSW_URLS.REST_DEVICE_TREE_LIST, {"with_monitoring_hint" : true, "pks" : angular.toJson($scope.devsel_list), "olp" : "backbone.device.change_monitoring"}],
                            [ICSW_URLS.REST_FETCH_FORMS, {
                                "forms" : angular.toJson([
                                    "monitoring_hint_form"
                                 ])
                            }],
                        ])
                        $q.all(wait_list).then((data) ->
                            $scope.devices = []
                            $scope.device_lut = {}
                            for entry in data[0]
                                entry.expanded = true
                                $scope.devices.push(entry)
                                $scope.device_lut[entry.idx] = entry
                            # forms
                            for cur_form in data[1] 
                                $templateCache.put(cur_form.name, cur_form.form)
                            $scope.reload_pending = false
                        )
                    else
                        $scope.$apply(
                            $scope.mc_tables = []
                            $scope.reload_pending = false
                        )
        $scope.get_tr_class = (obj) ->
            if obj.device_type_identifier == "MD"
                return "success"
            else
                return ""
        $scope.expand_vt = (obj) ->
            obj.expanded = not obj.expanded
        $scope.get_expand_class = (obj) ->
            if obj.expanded
                return "glyphicon glyphicon-chevron-down"
            else
                return "glyphicon glyphicon-chevron-right"
        $scope.remove_hint = (hint) ->
            _.remove($scope.device_lut[hint.device].monitoring_hint_set, (entry) -> return entry.idx == hint.idx)
            call_ajax
                url     :ICSW_URLS.MON_DELETE_HINT
                data    :
                    hint_pk : hint.idx
        $scope.save_hint = (hint) ->
            Restangular.restangularizeElement(null, hint, ICSW_URLS.REST_MONITORING_HINT_DETAIL.slice(1).slice(0, -2))
            hint.put()
        $scope.backup_values = (hint) ->
            if hint.v_type == "f"
                v_name = "float"
            else
                v_name = "int"
            for _a in ["lower", "upper"]
                for _b in ["crit", "warn"]
                    _var = "#{_a}_#{_b}_#{v_name}"
                    hint["#{_var}_saved"] = hint[_var]
                    hint["#{_var}_source_saved"] = hint["#{_var}_source"]
                    hint["#{_var}_source"] = "u"
        $scope.restore_values = (hint, intl) ->
            if hint.v_type == "f"
                v_name = "float"
            else
                v_name = "int"
            for _a in ["lower", "upper"]
                for _b in ["crit", "warn"]
                    _var = "#{_a}_#{_b}_#{v_name}"
                    if intl
                        if hint["#{_var}"] == hint["#{_var}_saved"]
                            hint["#{_var}"] = hint["#{_var}_saved"]
                            hint["#{_var}_source"] = hint["#{_var}_source_saved"]
                    else
                        hint["#{_var}"] = hint["#{_var}_saved"]
                        hint["#{_var}_source"] = hint["#{_var}_source_saved"]
        $scope.modify_hint = (hint, event) ->
            $scope.backup_values(hint)
            $scope.hint_edit.edit(hint, event).then(
                (mod_hint) ->
                    if mod_hint == false
                        $scope.restore_values(hint, false)
            )
        $scope.$on("$destroy", () ->
            #if $scope.cur_timeout?
            #    $timeout.cancel($scope.cur_timeout)
            if $scope.cur_xhr?
                $scope.cur_xhr.abort()
        )
]).directive("monconfig", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("ICSW.device.livestatus.monconfig")
        link : (scope, el, attrs) ->
            scope.$watch(attrs["devicepk"], (new_val) ->
                if new_val and new_val.length
                    scope.new_devsel(new_val)
            )
    }
).directive("mhdevrow", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("ICSW.device.livestatus.hint_row")
    }
).directive("mhrow", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("mhrow.html")
        link : (scope) ->
            scope.get_v_type = () ->
                return {"f" : "float", "i" : "int", "s" : "string"}[scope.hint.v_type]
            scope.get_value = () ->
                return scope.hint["value_" + scope.get_v_type()]
            scope.get_td_title = (name) ->
                v_type = scope.get_v_type()
                key = "#{name}_#{v_type}"
                skey = "#{key}_source"
                if scope.hint[skey] == "n"
                    return "not set"
                else if scope.hint[skey] == "s"
                    return "set by system"
                else if scope.hint[skey] == "u"
                    return "set by user"
                else
                    return "unknown source '#{scope.hint[skey]}'"
            scope.get_td_class = (name) ->
                v_type = scope.get_v_type()
                key = "#{name}_#{v_type}"
                skey = "#{key}_source"
                if scope.hint[skey] == "n"
                    return ""
                else if scope.hint[skey] == "s"
                    return "warning"
                else if scope.hint[skey] == "u"
                    return "success"
            scope.get_limit = (name) ->
                v_type = scope.get_v_type()
                key = "#{name}_#{v_type}"
                skey = "#{key}_source"
                if scope.hint[skey] == "s" or scope.hint[skey] == "u"
                    return scope.hint[key]
                else
                    return "---"
            scope.delete_hint = (hint) ->
                scope.remove_hint(hint)
            scope.toggle_enabled = (hint) ->
                hint.enabled = !hint.enabled
                scope.save_hint(hint)
    }
).directive("monitoringhinttable", ($templateCache, $compile, $modal, Restangular) ->
    return {
        restrict : "EA"
        template : $templateCache.get("ICSW.device.livestatus.hint_table")
        link : (scope) ->
    }
)
