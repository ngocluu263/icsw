{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

{% verbatim %}

icsw_paginator = '
<form class="form-inline">
    <span ng-show="pagSettings.conf.filtered_len">
        <div class="form-group">
            <ul class="pagination pagination-sm" ng-show="pagSettings.conf.num_pages > 1"  style="margin-top:0px; margin-bottom:0px;">
                <li ng-repeat="pag_num in pagSettings.conf.page_list track by $index" ng-class="pagSettings.get_li_class(pag_num)">
                    <a href="#" ng-click="activate_page(pag_num)">{{ pag_num }}</a>
                </li>
            </ul>
        </div>
        <span ng-show="pagSettings.conf.num_pages > 1">, </span>
        showing entries {{ pagSettings.conf.start_idx + 1 }} to {{ pagSettings.conf.end_idx + 1 }},
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
'

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
            filter_mode      : false
            filter           : undefined
            filter_func      : undefined
            filter_settings  : @$scope.settings.filter_settings
        }
    activate_page: (num) =>
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
        @conf.unfiltered_len = el_list.length
        el_list = @apply_filter(el_list)
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
        cur_mod.config(['$httpProvider', 
            ($httpProvider) ->
                $httpProvider.defaults.xsrfCookieName = 'csrftoken'
                $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken'
        ])
        cur_mod.filter("paginator", ["$filter", ($filter) ->
            return (arr, scope) ->
                if scope.pagSettings.conf.init 
                    arr = scope.pagSettings.apply_filter(arr)
                    return arr.slice(scope.pagSettings.conf.start_idx, scope.pagSettings.conf.end_idx + 1)
                else
                    return arr
        ])
        cur_mod.filter("paginator_filter", ["$filter", ($filter) ->
            return (arr, scope) ->
                return scope.pagSettings.apply_filter(arr)
        ])
        cur_mod.config(["RestangularProvider", 
            (RestangularProvider) ->
                RestangularProvider.setRestangularFields({
                    "id" : "idx"
                })
                RestangularProvider.setResponseInterceptor((data, operation, what, url, response, deferred) ->
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
                    if typeof(resp.data) == "string"
                        if resp.data
                            resp.data = {"error" : resp.data}
                        else
                            resp.data = {}
                    for key, value of resp.data
                        if (typeof(value) == "object" or typeof(value) == "string") and (not key.match(/^_/) or key == "__all__")
                            key_str = if key == "__all__" then "error: " else "#{key} : "
                            noty
                                text : key_str + if typeof(value) == "string" then value else value.join(", ")
                                type : "error"
                                timeout : false
                    return true
                )
        ])
        # in fact identical ?
        # cur_mod.service("paginatorSettings", (paginator_class))
        cur_mod.service("paginatorSettings", ["$filter", ($filter) ->
            return new paginator_root($filter)
        ])
        cur_mod.service("restDataSource", ["$q", "Restangular", ($q, Restangular) ->
            return new rest_data_source($q, Restangular)
        ])
        cur_mod.service("sharedDataSource", [() ->
            return new shared_data_source()
        ])
        cur_mod.directive("paginator", ($templateCache) ->
            link = (scope, element, attrs) ->
                scope.pagSettings.conf.per_page = parseInt(attrs.perPage)
                #scope.pagSettings.conf.filter = attrs.paginatorFilter
                if attrs.paginatorEpp
                    scope.pagSettings.set_epp(attrs.paginatorEpp)
                if attrs.paginatorFilter
                    scope.pagSettings.conf.filter_mode = attrs.paginatorFilter
                    if scope.pagSettings.conf.filter_mode == "simple"
                        scope.pagSettings.conf.filter = ""
                    else if scope.pagSettings.conf.filter_mode == "func"
                        scope.pagSettings.conf.filter_func = scope.filterFunc
                scope.activate_page = (page_num) ->
                    scope.pagSettings.activate_page(page_num)
                scope.$watch(
                    () -> return scope.entries
                    (new_el) ->
                        scope.pagSettings.set_entries(new_el)
                )
                scope.$watch(
                    () -> return scope.pagSettings.conf.filter
                    (new_el) ->
                        scope.pagSettings.set_entries(scope.entries)
                )
                scope.$watch(
                    () -> return scope.pagSettings.conf.per_page
                    (new_el) ->
                        scope.pagSettings.set_entries(scope.entries)
                )
                scope.$watch(
                    () -> return scope.pagSettings.conf.filter_settings
                    (new_el) ->
                        scope.pagSettings.set_entries(scope.entries)
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

simple_modal_template = '
<div class="modal-header"><h3>Please confirm</h3></div>
<div class="modal-body">
    {% verbatim %}{{ question }}{% endverbatim %}
</div>
<div class="modal-footer">
    <button class="btn btn-primary" ng-click="ok()">OK</button>
    <button class="btn btn-warning" ng-click="cancel()">Cancel</button>
</div>
'

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
    "yesno1", () ->
        return (in_value) ->
            return if in_value then "yes" else "---"
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
)

root = exports ? this
root.angular_module_setup = angular_module_setup
root.handle_reset = handle_reset
root.angular_add_simple_list_controller = angular_add_simple_list_controller
root.build_lut = build_lut

{% endinlinecoffeescript %}

</script>


