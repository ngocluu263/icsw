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

menu_module = angular.module(
    "icsw.layout.menu",
    [
        "ngSanitize", "ui.bootstrap", "icsw.layout.selection", "icsw.user",
    ]
).controller("icswMenuBaseCtrl",
[
    "$scope", "$window", "ICSW_URLS", "icswSimpleAjaxCall", "icswAcessLevelService",
    "initProduct", "icswLayoutSelectionDialogService", "icswActiveSelectionService",
    "$q", "icswUserService", "blockUI", "$state", "icswSystemLicenseDataService", "$rootScope",
    "icswRouteHelper", "ICSW_SIGNALS", "$timeout",
(
    $scope, $window, ICSW_URLS, icswSimpleAjaxCall, icswAcessLevelService,
    initProduct, icswLayoutSelectionDialogService, icswActiveSelectionService,
    $q, icswUserService, blockUI, $state, icswSystemLicenseDataService, $rootScope,
    icswRouterHelper, ICSW_SIGNALS, $timeout,
) ->
    # init service types
    $scope.ICSW_URLS = ICSW_URLS
    $scope.initProduct = initProduct
    $scope.struct = {
        # current user
        current_user: undefined
        # selection string
        selection_string: "N/A"
    }
    $scope.HANDBOOK_PDF_PRESENT = false
    $scope.HANDBOOK_CHUNKS_PRESENT = false
    $scope.HANDBOOK_PAGE = "---"
    icswAcessLevelService.install($scope)
    $q.all(
        [
            icswSimpleAjaxCall(
                {
                    url: ICSW_URLS.MAIN_GET_DOCU_INFO
                    dataType: "json"
                }
            )
            icswUserService.load($scope.$id)
        ]
    ).then(
        (data) ->
            $scope.HANDBOOK_PDF_PRESENT = data[0].HANDBOOK_PDF_PRESENT
            $scope.HANDBOOK_CHUNKS_PRESENT = data[0].HANDBOOK_CHUNKS_PRESENT
    )
    $rootScope.$on(ICSW_SIGNALS("ICSW_OVERVIEW_EMIT_SELECTION"), (event) ->
        _cur_sel = icswActiveSelectionService.current()

        _cur_check_to = undefined
        _install_to = () ->
            if _cur_check_to
                $timeout.cancel(_cur_check_to)
            # check future selection every 2 seconds
            _cur_check_to = $timeout(
                () ->
                    _future_tot = _cur_sel.tot_dev_sel.length
                    _show_string(_current_tot, _future_tot)
                    _install_to()
                2000
            )

        _show_string = (cur, future) ->
            if cur == future
                if cur
                    $scope.struct.selection_string = "#{cur}"
                else
                    $scope.struct.selection_string = "none"
            else
                $scope.struct.selection_string = "#{cur} / #{future}"

        _install_to()
        _current_tot = _cur_sel.tot_dev_sel.length
        _future_tot = _current_tot
        _show_string(_current_tot, _future_tot)
    )

    $scope.get_progress_style = (obj) ->
        return {"width" : "#{obj.value}%"}

    $scope.redirect_to_init = () ->
        window.location = "http://www.initat.org"
        return false

    $scope.device_quickselection = (onoff) ->
        icswLayoutSelectionDialogService.quick_dialog(onoff)

    $scope.handbook_url = "/"
    $scope.handbook_url_valid = false

    $scope.$watch(
        "initProduct",
        (new_val) ->
            if new_val.name?
                $scope.handbook_url_valid = true
                $scope.handbook_url = "/icsw/docu/handbook/#{new_val.name.toLowerCase()}_handbook.pdf"
        true
    )

    # not needed, now handled in menubar-component
    # $scope.$watch(
    #    "size",
    #    (new_val) ->
    #        console.log "size=", new_val
    #        $rootScope.$emit(ICSW_SIGNALS("ICSW_RENDER_MENUBAR"))
    # )

    route_counter = 0
    # load license tree
    icswSystemLicenseDataService.load($scope.$id).then(
        (data) ->
    )

    $scope.$on("$stateChangeStart", (event, to_state, to_params, from_state, from_params) ->
        to_main = if to_state.name.match(/^main/) then true else false
        from_main = if from_state.name.match(/^main/) then true else false
        console.log "$stateChangeStart from '#{from_state.name}' (#{from_main}) to '#{to_state.name}' (#{to_main})"
        if to_main and not from_main
            if to_state.icswData? and not to_state.icswData.$$allowed and $scope.struct.current_user?
                console.error "target state not allowed", to_state.icswData.$$allowed, $scope.struct.current_user
                event.preventDefault()
        else if to_state.name == "login"
            # logout if logged in
            if icswUserService.user_present()
                icswUserService.logout()
            icswUserService.force_logout()
            $scope.struct.current_user = undefined
    )

    $scope.$on("$stateChangeSuccess", (event, to_state, to_params, from_state, from_params) ->
        to_main = if to_state.name.match(/^main/) then true else false
        from_main = if from_state.name.match(/^main/) then true else false
        console.log "$stateChangeSuccess from '#{from_state.name}' (#{from_main}) to '#{to_state.name}' (#{to_main})"
        route_counter++
        if to_state.name == "logout"
            blockUI.start("Logging out...")
            icswUserService.logout().then(
                (json) ->
                    blockUI.stop()
                    $scope.struct.current_user = undefined
            )
        else if not from_main and to_main
            $scope.struct.current_user = icswUserService.get().user
            _helper = icswRouterHelper.get_struct()
            # todo, unify rights checking
            # console.log _helper.valid
            # if $scope.struct.current_user? and $state.current.icswData?
            #    if not $state.current.icswData.$$allowed
            #        _to_state = "main.dashboard"
            #        console.error "target state #{to_state.name} not allowed, going to #{_to_state}"
            #        $state.go(_to_state)
            # console.log to_params, $scope
        else
            # we allow one gentle transfer
            if route_counter >= 2 and not icswSystemLicenseDataService.fx_mode()
                # reduce flicker
                $(document.body).hide()
                $window.location.reload()
    )
    $scope.$on("$stateChangeError", (event, to_state, to_params, from_state, from_params, error) ->
        console.error "error moving to state #{to_state.name} (#{to_state}), error is #{error}"
        _to_login = true
        if to_state.icswData?
            if to_state.icswData.redirect_to_from_on_error
                _to_login = false
        if _to_login
            $state.go("login")
        else
            $state.go(from_state, from_params)
    )
    # $scope.device_selection = () ->
    #    console.log "SHOW_DIALOG"
    #     icswLayoutSelectionDialogService.show_dialog()

    # apply selected theme if theme is set in session
]).directive("icswLayoutMenubar",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.layout.menubar")
    }
]).service("icswMenuProgressService",
[
    "ICSW_SIGNALS", "$rootScope",
(
    ICSW_SIGNALS, $rootScope
) ->
    _settings = {
        # progress bar counter
        rebuilding: 0
    }
    return {
        set_rebuilding: (count) ->
            if count != _settings.rebuilding
                _settings.rebuilding = count
                $rootScope.$emit(ICSW_SIGNALS("ICSW_MENU_PROGRESS_BAR_CHANGED"), _settings)
        get_rebuilding: () ->
            return _settings.rebuilding
    }
]).directive("icswMenuProgressBars",
[
    "$templateCache", "ICSW_URLS", "$timeout", "icswSimpleAjaxCall", "initProduct",
    "icswMenuProgressService", "icswLayoutSelectionDialogService", "ICSW_SIGNALS",
    "$rootScope",
(
    $templateCache, ICSW_URLS, $timeout, icswSimpleAjaxCall, initProduct,
    icswMenuProgressService, icswLayoutSelectionDialogService, ICSW_SIGNALS,
    $rootScope,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.layout.menubar.progress")
        scope: {}
        link: (scope, el, attrs) ->
            scope.initProduct = initProduct
            scope.num_gauges = 0
            scope.progress_iters = 0
            scope.cur_gauges = {}
            $rootScope.$on(ICSW_SIGNALS("ICSW_MENU_PROGRESS_BAR_CHANGED"), (event, settings) ->
                scope.update_progress_bar()
            )
            scope.update_progress_bar = () ->
                icswSimpleAjaxCall(
                    {
                        url: ICSW_URLS.BASE_GET_GAUGE_INFO
                        hidden: true
                    }
                ).then(
                    (xml) =>
                        cur_pb = []
                        $(xml).find("gauge_info gauge_element").each (idx, cur_g) ->
                            cur_g = $(cur_g)
                            idx = cur_g.attr("idx")
                            if idx of scope.cur_gauges
                                scope.cur_gauges[idx].info = cur_g.text()
                                scope.cur_gauges[idx].value = parseInt(cur_g.attr("value"))
                            else
                                scope.cur_gauges[idx] = {info : cur_g.text(), value : parseInt(cur_g.attr("value"))}
                            cur_pb.push(idx)
                        del_pbs = (cur_idx for cur_idx of scope.cur_gauges when cur_idx not in cur_pb)
                        for del_pb in del_pbs
                            delete scope.cur_gauges[del_pb]
                        #for cur_idx, value of $scope.cur_gauges
                        scope.num_gauges = cur_pb.length
                        if cur_pb.length or scope.progress_iters
                            if scope.progress_iters
                                scope.progress_iters--
                            $timeout(scope.update_progress_bar, 1000)
                        if not cur_pb.length
                            icswMenuProgressService.set_rebuilding(0)
                )
    }
]).directive("icswBackgroundJobInfo",
[
    "$templateCache", "ICSW_URLS", "icswSimpleAjaxCall", "$timeout", "$state",
(
    $templateCache, ICSW_URLS, icswSimpleAjaxCall, $timeout, $state
) ->
    return {
        restrict: "EA"
        template: '<button type="button" ng-click="redirect_to_bgj_info()" title="number of background jobs"></button>'
        replace: true
        link: (scope, el, attrs) ->
            scope.background_jobs = 0
            el.hide()
            scope.redirect_to_bgj_info = () ->
                if scope.has_menu_permission('background_job.show_background')
                    $state.go("main.backgroundinfo")
                return false
            el.removeClass()
            el.addClass("btn btn-xs btn-warning")
            get_background_job_class = () ->
                if scope.background_jobs < 4
                    return "btn btn-xs btn-warning"
                else
                    return "btn btn-xs btn-danger"
            reload = () ->
                icswSimpleAjaxCall(
                    {
                        url: ICSW_URLS.MAIN_GET_NUMBER_OF_BACKGROUND_JOBS
                        dataType: "json"
                    }
                ).then(
                    (data) ->
                        scope.background_jobs = data["background_jobs"]
                        if scope.background_jobs
                            el.show()
                            el.removeClass()
                            el.addClass(get_background_job_class())
                            el.text(scope.background_jobs)
                        else
                            el.hide()
                )
                # reload every 30 seconds
                $timeout(reload, 30000)
            reload()
    }
]).factory("icswReactMenuFactory",
[
    "icswAcessLevelService", "ICSW_URLS", "icswSimpleAjaxCall", "blockUI",
    "icswMenuProgressService", "$state", "icswRouteHelper",
(
    icswAcessLevelService, ICSW_URLS, icswSimpleAjaxCall, blockUI,
    icswMenuProgressService, $state, icswRouteHelper,
) ->
    # console.log icswAcessLevelService
    {input, ul, li, a, span, h4, div} = React.DOM
    react_dom = ReactDOM
    menu_line = React.createClass(
        displayName: "menuline"
        render: () ->
            state = @props.state
            data = state.icswData
            # console.log "D=", data
            if data.menuEntry.href?
                a_attrs = {href: data.menuEntry.href, key: "a"}
            else
                a_attrs = {href: data.menuEntry.sref, key: "a"}
            if data.menuEntry.labelClass
                return li(
                    {key: "li"}
                    [
                        a(
                            a_attrs
                            [
                                span(
                                    {className: "label #{data.menuEntry.labelClass}", key: "spanl"}
                                    [
                                        span(
                                            {className: "fa #{data.menuEntry.icon} fa_icsw", key: "span"}
                                        )
                                    ]
                                )
                                " #{data.menuEntry.name}"
                            ]
                        )
                    ]
                )
            else
                return li(
                    {key: "li"}
                    [
                        a(
                            a_attrs
                            [
                                span(
                                    {className: "fa #{data.menuEntry.icon} fa_icsw", key: "span"}
                                )
                                " #{data.menuEntry.name}"
                            ]
                        )
                    ]
                )
    )
    menu_header = React.createClass(
        displayName: "menuheader"
        getDefaultProps: () ->
        render: () ->
            _idx = 0
            _items = []
            # _idx = 0
            # flag for last entry was a valid one
            valid_entry = false
            _post_spacer = false
            for state in @props.entries
                _idx++
                data = state.icswData
                _key = data.key
                if data.$$allowed
                    # console.log _key
                    if (data.menuEntry.preSpacer? and valid_entry) or _post_spacer
                        _items.push(
                            li({className: "divider", key: _key + "_pre"})
                        )
                    if angular.isFunction(state.name)
                        _items.push(
                            React.createElement(state.name, {key: _key})
                        )
                    else
                        _items.push(
                            React.createElement(menu_line, {key: _key, state: state})
                        )
                    valid_entry = true
                    if data.menuEntry.postSpacer?
                        _post_spacer = true
                    else
                        _post_spacer = false
            if _items.length
                state = @props.state
                header = state.icswData.menuHeader
                key= "mh_#{state.icswData.key}"
                _res = li(
                    {
                        key: "menu_" + key
                    }
                    [
                        a(
                            {
                                className: "dropdown-toggle"
                                # dataToggle is not working
                                "data-toggle": "dropdown"
                                key: "menu.head_" + key
                            }
                            [
                                span(
                                    {
                                        className: "fa #{header.icon} fa-lg fa_top"
                                        key: "span_" + key
                                    }
                                )
                                span(
                                    {
                                        key: "text_" + key
                                    }
                                    header.name
                                )
                            ]
                        )
                        ul(
                            {
                                className: "dropdown-menu"
                                key: "ul_" + key
                            }
                            _items
                        )
                    ]
                )
            else
                _res = null
            return _res
    )
    
    class MenuHeader
        constructor: (@state) ->
            @entries = []

        add_entry: (entry) =>
            @entries.push(entry)

        get_react: () =>
            # order entries
            return React.createElement(
                menu_header
                {
                    key: @state.icswData.key + "_top"
                    state: @state
                    entries: _.orderBy(@entries, "icswData.menuEntry.ordering")
                }
            )
    
    menu_comp = React.createClass(
        displayName: "menubar"

        update_dimensions: () ->
            @setState(
                {
                    width: $(window).width()
                    height: $(window).height()
                }
            )
        getInitialState: () ->
            return {
                counter: 0
            }

        force_redraw: () ->
            @setState({counter: @state.counter + 1})

        componentWillMount: () ->
            # register eventhandler
            $(window).on("resize", @update_dimensions)
    
        componentWillUnmount: () ->
            # remove eventhandler
            $(window).off("resize", @update_dimensions)
    
        render: () ->
            _menu_struct = icswRouteHelper.get_struct()
            # may not be valid
            # console.log "mv", _menu_struct.valid
            if _menu_struct.valid
                menus = (new MenuHeader(state) for state in _menu_struct.menu_header_states)
                # console.log menus.length
                for state in _menu_struct.menu_states
                    # find menu
                    menu = (entry for entry in menus when entry.state.icswData.menuHeader.key == state.icswData.menuEntry.menukey)
                    if menu.length
                        menu[0].add_entry(state)
                    else
                        console.error("No menu with name #{state.icswData.menuEntry.menukey} found (#{state.icswData.pageTitle})")
                        console.log "Menus known:", (entry.state.icswData.menuHeader.key for entry in menus).join(", ")

            else
                menus = []

            if menus.length
                _res = ul(
                    {
                        key: "topmenu"
                        className: "nav navbar-nav"
                    }
                    (
                        menu.get_react() for menu in _.orderBy(menus, "state.icswData.menuHeader.ordering")
                    )
                )
            else
                _res = null
            return _res
    )
    return menu_comp
]).directive("icswMenuDirective",
[
    "icswReactMenuFactory", "icswAcessLevelService", "icswMenuProgressService",
    "$rootScope", "ICSW_SIGNALS",
(
    icswReactMenuFactory, icswAcessLevelService, icswMenuProgressService,
    $rootScope, ICSW_SIGNALS
) ->
    return {
        restrict: "EA"
        replace: true
        scope: true
        link: (scope, el, attrs) ->
            _element = ReactDOM.render(
                React.createElement(
                    icswReactMenuFactory
                )
                el[0]
            )
            $rootScope.$on(ICSW_SIGNALS("ICSW_ROUTE_RIGHTS_CHANGED"), (event) ->
                _element.force_redraw()
            )
            $rootScope.$on(ICSW_SIGNALS("ICSW_MENU_PROGRESS_BAR_CHANGED"), (event, settings) ->
                console.log "mps", settings
                # _render()
            )

    }
]).controller("icswMenuSubCtrl",
[
    "$scope", "icswLayoutSelectionDialogService", "icswActiveSelectionService",
    "icswUserService", "$state",
(
    $scope, icswLayoutSelectionDialogService, icswActiveSelectionService,
    icswUserService, $state
) ->
    $scope.device_quickselection = (onoff) ->
        icswLayoutSelectionDialogService.quick_dialog(onoff)
    $scope.show_submenu = false
    $scope.sel_devices = 3
    $scope.breadcrumb = "Devices > Device configuration"

])
