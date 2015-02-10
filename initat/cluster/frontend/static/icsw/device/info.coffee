device_info_module = angular.module(
    "icsw.device.info",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "noVNC", "ui.select", "icsw.tools", "icsw.device.variables"
    ]
).controller("icswDeviceInfoOverviewCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q", "$timeout", "$window", "msgbus", "access_level_service", "ICSW_URLS",
    ($scope, $compile, $filter, $templateCache, Restangular, $q, $timeout, $window, msgbus, access_level_service, ICSW_URLS) ->
        access_level_service.install($scope)
        $scope.active_div = "general"
        $scope.show = false
        $scope.permissions = undefined
        $scope.devicepk = undefined
        msgbus.emit("devselreceiver")
        msgbus.receive("devicelist", $scope, (name, args) ->
            $scope.dev_pk_list = args[0]
            $scope.dev_pk_nmd_list = args[1]
            $scope.devg_pk_list = args[2]
            $scope.dev_pk_md_list = args[3]
            $scope.addon_devices = []
            if $scope.dev_pk_list.length
                $scope.show = true
                $scope.fetch_info()
            else
                $scope.show = false
        )
        $scope.fetch_info = () ->
            wait_list = [
                Restangular.one(ICSW_URLS.REST_DEVICE_DETAIL.slice(1).slice(0, -2), $scope.dev_pk_list[0]).get()
                Restangular.one(ICSW_URLS.REST_MIN_ACCESS_LEVELS.slice(1)).get( {"obj_type": "device", "obj_list": angular.toJson($scope.dev_pk_list)})
            ]
            # access levels needed ?
            $q.all(wait_list).then((data) ->
                $scope.show_div(data[0], data[1])
            )
        $scope.show_div = (json, access_json) ->
            $scope.devicepk = json.idx
            $scope.permissions = access_json
            $scope.show = true
]).service(
    "DeviceOverviewService",
    [
        "Restangular", "$rootScope", "$templateCache", "$compile", "$modal", "$q", "access_level_service", "msgbus",
        (Restangular, $rootScope, $templateCache, $compile, $modal, $q, access_level_service, msgbus) ->
            return {
                "NewSingleSelection" : (dev) ->
                    if dev.device_type_identifier == "MD"
                        msgbus.emit("devicelist", [[dev.idx], [], [], [dev.idx]])
                    else
                        msgbus.emit("devicelist", [[dev.idx], [dev.idx], [], []])
                "NewOverview" : (event, dev) ->
                    # create new modal for device
                    # device object with access_levels
                    sub_scope = $rootScope.$new()
                    access_level_service.install(sub_scope)
                    dev_idx = dev.idx
                    sub_scope.devicepk = dev_idx
                    sub_scope.disable_modal = true
                    if dev.device_type_identifier == "MD"
                        sub_scope.dev_pk_list = [dev_idx]
                        sub_scope.dev_pk_nmd_list = []
                    else
                        sub_scope.dev_pk_list = [dev_idx]
                        sub_scope.dev_pk_nmd_list = [dev_idx]
                    my_mixin = new angular_modal_mixin(
                        sub_scope,
                        $templateCache,
                        $compile
                        $modal
                        Restangular
                        $q
                    )
                    my_mixin.min_width = "800px"
                    my_mixin.template = "DeviceOverviewTemplate"
                    my_mixin.edit(null, dev_idx)
                    # todo: destroy sub_scope
            }
    ]
).run(["$templateCache", ($templateCache) ->
    $templateCache.put(
        "DeviceOverviewTemplate",
        "<deviceoverview devicepk='devicepk'></deviceoverview>"
    )
]).service("DeviceOverviewSettings", [() ->
    def_mode = ""
    return {
        "get_mode" : () ->
            return def_mode
        "set_mode": (mode) ->
            def_mode = mode
    }
]).directive("deviceoverview", ["$compile", "DeviceOverviewSettings", "$templateCache", ($compile, DeviceOverviewSettings, $templateCache) ->
    return {
        restrict: "EA"
        replace: true
        compile: (element, attrs) ->
            return (scope, iElement, iAttrs) ->
                scope.current_subscope = undefined
                scope.pk_list = {
                    "category": []
                    "location": []
                    "network": []
                    "config": []
                    "partinfo": []
                    "variables": []
                    "status_history": []
                    "livestatus": []
                    "monconfig": []
                    "graphing": []
                }
                scope["general_active"] = true
                for key of scope.pk_list
                    scope["#{key}_active"] = false
                scope.active_div = DeviceOverviewSettings.get_mode()
                if scope.active_div
                    scope["#{scope.active_div}_active"] = true
                if attrs["multi"]?
                    # possibly multi-device view
                    scope.multi_device = true
                    scope.$watch("dev_pk_list", (new_val) ->
                        if new_val and new_val.length
                            scope.devicepk = new_val[0]
                            scope.new_device_sel()
                    )
                else
                    scope.multi_device = false
                    scope.$watch(attrs["devicepk"], (new_val) ->
                        if new_val
                            scope.devicepk = new_val
                            scope.new_device_sel()
                    )
                scope.new_device_sel = () ->
                    if scope.dev_pk_list.length > 1
                        scope.addon_text = " (#{scope.dev_pk_list.length})"
                    else
                        scope.addon_text = ""
                    if scope.dev_pk_nmd_list.length > 1
                        scope.addon_text_nmd = " (#{scope.dev_pk_nmd_list.length})"
                    else
                        scope.addon_text_nmd = ""
                    # destroy old subscope, important
                    if scope.current_subscope
                        scope.current_subscope.$destroy()
                    new_scope = scope.$new()
                    new_el = $compile($templateCache.get("icsw.device.info"))(new_scope)
                    iElement.children().remove()
                    iElement.append(new_el)
                    scope.current_subscope = new_scope
                scope.activate = (name) ->
                    DeviceOverviewSettings.set_mode(name)
                    if name in ["category", "location", "network", "partinfo", "status_history", "livestatus", "monconfig"]
                        scope.pk_list[name] = scope.dev_pk_nmd_list
                    else if name in ["config", "variables", "graphing"]
                        scope.pk_list[name] = scope.dev_pk_list
    }
]).controller("deviceinfo_ctrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "access_level_service",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, access_level_service) ->
        access_level_service.install($scope)
        $scope.show_uuid = false
        $scope.image_url = ""
        $scope.get_image_src = () ->
            img_url = ""
            if $scope._edit_obj.mon_ext_host
                for entry in $scope.mon_ext_host_list
                    if entry.idx == $scope._edit_obj.mon_ext_host
                        img_url = entry.data_image
            return img_url
        $scope.toggle_uuid = () ->
            $scope.show_uuid = !$scope.show_uuid
        $scope.modify = () ->
            if not $scope.form.$invalid
                if $scope.acl_modify($scope._edit_obj, "backbone.device.change_basic")
                    if $scope._edit_obj.device_type_identifier == "MD"
                        $scope._edit_obj.name = "METADEV_" + $scope._edit_obj.name
                    $scope._edit_obj.put().then(() ->
                        if $scope._edit_obj.device_type_identifier == "MD"
                            $scope._edit_obj.name = $scope._edit_obj.name.substr(8)
                        # selectively reload sidebar tree
                        reload_sidebar_tree([$scope._edit_obj.idx])
                    )
            else
                noty
                    text : "form validation problem"
                    type : "warning"
]).directive("deviceinfo", ["$templateCache", "$compile", "$modal", "Restangular", "restDataSource", "$q", "ICSW_URLS", ($templateCache, $compile, $modal, Restangular, restDataSource, $q, ICSW_URLS) ->
    return {
        restrict : "EA"
        # bugfix for ui-select2, not working ...
        #priority : 2
        link : (scope, element, attrs) ->
            scope._edit_obj = null
            scope.device_pk = null
            scope.$on("$destroy", () ->
            )
            scope.$watch(attrs["devicepk"], (new_val) ->
                if new_val
                    scope.device_pk = new_val
                    wait_list = [
                        restDataSource.reload([ICSW_URLS.REST_DOMAIN_TREE_NODE_LIST, {}])
                        restDataSource.reload([ICSW_URLS.REST_MON_DEVICE_TEMPL_LIST, {}])
                        restDataSource.reload([ICSW_URLS.REST_MON_EXT_HOST_LIST, {}])
                        restDataSource.reload([ICSW_URLS.REST_DEVICE_TREE_LIST, {"with_network" : true, "with_monitoring_hint" : true, "with_disk_info" : true, "pks" : angular.toJson([scope.device_pk]), "ignore_cdg" : false}])
                    ]
                    $q.all(wait_list).then((data) ->
                        #form = data[0][0].form
                        scope.domain_tree_node = data[0]
                        scope.mon_device_templ_list = data[1]
                        scope.mon_ext_host_list = data[2]
                        scope._edit_obj = data[3][0]
                        if scope._edit_obj.device_type_identifier == "MD"
                            scope._edit_obj.name = scope._edit_obj.name.substr(8)
                        element.append($compile($templateCache.get("device.info.form"))(scope))
                    )
            )
            scope.is_device = () ->
                return if scope._edit_obj.device_type_identifier in ["MD"] then false else true
            scope.get_monitoring_hint_info = () ->
                if scope._edit_obj.monitoring_hint_set.length
                    mhs = scope._edit_obj.monitoring_hint_set
                    return "#{mhs.length} (#{(entry for entry in mhs when entry.check_created).length} used for service checks)"
                else
                    return "---"
            scope.get_ip_info = () ->
                if scope._edit_obj?
                    ip_list = []
                    for _nd in scope._edit_obj.netdevice_set
                        for _ip in _nd.net_ip_set
                            ip_list.push(_ip.ip)
                    if ip_list.length
                        return ip_list.join(", ")
                    else
                        return "none"
                else
                    return "---"
            scope.get_snmp_scheme_info = () ->
                if scope._edit_obj?
                    _sc = scope._edit_obj.snmp_schemes
                    if _sc.length
                        return ("#{_entry.snmp_scheme_vendor.name}.#{_entry.name}" for _entry in _sc).join(", ")
                    else
                        return "none"
                else
                    return "---"
            scope.get_snmp_info = () ->
                if scope._edit_obj?
                    _sc = scope._edit_obj.DeviceSNMPInfo
                    if _sc
                        return _sc.description
                    else
                        return "none"
                else
                    return "---"
    }
])