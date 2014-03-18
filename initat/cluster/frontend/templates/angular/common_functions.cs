{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

{% verbatim %}

icsw_paginator = """
<form class="form-inline">
    <span ng-show="pagSettings.conf.filtered_len">
        <div class="form-group">
            <ul class="pagination pagination-sm" ng-show="pagSettings.conf.num_pages > 1 && pagSettings.conf.num_pages < 11"  style="margin-top:0px; margin-bottom:0px;">
                <li ng-repeat="pag_num in pagSettings.conf.page_list track by $index" ng-class="pagSettings.get_li_class(pag_num)">
                    <a href="#" ng-click="activate_page(pag_num)">{{ pag_num }}</a>
                </li>
            </ul>
            <ul class="pagination pagination-sm" ng-show="pagSettings.conf.num_pages > 1 && pagSettings.conf.num_pages > 10"  style="margin-top:0px; margin-bottom:0px;">
                <li ng-class="pagSettings.get_laquo_class()">
                    <a href="#" ng-click="pagSettings.page_back()">&laquo;</a>
                </li>
                <li ng-class="pagSettings.get_raquo_class()">
                    <a href="#" ng-click="pagSettings.page_forward()">&raquo;</a>
                </li>
                <li ng-repeat="pag_num in pagSettings.get_filtered_pl() track by $index" ng-class="pagSettings.get_li_class(pag_num)">
                    <a href="#" ng-click="activate_page(pag_num)">{{ pag_num }}</a>
                </li>
            </ul>
        </div>
        <span ng-show="pagSettings.conf.num_pages > 5">
            <select class="form-control input-sm" ng-model="pagSettings.conf.act_page" ng-change="activate_page()"
                ng-options="idx as pagSettings.get_range_info(idx) for idx in [] | range:pagSettings.conf.num_pages"
            >
            </select>
        </span>
        <span ng-show="pagSettings.conf.num_pages > 1">, </span>
        <span ng-show="pagSettings.conf.num_pages < 6">
            showing entries {{ pagSettings.conf.start_idx + 1 }} to {{ pagSettings.conf.end_idx + 1 }},
        </span>
    </span>
    <span ng-show="! pagSettings.conf.filtered_len">
        no entries to show,
    </span>
    <span ng-show="pagSettings.conf.modify_epp">
        show
        <div class="form-group">
            <select class="form-control input-sm" ng-model="pagSettings.conf.per_page" ng-options="value as value for (key, value) in pagSettings.conf.entries_per_page"></select>
        </div> per page,
    </span>
    <span ng-show="pagSettings.simple_filter_mode()">
        filter <div class="form-group"><input ng-model="pagSettings.conf.filter" class="form-control input-sm""></input></div>,
    </span>
</form>
"""

{% endverbatim %}

build_lut = (list) ->
    lut = {}
    for value in list
        lut[value.idx] = value
    return lut

class paginator_root
    constructor: (@$filter) ->
        @dict = {}
    get_paginator: (name, $scope) =>
        if name not in @dict
            @dict[name] = new paginator_class(name, @$filter, $scope)
        return @dict[name]

class paginator_class
    constructor: (@name, @$filter, @$scope) ->
        @conf = {
            per_page         : 10
            filtered_len     : 0
            unfiltered_len   : 0
            num_pages        : 0
            start_idx        : 0
            end_idx          : 0
            act_page         : 0
            page_list        : []
            modify_epp       : false
            entries_per_page : []
            init             : false
            filter_changed   : false
            filter_mode      : false
            filter           : undefined
            filter_func      : undefined
        }
        if @$scope and @$scope.settings and @$scope.settings.filter_settings
            @conf.filter_settings = @$scope.settings.filter_settings
        else
            @conf.filter_settings = {}
    get_laquo_class : () =>
        if @conf.act_page == 1
            return "disabled"
        else
            return ""
    get_raquo_class : () =>
        if @conf.act_page == @conf.num_pages
            return "disabled"
        else
            return ""
    page_back: () =>
        if @conf.act_page > 1
            @conf.act_page--
            @activate_page()
    page_forward: () =>
        if @conf.act_page < @conf.num_pages
            @conf.act_page++
            @activate_page()
    get_filtered_pl: () =>
        # return a filtered page list around the current page
        s_page = @conf.act_page
        m_page = @conf.act_page
        e_page = @conf.act_page
        for idx in [1..10]
            if s_page > 1 and e_page - s_page < 10
                s_page--
            if e_page < @conf.num_pages and e_page - s_page < 10
                e_page++
        return (idx for idx in [s_page..e_page])
    get_range_info: (num) =>
        num = parseInt(num)
        s_val = (num - 1 ) * @conf.per_page + 1
        e_val = s_val + @conf.per_page - 1
        if e_val > @conf.filtered_len
            e_val = @conf.filtered_len
        return "page #{num} (#{s_val} - #{e_val})"
    activate_page: (num) =>
        if num != undefined
            @conf.act_page = parseInt(num)
        # indices start at zero
        pp = @conf.per_page
        @conf.start_idx = (@conf.act_page - 1 ) * pp
        @conf.end_idx = (@conf.act_page - 1) * pp + pp - 1
        if @conf.end_idx >= @conf.filtered_len
            @conf.end_idx = @conf.filtered_len - 1
    get_li_class: (num) =>
        if num == @conf.act_page
            return "active"
        else
            return ""
    set_epp: (in_str) =>
        @conf.modify_epp = true
        @conf.entries_per_page = (parseInt(entry) for entry in in_str.split(","))
    set_entries: (el_list) =>
        # can also be used to reapply the filter
        @conf.unfiltered_len = el_list.length
        el_list = @apply_filter(el_list)
        @filtered_list = el_list
        @conf.init = true
        @conf.filtered_len = el_list.length
        pp = @conf.per_page
        @conf.num_pages = parseInt((@conf.filtered_len + pp - 1) / pp)
        if @conf.num_pages > 0
            @conf.page_list = (idx for idx in [1..@conf.num_pages])
        else
            @conf.page_list = []
        if @conf.act_page == 0
            @activate_page(1)
        else
            if @conf.act_page > @conf.page_list.length
                @activate_page(@conf.page_list.length)
            else
                @activate_page(@conf.act_page)
    simple_filter_mode: () =>
        return @conf.filter_mode == "simple"
    clear_filter: () =>
        if @conf.filter_mode
            @conf.filter = ""
    apply_filter: (el_list) =>
        if @conf.filter_changed
            @conf.filter_changed(@)
        if @conf.filter_mode
            if @conf.filter_func
                el_list = (entry for entry in el_list when @conf.filter_func()(entry, @$scope))
            else
                el_list = @$filter("filter")(el_list, @conf.filter)
        return el_list

class shared_data_source
    constructor: () ->
        @data = {}

class rest_data_source
    constructor: (@$q, @Restangular) ->
        @reset()
    reset: () =>
        @_data = {}
    _build_key: (url, options) =>
        url_key = url
        for key, value of options
            url_key = "#{url_key},#{key}=#{value}"
        return url_key
    _do_query: (q_type, options) =>
        d = @$q.defer()
        result = q_type.getList(options).then(
           (response) ->
               d.resolve(response)
        )
        return d.promise
    load: (rest_tuple) =>
        if typeof(rest_tuple) == "string"
            rest_tuple = [rest_tuple, {}]
        url = rest_tuple[0]
        options = rest_tuple[1]
        if @_build_key(url, options) of @_data
            # queries with options are not shared
            return @get([url, options])
        else
            return @reload([url, options])
    reload: (rest_tuple) =>
        if typeof(rest_tuple) == "string"
            rest_tuple = [rest_tuple, {}]
        url = rest_tuple[0]
        options = rest_tuple[1]
        if not @_build_key(url, options) of @_data
            # not there, call load
            return @load([url, options])
        else
            @_data[@_build_key(url, options)] = @_do_query(@Restangular.all(url.slice(1)), options)
            return @get(rest_tuple)
    add_sources: (in_list) =>
        # in list is a list of (url, option) lists
        q_list = []
        r_list = []
        for rest_tuple in in_list
            rest_key = @_build_key(rest_tuple[0], rest_tuple[1])
            if rest_key not of @_data
                sliced = rest_tuple[0].slice(1)
                rest_tuple[1] ?= {}
                @_data[rest_key] = @_do_query(@Restangular.all(sliced), rest_tuple[1])
                q_list.push(@_data[rest_key])
            r_list.push(@_data[rest_key])
        if q_list
            @$q.all(q_list)
        return r_list
    get: (rest_tuple) =>
        return @_data[@_build_key(rest_tuple[0], rest_tuple[1])]
  
angular_module_setup = (module_list, url_list=[]) ->
    $(module_list).each (idx, cur_mod) ->
        cur_mod.factory("access_level_service", () ->
            # see lines 205 ff in backbone/models/user.py
            to_list = (in_str) ->
                r_dict = {}
                for part in in_str.split(",")
                    kv = part.split("=")
                    r_dict[kv[0]] = parseInt(kv[1])
                return r_dict
            check_level = (obj, ac_name, mask, any) ->
                if ac_name.split(".").length != 3
                    alert("illegal ac specifier '#{ac_name}'")
                #console.log ac_name, obj._GLOBAL_, obj.access_levels
                if obj and obj.access_levels?
                    # object level permissions
                    # no need to check for global permissions because those are mirrored down
                    # to the object_level permission on the server
                    if not obj._all
                        obj._all = to_list(obj.access_levels)
                    if ac_name of obj._all
                        if any
                            return if obj._all[ac_name] & mask then true else false
                        else
                            return (obj._all[ac_name] & mask) == mask
                    else
                        return false
                else
                    # check global permissions
                    obj = GLOBAL_PERMISSIONS
                    if ac_name of obj
                        if any
                            return if obj[ac_name] & mask then true else false
                        else
                            return (obj[ac_name] & mask) == mask
                    else
                        return false
            func_dict = {
                "acl_delete" : (obj, ac_name) ->
                    return check_level(obj, ac_name, 4, true)
                "acl_create" : (obj, ac_name) ->
                    return check_level(obj, ac_name, 2, true)
                "acl_modify" : (obj, ac_name) ->
                    return check_level(obj, ac_name, 1, true)
                "acl_read" : (obj, ac_name) ->
                    return check_level(obj, ac_name, 0, true)
                "acl_any" : (obj, ac_name, mask) ->
                    return check_level(obj, ac_name, mask, true)
                "acl_all" : (obj, ac_name, mask) ->
                    return check_level(obj, ac_name, mask, false)

            }
            return {
                "install" : (scope) ->
                    scope.acl_create = func_dict["acl_create"]
                    scope.acl_modify = func_dict["acl_modify"]
                    scope.acl_delete = func_dict["acl_delete"]
                    scope.acl_read = func_dict["acl_read"]
                    scope.acl_any = func_dict["acl_any"]
                    scope.acl_all = func_dict["acl_all"]
           }
        )
        cur_mod.config(['$httpProvider', 
            ($httpProvider) ->
                $httpProvider.defaults.xsrfCookieName = 'csrftoken'
                $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken'
        ]).filter("paginator", ["$filter", ($filter) ->
            return (arr, scope) ->
                if scope.pagSettings.conf.init
                    arr = scope.pagSettings.apply_filter(arr)
                    return arr.slice(scope.pagSettings.conf.start_idx, scope.pagSettings.conf.end_idx + 1)
                else
                    return arr
        ]).filter("paginator2", ["$filter", ($filter) ->
            return (arr, pag_settings) ->
                if pag_settings.conf.init
                    arr = pag_settings.apply_filter(arr)
                    return arr.slice(pag_settings.conf.start_idx, pag_settings.conf.end_idx + 1)
                else
                    return arr
        ]).filter("paginator_filter", ["$filter", ($filter) ->
            return (arr, scope) ->
                return scope.pagSettings.apply_filter(arr)
        ]).config(["RestangularProvider", 
            (RestangularProvider) ->
                RestangularProvider.setRestangularFields({
                    "id" : "idx"
                })
                RestangularProvider.setResponseInterceptor((data, operation, what, url, response, deferred) ->
                    if data.log_lines
                        for entry in data.log_lines
                            noty
                                type : {20 : "success", 30 : "warning", 40 : "error", 50 : "alert"}[entry[0]] 
                                text : entry[1]
                    if data._change_list
                        $(data._change_list).each (idx, entry) ->
                            noty
                                text : entry[0] + " : " + entry[1]
                        delete data._change_list
                    if data._messages
                        $(data._messages).each (idx, entry) ->
                            noty
                                text : entry
                    return data
                )
                RestangularProvider.setErrorInterceptor((resp) ->
                    error_list = []
                    if typeof(resp.data) == "string"
                        if resp.data
                            resp.data = {"error" : resp.data}
                        else
                            resp.data = {}
                    for key, value of resp.data
                        key_str = if key == "__all__" then "error: " else "#{key} : "
                        if key != "_reset_list"
                            if Array.isArray(value)
                                for sub_val in value
                                    if sub_val.non_field_errors
                                        error_list.push(key_str + sub_val.non_field_errors.join(", "))
                                    else
                                        error_list.push(key_str + String(sub_val))
                            else
                                if (typeof(value) == "object" or typeof(value) == "string") and (not key.match(/^_/) or key == "__all__")
                                    error_list.push(key_str + if typeof(value) == "string" then value else value.join(", "))
                    new_error_list = []
                    for _err in error_list
                        if _err not in new_error_list
                            new_error_list.push(_err)
                            noty
                                text : _err
                                type : "error"
                                timeout : false
                    return true
                )
        ]).service("paginatorSettings", ["$filter", ($filter) ->
        # in fact identical ?
        # cur_mod.service("paginatorSettings", (paginator_class))
            return new paginator_root($filter)
        ]).service("restDataSource", ["$q", "Restangular", ($q, Restangular) ->
            return new rest_data_source($q, Restangular)
        ]).service("sharedDataSource", [() ->
            return new shared_data_source()
        ]).directive("paginator", ($templateCache) ->
            link = (scope, element, attrs) ->
                pagSettings = scope.pagSettings
                pagSettings.conf.per_page = parseInt(attrs.perPage)
                #scope.pagSettings.conf.filter = attrs.paginatorFilter
                if attrs.paginatorEpp
                    pagSettings.set_epp(attrs.paginatorEpp)
                if attrs.paginatorFilter
                    pagSettings.conf.filter_mode = attrs.paginatorFilter
                    if pagSettings.conf.filter_mode == "simple"
                        pagSettings.conf.filter = ""
                    else if pagSettings.conf.filter_mode == "func"
                        pagSettings.conf.filter_func = scope.filterFunc
                scope.activate_page = (page_num) ->
                    pagSettings.activate_page(page_num)
                scope.$watch(
                    () -> return scope.entries
                    (new_el) ->
                        pagSettings.set_entries(new_el)
                )
                scope.$watch(
                    () -> return pagSettings.conf.filter
                    (new_el) ->
                        pagSettings.set_entries(scope.entries)
                )
                scope.$watch(
                    () -> return pagSettings.conf.per_page
                    (new_el) ->
                        pagSettings.set_entries(scope.entries)
                )
                scope.$watch(
                    () -> return pagSettings.conf.filter_settings
                    (new_el) ->
                        pagSettings.set_entries(scope.entries)
                    true
                )
            return {
                restrict : "EA"
                scope:
                    entries     : "="
                    pagSettings : "="
                    paginatorFilter : "="
                    filterFunc  : "&paginatorFilterFunc"
                template : icsw_paginator
                link     : link
            }
        )
        
handle_reset = (data, e_list, idx) ->
    # used to reset form fields when requested by server reply
    if data._reset_list
        if idx == null
            # special case: e_list is the element to modify
            scope_obj = e_list
        else
            scope_obj = (entry for key, entry of e_list when key.match(/\d+/) and entry.idx == idx)[0]
        $(data._reset_list).each (idx, entry) ->
            scope_obj[entry[0]] = entry[1]
        delete data._reset_list

   
simple_modal_ctrl = ($scope, $modalInstance, question) ->
    $scope.question = question
    $scope.ok = () ->
        $modalInstance.close(true)
    $scope.cancel = () ->
        $modalInstance.dismiss("cancel")

simple_modal_template = """
<div class="modal-header"><h3>Please confirm</h3></div>
<div class="modal-body">
    {% verbatim %}{{ question }}{% endverbatim %}
</div>
<div class="modal-footer">
    <button class="btn btn-primary" ng-click="ok()">OK</button>
    <button class="btn btn-warning" ng-click="cancel()">Cancel</button>
</div>
"""

enter_password_template = """
<div class="modal-header"><h3>Please enter the new password</h3></div>
<div class="modal-body">
    <form name="form">
        <div ng-class="dyn_check(pwd.pwd1)">
            <label>Password:</label>
            <input type="password" ng-model="pwd.pwd1" placeholder="enter password" class="form-control"></input>
        </div>
        <div ng-class="dyn_check(pwd.pwd2)">
            <label>again:</label>
            <input type="password" ng-model="pwd.pwd2" placeholder="confirm password" class="form-control"></input>
        </div>
    </form>
</div>
<div class="modal-footer">
    <div ng-class="pwd_error_class">
       {% verbatim %}
           {{ pwd_error }}
       {% endverbatim %}
    </div>
    <div>
        <button class="btn btn-primary" ng-click="check()">Check</button>
        <button class="btn btn-success" ng-click="ok()" ng-show="check()">Save</button>
        <button class="btn btn-warning" ng-click="cancel()">Cancel</button>
    </div>
</div>
"""

angular_add_simple_list_controller = (module, name, settings) ->
    $(settings.template_cache_list).each (idx, t_name) ->
        short_name = t_name.replace(/.html$/g, "").replace(/_/g, "")
        module.directive(short_name, ($templateCache) ->
            return {
                restrict : "EA"
                template : $templateCache.get(t_name)
            }
        )
    module.directive("edittemplate", ($compile, $templateCache) ->
        return {
            restrict : "EA"
            template : $templateCache.get(settings.edit_template)
            link : (scope, element, attrs) ->
                scope.form_error = (field_name) ->
                    if scope.form[field_name].$valid
                        return ""
                    else
                        return "has-error"
        }
    )
    module.run(($templateCache) ->
        $templateCache.put("simple_confirm.html", simple_modal_template)
    )
    module.controller(name, ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$timeout", "$modal", 
        ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $timeout, $modal) ->
            # set reference
            $scope.settings = settings
            $scope.settings.use_modal ?= true
            # shortcut to fn
            $scope.fn = settings.fn
            # init pagSettings
            $scope.pagSettings = paginatorSettings.get_paginator(name, $scope)
            # list of entries
            $scope.entries = []
            # init form
            $scope.form = {}
            $scope.shared_data = sharedDataSource.data
            if $scope.settings.rest_url
                $scope.rest = Restangular.all($scope.settings.rest_url.slice(1))
                $scope.settings.rest_options ?= {}
                wait_list = [restDataSource.add_sources([[$scope.settings.rest_url, $scope.settings.rest_options]])[0]]
            else
                wait_list = []
            $scope.rest_data = {}
            $scope.modal_active = false
            if $scope.settings.rest_map
                for value, idx in $scope.settings.rest_map
                    $scope.rest_data[value.short] = restDataSource.load([value.url, value.options])
                    wait_list.push($scope.rest_data[value.short])
            $q.all(wait_list).then((data) ->
                base_idx = if $scope.settings.rest_url then 0 else -1
                for value, idx in data
                    if idx == base_idx
                        $scope.set_entries(value, true)
                    else
                        $scope.rest_data[$scope.settings.rest_map[idx - (1 + base_idx)].short] = value
                if $scope.fn and $scope.fn.rest_data_set
                    $scope.fn.rest_data_set($scope)
            )
            $scope.load_data = (url, options) ->
                return Restangular.all(url.slice(1)).getList(options)
            $scope.reload = () ->
                # only reload primary rest, nothing from rest_map
                restDataSource.reload([$scope.settings.rest_url, $scope.settings.rest_options]).then((data) ->
                    $scope.set_entries(data)
                )
            $scope.set_entries = (data, ignore_rest_data_set) ->
                if $scope.settings.entries_filter
                    $scope.entries = $filter("filter")(data, $scope.settings.entries_filter)
                else
                    $scope.entries = data
                if not ignore_rest_data_set and $scope.fn and $scope.fn.rest_data_set
                    $scope.fn.rest_data_set($scope)
            $scope.modify = () ->
                if not $scope.form.$invalid
                    if $scope.create_mode
                        $scope.rest.post($scope.new_obj).then((new_data) ->
                            $scope.entries.push(new_data)
                            if $scope.pagSettings.conf.init
                                $scope.pagSettings.set_entries($scope.entries)
                            $scope.close_modal()
                            if $scope.settings.object_created
                                $scope.settings.object_created($scope.new_obj, new_data, $scope)
                        )
                    else
                        $scope.edit_obj.put($scope.settings.rest_options).then(
                            (data) -> 
                                handle_reset(data, $scope.entries, $scope.edit_obj.idx)
                                if $scope.fn and $scope.fn.object_modified
                                    $scope.fn.object_modified($scope.edit_obj, data, $scope)
                                $scope.close_modal()
                            (resp) -> handle_reset(resp.data, $scope.entries, $scope.edit_obj.idx)
                        )
                else
                    noty
                        text : "form validation problem"
                        type : "warning"
            $scope.form_error = (field_name) ->
                if $scope.form[field_name].$valid
                    return ""
                else
                    return "has-error"
            $scope.create = (event) ->
                if typeof($scope.settings.new_object) == "function"
                    $scope.new_obj = $scope.settings.new_object($scope)
                else
                    $scope.new_obj = $scope.settings.new_object
                $scope.create_or_edit(event, true, $scope.new_obj)
            $scope.edit = (event, obj) ->
                $scope.pre_edit_obj = angular.copy(obj)
                $scope.create_or_edit(event, false, obj)
            $scope.create_or_edit = (event, create_or_edit, obj) ->
                $scope.edit_obj = obj
                $scope.create_mode = create_or_edit
                if $scope.fn and $scope.fn.create_or_edit
                    $scope.fn.create_or_edit($scope, $scope.create_mode, obj)
                if $scope.settings.use_modal
                    $scope.edit_div = $compile($templateCache.get($scope.settings.edit_template))($scope)
                    $scope.edit_div.simplemodal
                        #opacity      : 50
                        position     : [event.pageY, event.pageX]
                        #autoResize   : true
                        #autoPosition : true
                        onShow: (dialog) => 
                            dialog.container.draggable()
                            $("#simplemodal-container").css("height", "auto")
                            $scope.modal_active = true
                        onClose: (dialog) =>
                            $scope.close_modal()
                else
                    $scope.modal_active = true
            $scope.hide_modal = () ->
                # hides dummy modal
                if not $scope.fn.use_modal and $scope.modal_active
                    $scope.modal_active = false
            $scope.close_modal = () ->
                if $scope.settings.use_modal
                    $.simplemodal.close()
                $scope.modal_active = false
                if $scope.fn and $scope.fn.modal_closed
                    $scope.fn.modal_closed($scope)
                    if $scope.settings.use_modal
                        try
                            # fixme, call digest cycle and ignore if cycle is already running
                            $scope.$digest()
                        catch exc
            $scope.get_action_string = () ->
                return if $scope.create_mode then "Create" else "Modify"
            $scope.delete = (obj) ->
                c_modal = $modal.open
                    template : $templateCache.get("simple_confirm.html")
                    controller : simple_modal_ctrl
                    backdrop : "static"
                    resolve :
                        question : () ->
                            return $scope.settings.delete_confirm_str(obj)
                c_modal.result.then(
                    () ->
                        obj.remove().then((resp) ->
                            noty
                                text : "deleted instance"
                            remove_by_idx($scope.entries, obj.idx)
                            if $scope.pagSettings.conf.init
                                $scope.pagSettings.set_entries($scope.entries)
                            if $scope.settings.post_delete
                                $scope.settings.post_delete($scope, obj)
                        )
                )
            # call the external init function after the rest has been declared
            if $scope.settings.init_fn
                $scope.settings.init_fn($scope, $timeout)
    ])

angular.module(
    "init.csw.filters", []
).filter(
    "resolve_n2m", () ->
        return (in_array, f_array, n2m_key, null_msg) ->
            if typeof(in_array) == "string"
                # handle strings for chaining
                in_array = (parseInt(value) for value in in_array.split(/,\s*/))
            res = (value for key, value of f_array when typeof(value) == "object" and value and value.idx in in_array)
            #ret_str = (f_array[key][n2m_key] for key in in_array).join(", ")
            if res.length
                return (value[n2m_key] for value in res).join(", ")
            else
                if null_msg
                    return null_msg
                else
                    return "N/A"

).filter(
    "follow_fk", () ->
        return (in_value, scope, fk_model, fk_key, null_msg) ->
            if in_value != null
                return scope[fk_model][in_value][fk_key]
            else
                return null_msg
).filter(
    "array_length", () ->
        return (array) ->
            return array.length
).filter(
    "array_lookup", () ->
        return (in_value, f_array, fk_key, null_msg) ->
            if in_value != null
                if fk_key
                    res_list = (entry[fk_key] for key, entry of f_array when typeof(entry) == "object" and entry and entry["idx"] == in_value)
                else
                    res_list = (entry for key, entry of f_array when typeof(entry) == "object" and entry and entry["idx"] == in_value)
                return if res_list.length then res_list[0] else "Key Error (#{in_value})"
            else
                return if null_msg then null_msg else "N/A"
).filter(
    "exclude_device_groups", () ->
        return (in_array) ->
            return (entry for entry in in_array when entry.is_meta_device == false)
).filter(
    "ip_fixed_width", () ->
        return (in_str) ->
            if in_str
                ip_field = in_str.split(".")
            else
                ip_field = ["?", "?", "?", "?"]
            return ("QQ#{part}".substr(-3, 3) for part in ip_field).join(".").replace(/Q/g, "&nbsp;")
).filter(
    "range", () ->
        return (in_value, upper_value) ->
            return (_val for _val in [1..parseInt(upper_value)])
).filter(
    "yesno1", () ->
        return (in_value) ->
            return if in_value then "yes" else "---"
).filter(
    "yesno2", () ->
        return (in_value) ->
            return if in_value then "yes" else "no"
).filter("limit_text", () ->
    return (text, max_len) ->
        if text.length > max_len
            return text[0..max_len] + "..."
        else
            return text
).filter("show_user", () ->
    return (user) ->
        if user
            if user.first_name and user.last_name
                return "#{user.login} (#{user.first_name} #{user.last_name})"
            else if user.first_name
                return "#{user.login} (#{user.first_name})"
            else if user.last_name
                return "#{user.login} (#{user.last_name})"
            else
                return "#{user.login}"
        else
            # in case user is undefined
            return "???"
).filter("show_dtn", () ->
    return (cur_dtn) ->
        r_str = if cur_dtn.node_postfix then "#{cur_dtn.node_postfix}" else ""
        if cur_dtn.depth
            r_str = "#{r_str}.#{cur_dtn.full_name}"
        else
            r_str = "#{r_str} [TLN]"
        return r_str
).filter("datetime1", () ->
    return (cur_dt) ->
        return moment(cur_dt).format("ddd, D. MMM YYYY, HH:mm:ss") + ", " + moment(cur_dt).fromNow()
).filter("get_size", () ->
    return (size, base_factor, factor) ->
        size = size * base_factor
        f_idx = 0
        while size > factor
            size = parseInt(size/factor)
            f_idx += 1
        factor = ["", "k", "M", "G", "T", "P", "E"][f_idx]
        return "#{size} #{factor}B"
)

class angular_edit_mixin
    constructor : (@scope, @templateCache, @compile, @modal, @Restangular, @q) ->
        @use_modal = true
        @new_object_at_tail = true
        @use_promise = false
        @min_width = "600px"
    create : (event) =>
        if @new_object
            @scope.new_obj = @new_object(@scope)
        else
            @scope.new_obj = {}
        @create_or_edit(event, true, @scope.new_obj)
    send_change_signal : () =>
        if @change_signal
            @scope.$emit(@change_signal)
    edit : (obj, event) =>
        @create_or_edit(event, false, obj)
    modify_data_before_put: (data) =>
        # dummy, override in app
    modify_data_after_post: (data) =>
        # dummy, override in app
    create_or_edit : (event, create_or_edit, obj) =>
        @scope._edit_obj = obj
        @scope.pre_edit_obj = angular.copy(obj)
        @scope.create_mode = create_or_edit
        @scope.cur_edit = @
        if not @scope.create_mode
            @Restangular.restangularizeElement(null, @scope._edit_obj, @modify_rest_url)
        @scope.action_string = if @scope.create_mode then "Create" else "Modify"
        if @use_promise
           @_prom = @q.defer()
        if @use_modal
            @edit_div = @compile(@templateCache.get(if @scope.create_mode then @create_template else @edit_template))(@scope)
            @edit_div.simplemodal
                #opacity      : 50
                position     : [event.pageY, event.pageX]
                minWidth : @min_width
                #autoResize   : true
                #autoPosition : true
                onShow: (dialog) => 
                    dialog.container.draggable()
                    $("#simplemodal-container").css("height", "auto")
                    @_modal_close_ok = false
                    @scope.modal_active = true
                onClose: (dialog) =>
                    @close_modal()
        else
            @scope.modal_active = true
        if @use_promise
            return @_prom.promise
    close_modal : () =>
        if @use_modal
            $.simplemodal.close()
        #console.log scope.pre_edit_obj.pnum, scope._edit_obj.pnum
        if @scope.modal_active
            #console.log "*", @_modal_close_ok, @scope.pre_edit_obj
            if not @_modal_close_ok and not @scope.create_mode
                # not working right now, hm ...
                true
                #@scope._edit_obj = angular.copy(@scope.pre_edit_obj)
                #console.log @scope._edit_obj.pnum, @scope.pre_edit_obj.pnum
                #@scope._edit_obj.pnum = 99
                #console.log @scope._edit_obj, @scope.pre_edit_obj
        @scope.modal_active = false
        if @edit_div
            @edit_div.remove()
    form_error : (field_name) =>
        if @scope.form[field_name].$valid
            return ""
        else
            return "has-error"
    modify : () ->
        if not @scope.form.$invalid
            if @scope.create_mode
                @create_rest_url.post(@scope.new_obj).then(
                    (new_data) =>
                        if @create_list
                            if @new_object_at_tail
                                @create_list.push(new_data)
                            else
                                @create_list.splice(0, 0, new_data)
                        @modify_data_after_post(new_data)
                        @close_modal()
                        @_modal_close_ok = true
                        if @use_promise
                            return @_prom.resolve(new_data)
                        else
                            @send_change_signal()       
                    () ->        
                        if @use_promise
                            return @_prom.resolve(false)
                )
            else
                @modify_data_before_put(@scope._edit_obj)
                @scope._edit_obj.put().then(
                    (data) =>
                        handle_reset(data, @scope._edit_obj, null)
                        @_modal_close_ok = true
                        @close_modal()
                        if @use_promise
                            return @_prom.resolve(data)
                        else
                            @send_change_signal()                
                    (resp) =>
                        if @use_promise
                            return @_prom.resolve(false)
                        else
                            handle_reset(resp.data, @scope._edit_obj, null)
                )
        else
            noty
                text : "form validation problem"
                type : "warning"
    modal_ctrl : ($scope, $modalInstance, question) ->
        $scope.question = question
        $scope.ok = () ->
            $modalInstance.close(true)
        $scope.cancel = () ->
            $modalInstance.dismiss("cancel")
    delete_obj : (obj) =>
        if @use_promise
           ret = @q.defer()
        c_modal = @modal.open
            template : @templateCache.get("simple_confirm.html")
            controller : @modal_ctrl
            backdrop : "static"
            resolve :
                question : () =>
                    if @delete_confirm_str
                        return @delete_confirm_str(obj)
                    else
                        return "Really delete object ?"
        c_modal.result.then(
            () =>
                # add restangular elements
                @Restangular.restangularizeElement(null, obj, @modify_rest_url)
                obj.remove().then(
                    (resp) =>
                        noty
                            text : "deleted instance"
                        if @delete_list
                            remove_by_idx(@delete_list, obj.idx)
                        @close_modal()
                        if @use_promise
                            return ret.resolve(true)
                        else
                            @send_change_signal()
                    () =>
                        if @use_promise
                            return ret.resolve(false)
                )
            () =>
                if @use_promise
                    return ret.resolve(false)
        )
        if @use_promise
            return ret.promise

class angular_modal_mixin
    constructor : (@scope, @templateCache, @compile, @modal, @Restangular, @q) ->
        @min_width = "600px"
    edit : (obj, event) =>
        @scope._edit_obj = obj
        @scope.cur_edit = @
        @_prom = @q.defer()
        @edit_div = @compile(@templateCache.get(@template))(@scope)
        @edit_div.simplemodal
            #opacity      : 50
            position     : [event.pageY, event.pageX]
            minWidth : @min_width
            #autoResize   : true
            #autoPosition : true
            onShow: (dialog) => 
                dialog.container.draggable()
                $("#simplemodal-container").css("height", "auto")
                @_modal_close_ok = false
                @scope.modal_active = true
            onClose: (dialog) =>
                @close_modal()
        return @_prom.promise
    close_modal : () =>
        $.simplemodal.close()
        @scope.modal_active = false
    form_error : (field_name) =>
        if @scope.form[field_name].$valid
            return ""
        else
            return "has-error"
    modify : () ->
        if not @scope.form.$invalid
            @close_modal()
            return @_prom.resolve(@scope._edit_obj)
        else
            noty
                text : "form validation problem"
                type : "warning"

root = exports ? this
root.angular_edit_mixin = angular_edit_mixin
root.angular_modal_mixin = angular_modal_mixin
root.angular_module_setup = angular_module_setup
root.handle_reset = handle_reset
root.angular_add_simple_list_controller = angular_add_simple_list_controller
root.build_lut = build_lut
root.simple_modal_template = simple_modal_template

{% endinlinecoffeescript %}

</script>


