# Copyright (C) 2012-2016 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
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

monitoring_basic_module = angular.module("icsw.monitoring.monitoring_basic",
[
    "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select",
    "icsw.tools.table", "icsw.tools.button"
]).directive("icswMonitoringBasic",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict:"EA"
        template: $templateCache.get("icsw.monitoring.basic")
        controller: "icswMonitoringBasicCtrl"
    }
]).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.monitorbasics", {
            url: "/monitorbasics"
            template: "<icsw-monitoring-basic></icsw-monitoring-basic>"
            data:
                pageTitle: "Monitoring Basic setup"
                menuHeader:
                    key: "mon"
                    name: "Monitoring"
                    icon: "fa-gears"
                    ordering: 70
                rights: ["mon_check_command.setup_monitoring"]
                menuEntry:
                    menukey: "mon"
                    name: "Basic setup"
                    icon: "fa-bars"
                    ordering: 0
        }
    )
    $stateProvider.state(
        "main.monitorredirect", {
            url: "/monitorredirect"
            template: "<h2>Redirecting...</h2>"
            data:
                menuEntry:
                    menukey: "mon"
                    name: "Icinga"
                    icon: "fa-share-alt"
                    ordering: 120
            resolve:
                redirect: ["$window", "icswSimpleAjaxCall", "ICSW_URLS", "$q", ($window, icswSimpleAjaxCall, ICSW_URLS, $q) ->
                    _defer = $q.defer()
                    icswSimpleAjaxCall(
                        url: ICSW_URLS.MON_CALL_ICINGA
                        dataType: "json"
                    ).then(
                        (json) ->
                            url = json["url"]
                            $window.open(url, "_blank")
                            _defer.reject("nono")
                    )
                    return _defer.promise
                ]
        }
    )
    $stateProvider.state(
        "main.monitorb0", {
            url: "/monitorb0"
            data:
                menuEntry:
                    menukey: "mon"
                    name: "rebuild config cached"
                    icon: "fa-share-alt"
                    ordering: 101
            resolve:
                redirect: ["icswSimpleAjaxCall", "ICSW_URLS", "$q", "blockUI", (icswSimpleAjaxCall, ICSW_URLS, $q, blockUI) ->
                    # todo: add icswMenuProgressService
                    _defer = $q.defer()
                    blockUI.start()
                    icswSimpleAjaxCall(
                        url: ICSW_URLS.MON_CREATE_CONFIG
                        data:
                            "cache_mode": "ALWAYS"
                        title: "create config"
                    ).then(
                        (xml) ->
                            blockUI.stop()
                            _defer.reject("nono")
                        (xml) ->
                            blockUI.stop()
                            _defer.reject("nono")
                    )
                    return _defer.promise
                ]
        }
    )
    $stateProvider.state(
        "main.monitorb1", {
            url: "/monitorb1"
            data:
                menuEntry:
                    menukey: "mon"
                    name: "rebuild config dynamic"
                    icon: "fa-share-alt"
                    ordering: 102
            resolve:
                redirect: ["icswSimpleAjaxCall", "ICSW_URLS", "$q", "blockUI", (icswSimpleAjaxCall, ICSW_URLS, $q, blockUI) ->
                    _defer = $q.defer()
                    blockUI.start()
                    icswSimpleAjaxCall(
                        url: ICSW_URLS.MON_CREATE_CONFIG
                        data:
                            "cache_mode": "DYNAMIC"
                        title: "create config"
                    ).then(
                        (xml) ->
                            blockUI.stop()
                            _defer.reject("nono")
                        (xml) ->
                            blockUI.stop()
                            _defer.reject("nono")
                    )
                    return _defer.promise
                ]
        }
    )
    $stateProvider.state(
        "main.monitorb2", {
            url: "/monitorb2"
            data:
                menuEntry:
                    menukey: "mon"
                    name: "rebuild config refresh"
                    icon: "fa-share-alt"
                    ordering: 103
            resolve:
                redirect: ["icswSimpleAjaxCall", "ICSW_URLS", "$q", "blockUI", (icswSimpleAjaxCall, ICSW_URLS, $q, blockUI) ->
                    _defer = $q.defer()
                    blockUI.start()
                    icswSimpleAjaxCall(
                        url: ICSW_URLS.MON_CREATE_CONFIG
                        data:
                            "cache_mode": "REFRESH"
                        title: "create config"
                    ).then(
                        (xml) ->
                            blockUI.stop()
                            _defer.reject("nono")
                        (xml) ->
                            blockUI.stop()
                            _defer.reject("nono")
                    )
                    return _defer.promise
                ]
        }
    )
]).service("icswMonitoringBasicTree",
[
    "$q", "Restangular", "ICSW_URLS", "ICSW_SIGNALS", "icswTools",
(
    $q, Restangular, ICSW_URLS, ICSW_SIGNALS, icswTools
) ->
    ELIST = [
        "mon_period", "mon_notification",
        "host_check_command", "mon_check_command",
        "mon_check_command_special",
        "mon_service_templ", "mon_device_templ",
        "mon_contact", "mon_contactgroup",
        "mon_ext_host"
    ]
    class icswMonitoringBasicTree
        constructor: (args...) ->
            for entry in ELIST
                @["#{entry}_list"] = []
            @update(args...)

        update: (args...) =>
            for [entry, _list] in _.zip(ELIST, args)
                @["#{entry}_list"].length = 0
                for _el in _list
                    @["#{entry}_list"].push(_el)
            @link()

        link: () =>
            for entry in ELIST
                @["#{entry}_lut"] = _.keyBy(@["#{entry}_list"], "idx")

        # create / delete mon_period

        create_mon_period: (new_per) =>
            d = $q.defer()
            Restangular.all(ICSW_URLS.REST_MON_PERIOD_LIST.slice(1)).post(new_per).then(
                (created) =>
                    @mon_period_list.push(created)
                    @link()
                    d.resolve(created)
                (not_cr) =>
                    d.reject("not created")
            )
            return d.promise

        delete_mon_period: (del_per) =>
            d = $q.defer()
            Restangular.restangularizeElement(null, del_per, ICSW_URLS.REST_MON_PERIOD_DETAIL.slice(1).slice(0, -2))
            del_per.remove().then(
                (removed) ->
                    _.remove(@mon_period_list, (entry) -> return entry.idx == del_per.idx)
                    d.resolve("deleted")
                (not_removed) ->
                    d.resolve("not deleted")
            )
            return d.promise

        # create / delete mon_period

        create_mon_notification: (new_not) =>
            d = $q.defer()
            Restangular.all(ICSW_URLS.REST_MON_NOTIFICATION_LIST.slice(1)).post(new_not).then(
                (created) =>
                    @mon_notification_list.push(created)
                    @link()
                    d.resolve(created)
                (not_cr) =>
                    d.reject("not created")
            )
            return d.promise

        delete_mon_notification: (del_not) =>
            d = $q.defer()
            Restangular.restangularizeElement(null, del_not, ICSW_URLS.REST_MON_NOTIFICATION_DETAIL.slice(1).slice(0, -2))
            del_not.remove().then(
                (removed) ->
                    _.remove(@mon_notification_list, (entry) -> return entry.idx == del_per.idx)
                    d.resolve("deleted")
                (not_removed) ->
                    d.resolve("not deleted")
            )
            return d.promise

        # create / delete mon_service_templ

        create_mon_service_templ: (new_st) =>
            d = $q.defer()
            Restangular.all(ICSW_URLS.REST_MON_SERVICE_TEMPL_LIST.slice(1)).post(new_st).then(
                (created) =>
                    @mon_service_templ_list.push(created)
                    @link()
                    d.resolve(created)
                (not_cr) =>
                    d.reject("not created")
            )
            return d.promise

        delete_mon_service_templ: (del_st) =>
            d = $q.defer()
            Restangular.restangularizeElement(null, del_st, ICSW_URLS.REST_MON_SERVICE_TEMPL_DETAIL.slice(1).slice(0, -2))
            del_st.remove().then(
                (removed) ->
                    _.remove(@mon_service_templ_list, (entry) -> return entry.idx == del_st.idx)
                    d.resolve("deleted")
                (not_removed) ->
                    d.resolve("not deleted")
            )
            return d.promise

]).service("icswMonitoringBasicTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "icswCachingCall", "icswTools", "$rootScope",
    "ICSW_SIGNALS", "icswMonitoringBasicTree",
(
    $q, Restangular, ICSW_URLS, icswCachingCall, icswTools, $rootScope,
    ICSW_SIGNALS, icswMonitoringBasicTree
) ->
    # loads the monitoring tree
    rest_map = [
        [
            ICSW_URLS.REST_MON_PERIOD_LIST, {}
        ]
        [
            ICSW_URLS.REST_MON_NOTIFICATION_LIST, {}
        ]
        [
            ICSW_URLS.REST_HOST_CHECK_COMMAND_LIST, {}
        ]
        [
            ICSW_URLS.REST_MON_CHECK_COMMAND_LIST, {}
        ]
        [
            ICSW_URLS.REST_MON_CHECK_COMMAND_SPECIAL_LIST, {}
        ]
        [
            ICSW_URLS.REST_MON_SERVICE_TEMPL_LIST, {}
        ]
        [
            ICSW_URLS.REST_MON_DEVICE_TEMPL_LIST, {}
        ]
        [
            ICSW_URLS.REST_MON_CONTACT_LIST, {}
        ]
        [
            ICSW_URLS.REST_MON_CONTACTGROUP_LIST, {}
        ]
        [
            ICSW_URLS.REST_MON_EXT_HOST_LIST, {}
        ]
    ]
    _fetch_dict = {}
    _result = undefined
    # load called
    load_called = false

    load_data = (client) ->
        load_called = true
        _wait_list = (icswCachingCall.fetch(client, _entry[0], _entry[1], []) for _entry in rest_map)
        _defer = $q.defer()
        $q.all(_wait_list).then(
            (data) ->
                console.log "*** monitoring tree loaded ***"
                _result = new icswMonitoringBasicTree(data...)
                _defer.resolve(_result)
                for client of _fetch_dict
                    # resolve clients
                    _fetch_dict[client].resolve(_result)
                $rootScope.$emit(ICSW_SIGNALS("ICSW_MON_TREE_LOADED"), _result)
                # reset fetch_dict
                _fetch_dict = {}
        )
        return _defer

    fetch_data = (client) ->
        if client not of _fetch_dict
            # register client
            _defer = $q.defer()
            _fetch_dict[client] = _defer
        if _result
            # resolve immediately
            _fetch_dict[client].resolve(_result)
        return _fetch_dict[client]

    return {
        "load": (client) ->
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
    }
]).controller("icswMonitoringBasicCtrl",
[
    "$scope", "$q", "icswMonitoringBasicTreeService",
(
    $scope, $q, icswMonitoringBasicTreeService
) ->
    $scope.struct = {
        # tree valid
        tree_valid: false
        # basic tree
        basic_tree: undefined
    }
    $scope.reload = () ->
        icswMonitoringBasicTreeService.load($scope.$id).then(
            (data) ->
                $scope.struct.basic_tree = data
                $scope.struct.tree_valid = true
                console.log $scope.struct
        )
    $scope.reload()
]).service('icswMonitoringUtilService', () ->
    return {
        get_data_incomplete_error: (data, tables) ->
            missing = []
            for table_data in tables
                [model_name, human_name] = table_data
                if not data[model_name].length
                    missing.push(human_name)

            if missing.length
                missing_str = ("a #{n}" for n in missing).join(" and ")
                ret = "Please add #{missing_str}"
            else
                ret = ""
            return ret
    }
).service('icswMonitoringBasicRestService', ["ICSW_URLS", "Restangular", (ICSW_URLS, Restangular) ->
    get_rest = (url) ->
        console.log "get url (monitoringbasicrestservice)", url
        return Restangular.all(url).getList().$object
    data = {
        mon_period         : get_rest(ICSW_URLS.REST_MON_PERIOD_LIST.slice(1))
        user               : get_rest(ICSW_URLS.REST_USER_LIST.slice(1))
        mon_notification   : get_rest(ICSW_URLS.REST_MON_NOTIFICATION_LIST.slice(1))
        mon_service_templ  : get_rest(ICSW_URLS.REST_MON_SERVICE_TEMPL_LIST.slice(1))
        host_check_command : get_rest(ICSW_URLS.REST_HOST_CHECK_COMMAND_LIST.slice(1))
        mon_contact        : get_rest(ICSW_URLS.REST_MON_CONTACT_LIST.slice(1))
        device_group       : get_rest(ICSW_URLS.REST_DEVICE_GROUP_LIST.slice(1))
        mon_device_templ   : get_rest(ICSW_URLS.REST_MON_DEVICE_TEMPL_LIST.slice(1))
        mon_contactgroup   : get_rest(ICSW_URLS.REST_MON_CONTACTGROUP_LIST.slice(1))
    }
    return data
]).service("icswMonitoringBasicService",
[
    "icswComplexModalService", "$compile", "$templateCache", "$q", "toaster",
    "Restangular", "ICSW_URLS",
(
    icswComplexModalService, $compile, $templateCache, $q, toaster,
    Restangular, ICSW_URLS,
) ->
    return {
        create_or_edit: (basic_tree, scope, create, obj, obj_name, bu_def, template_name, template_title)  ->
            if not create
                dbu = new bu_def()
                dbu.create_backup(obj)
            sub_scope = scope.$new(false)
            sub_scope.create = create
            sub_scope.edit_obj = obj
            sub_scope.tree = basic_tree
            sub_scope.form_error = (field_name) ->
                if sub_scope.form_data[field_name].$valid
                    return ""
                else
                    return "has-error"

            icswComplexModalService(
                {
                    message: $compile($templateCache.get(template_name))(sub_scope)
                    title: template_title
                    css_class: "modal-wide"
                    ok_label: if create then "Create" else "Modify"
                    closable: true
                    ok_callback: (modal) ->
                        d = $q.defer()
                        if sub_scope.form_data.$invalid
                            toaster.pop("warning", "form validation problem", "", 0)
                            d.reject("form not valid")
                        else
                            if create
                                basic_tree["create_#{obj_name}"](sub_scope.edit_obj).then(
                                    (new_period) ->
                                        d.resolve("created")
                                    (notok) ->
                                        d.reject("not created")
                                )
                            else
                                _URL = ICSW_URLS["REST_" + _.toUpper(obj_name) + "_DETAIL"].slice(1).slice(0, -2)
                                Restangular.restangularizeElement(null, sub_scope.edit_obj, _URL)
                                sub_scope.edit_obj.put().then(
                                    (ok) ->
                                        basic_tree.link()
                                        d.resolve("updated")
                                    (not_ok) ->
                                        d.reject("not updated")
                                )
                        return d.promise
                    cancel_callback: (modal) ->
                        if not create
                            dbu.restore_backup(obj)
                        d = $q.defer()
                        d.resolve("cancel")
                        return d.promise
                }
            ).then(
                (fin) ->
                    sub_scope.$destroy()
            )

    }
]).service("icswMonitoringBasicPeriodService",
[
    "ICSW_URLS", "icswMonitoringBasicTreeService", "$q", "Restangular",
    "icswToolsSimpleModalService", "icswMonPeriodBackup", "icswMonitoringBasicService",
(
    ICSW_URLS, icswMonitoringBasicTreeService, $q, Restangular,
    icswToolsSimpleModalService, icswMonPeriodBackup, icswMonitoringBasicService,
) ->
    basic_tree = undefined
    return {
        fetch: (scope) ->
            defer = $q.defer()
            icswMonitoringBasicTreeService.load(scope.$id).then(
                (data) ->
                    basic_tree = data
                    scope.basic_tree = basic_tree
                    defer.resolve(basic_tree.mon_period_list)
            )
            return defer.promise

        create_or_edit: (scope, $event, create, obj) ->
            if create
                obj = {
                    alias: "new period"
                    mon_range: "00:00-24:00"
                    tue_range: "00:00-24:00"
                    wed_range: "00:00-24:00"
                    thu_range: "00:00-24:00"
                    fri_range: "00:00-24:00"
                    sat_range: "00:00-24:00"
                    sun_range: "00:00-24:00"
                }
            return icswMonitoringBasicService.create_or_edit(
                basic_tree
                scope
                create
                obj
                "mon_period"
                icswMonPeriodBackup
                "icsw.mon.period.form"
                "Monitoring Period"
            )

        delete: (scope, $event, obj) ->
            icswToolsSimpleModalService("Really delete MonitoringPeriod '#{obj.name}' ?").then(
                () =>
                    basic_tree.delete_mon_period(obj).then(
                        () ->
                            console.log "mon_period deleted"
                    )
            )
    }
]).service('icswMonitoringBasicNotificationService',
[
    "ICSW_URLS", "icswMonitoringBasicTreeService", "$q", "Restangular",
    "icswToolsSimpleModalService", "icswMonNotificationBackup", "icswMonitoringBasicService",
(
    ICSW_URLS, icswMonitoringBasicTreeService, $q, Restangular,
    icswToolsSimpleModalService, icswMonNotificationBackup, icswMonitoringBasicService,
) ->
    basic_tree = undefined
    return {
        fetch: (scope) ->
            defer = $q.defer()
            icswMonitoringBasicTreeService.load(scope.$id).then(
                (data) ->
                    basic_tree = data
                    scope.basic_tree = basic_tree
                    defer.resolve(basic_tree.mon_notification_list)
            )
            return defer.promise

        create_or_edit: (scope, $event, create, obj) ->
            if create
                obj = {
                    name: ""
                    channel: "mail"
                    not_type: "service"
                }
            return icswMonitoringBasicService.create_or_edit(
                basic_tree
                scope
                create
                obj
                "mon_notification"
                icswMonNotificationBackup
                "icsw.mon.notification.form"
                "Monitoring Notification"
            )

        delete: (scope, $event, obj) ->
            icswToolsSimpleModalService("Really delete MonitoringNotification '#{obj.name}' ?").then(
                () =>
                    basic_tree.delete_mon_notification(obj).then(
                        () ->
                            console.log "mon_not deleted"
                    )
            )
    }
]).service('icswMonitoringContactService', ["ICSW_URLS", "Restangular", "icswMonitoringBasicRestService", "icswMonitoringUtilService", (ICSW_URLS, Restangular, icswMonitoringRestService, icswMonitoringUtilService) ->
    ret = {
        rest_handle: icswMonitoringRestService.mon_contact
        edit_template: "mon.contact.form"
        delete_confirm_str: (obj) ->
            return "Really delete monitoring contact '#{obj.user}' ?"
        new_object: () ->
            return {
            "user": (entry.idx for entry in icswMonitoringRestService.user)[0]
            "snperiod": (entry.idx for entry in icswMonitoringRestService.mon_period)[0]
            "hnperiod": (entry.idx for entry in icswMonitoringRestService.mon_period)[0]
            "snrecovery": true
            "sncritical": true
            "hnrecovery": true
            "hndown": true
            }
        object_created: (new_obj) -> new_obj.user = null
        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(icswMonitoringRestService,
                [["mon_period", "period"], ["user", "user"]])
    }
    for k, v of icswMonitoringRestService  # shallow copy!
        ret[k] = v
    return ret
]).service('icswMonitoringBasicServiceTemplateService',
[
    "ICSW_URLS", "icswMonitoringBasicTreeService", "$q", "Restangular",
    "icswToolsSimpleModalService", "icswMonServiceTemplBackup", "icswMonitoringBasicService",
(
    ICSW_URLS, icswMonitoringBasicTreeService, $q, Restangular,
    icswToolsSimpleModalService, icswMonServiceTemplBackup, icswMonitoringBasicService,
) ->
    basic_tree = undefined
    return {
        fetch: (scope) ->
            defer = $q.defer()
            icswMonitoringBasicTreeService.load(scope.$id).then(
                (data) ->
                    basic_tree = data
                    scope.basic_tree = basic_tree
                    defer.resolve(basic_tree.mon_service_templ_list)
            )
            return defer.promise

        create_or_edit: (scope, $event, create, obj) ->
            if create
                obj = {
                    nsn_period: basic_tree.mon_period_list[0].idx
                    nsc_period: basic_tree.mon_period_list[0].idx
                    max_attempts: 1
                    ninterval: 2
                    check_interval: 2
                    retry_interval: 2
                    nrecovery: true
                    ncritical: true
                    low_flap_threshold: 20
                    high_flap_threshold: 80
                    freshness_threshold: 60
                }
            return icswMonitoringBasicService.create_or_edit(
                basic_tree
                scope
                create
                obj
                "mon_service_templ"
                icswMonServiceTemplBackup
                "icsw.mon.service.templ.form"
                "Monitoring Service Template"
            )

        delete: (scope, $event, obj) ->
            icswToolsSimpleModalService("Really delete MonitoringServiceTemplate '#{obj.name}' ?").then(
                () =>
                    basic_tree.delete_mon_service_templ(obj).then(
                        () ->
                            console.log "mon_service_templ deleted"
                    )
            )
    }
]).service('icswMonitoringDeviceTemplateService', ["ICSW_URLS", "Restangular", "icswMonitoringBasicRestService", "icswMonitoringUtilService", (ICSW_URLS, Restangular, icswMonitoringRestService, icswMonitoringUtilService) ->
    ret = {
        rest_handle         : icswMonitoringRestService.mon_device_templ
        edit_template       : "mon.device.templ.form"
        delete_confirm_str  : (obj) ->
            return "Really delete device template '#{obj.name}' ?"
        new_object          : () ->
            return {
                "mon_service_templ" : (entry.idx for entry in icswMonitoringRestService.mon_service_templ)[0]
                "host_check_command" : (entry.idx for entry in icswMonitoringRestService.host_check_command)[0]
                "mon_period" : (entry.idx for entry in icswMonitoringRestService.mon_period)[0]
                "not_period" : (entry.idx for entry in icswMonitoringRestService.mon_period)[0]
                "max_attempts" : 1
                "ninterval" : 5
                "check_interval" : 2
                "retry_interval" : 2
                "nrecovery" : true
                "ndown"     : true
                "ncritical" : true
                "low_flap_threshold" : 20
                "high_flap_threshold" : 80
                "freshness_threshold" : 60
            }
        object_created  : (new_obj) -> new_obj.name = null
        get_data_incomplete_error: () ->
            return icswMonitoringUtilService.get_data_incomplete_error(icswMonitoringRestService,
                [["mon_period", "period"], ["mon_service_templ", "service template"], ["host_check_command", "host check command"]])
    }
    for k, v of icswMonitoringRestService  # shallow copy!
        ret[k] = v
    return ret
]).service('icswMonitoringHostCheckCommandService', ["ICSW_URLS", "Restangular", "icswMonitoringBasicRestService", (ICSW_URLS, Restangular, icswMonitoringRestService) ->
    return {
        rest_handle: icswMonitoringRestService.host_check_command
        edit_template: "host.check.command.form"
        delete_confirm_str: (obj) ->
            return "Really delete host check command '#{obj.name}' ?"
        new_object: {"name": ""}
        object_created: (new_obj) -> new_obj.name = null
    }
]).service('icswMonitoringContactgroupService', ["ICSW_URLS", "Restangular", "icswMonitoringBasicRestService", (ICSW_URLS, Restangular, icswMonitoringRestService) ->
    ret = {
        rest_handle: icswMonitoringRestService.mon_contactgroup
        edit_template: "mon.contactgroup.form"
        delete_confirm_str: (obj) ->
            "Really delete Contactgroup '#{obj.name}' ?"
        new_object: {"name": ""}
        object_created: (new_obj) -> new_obj.name = null
    }
    for k, v of icswMonitoringRestService  # shallow copy!
        ret[k] = v
    return ret
])
