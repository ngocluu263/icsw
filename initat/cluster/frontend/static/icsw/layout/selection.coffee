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

# selection module, handles session-persistent selections for non-FX enabled frontends

angular.module(
    "icsw.layout.selection",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap",
        "init.csw.filters", "restangular", "noVNC", "ui.select", "icsw.tools",
        "icsw.device.info", "icsw.tools.reacttree", "icsw.user",
        "icsw.backend.devicetree",
    ]
).service("icswActiveSelectionService",
[
    "$q", "Restangular", "$rootScope", "ICSW_URLS", "icswSelection",  "ICSW_SIGNALS",
(
    $q, Restangular, $rootScope, ICSW_URLS, icswSelection, ICSW_SIGNALS
) ->
    # used by menu.coffee (menu_base)
    _receivers = 0
    cur_selection = new icswSelection([], [], [], [])
    # for testing, uses gulp-preprocess
    # @if DEBUG
    cur_selection = new icswSelection([], [], [666, 3, 5, 16, 21], [3, 5, 16, 21, 666])
    # @endif
    # cur_selection = new icswSelection([], [], [3, 5], [3, 5])
    # cur_selection = new icswSelection([], [], [3], [3])
    # windowstest
    # cur_selection = new icswSelection([], [], [13], [13])
    # cur_selection = new icswSelection([], [], [16], [16]) # only firewall
    # cur_selection = new icswSelection([], [], [], [])

    $rootScope.$on(ICSW_SIGNALS("ICSW_DEVICE_TREE_LOADED"), (event) ->
        # tree loaded, re-emit selection
        send_selection()
    )

    register_receiver = () ->
        _receivers += 1
        # console.log "registered receiver"
        $rootScope.$emit(ICSW_SIGNALS("ICSW_DSR_REGISTERED"))

    unregister_receiver = () ->
        _receivers -= 1
        # console.log "registered receiver"
        $rootScope.$emit(ICSW_SIGNALS("ICSW_DSR_UNREGISTERED"))

    sync_selection = (new_sel) ->
        cur_selection.update(new_sel.categories, new_sel.device_groups, new_sel.devices, [])
        cur_selection.sync_with_db(new_sel)

    unsync_selection = () ->
        cur_selection.sync_with_db(undefined)

    send_selection = () ->
        # console.log "emit current device selection"
        $rootScope.$emit(ICSW_SIGNALS("ICSW_OVERVIEW_EMIT_SELECTION"))

    return {
        num_receivers: () ->
            return _receivers

        current: () ->
            return cur_selection

        get_selection: () ->
            return cur_selection

        sync_selection: (new_sel) ->
            # synchronizes cur_selection with new_sel
            sync_selection(new_sel)

        unsync_selection: () ->
            # remove synchronization with saved (==DB-selection)
            unsync_selection()

        send_selection: () ->
            send_selection()

        register_receiver: () ->
            # register devsel receiver
            register_receiver()

        unregister_receiver: () ->
            # unregister devsel receiver
            unregister_receiver()
    }
]).service("icswSelection",
[
    "icswDeviceTreeService", "$q", "icswSimpleAjaxCall", "ICSW_URLS", "$rootScope",
    "Restangular", "icswSavedSelectionService", "ICSW_SIGNALS",
(
    icswDeviceTreeService, $q, icswSimpleAjaxCall, ICSW_URLS, $rootScope,
    Restangular, icswSavedSelectionService, ICSW_SIGNALS
) ->

    class icswSelection
        # only instantiated once (for now), also handles saved selections
        constructor: (@cat_sel, @devg_sel, @dev_sel, @tot_dev_sel) ->
            $rootScope.$on(ICSW_SIGNALS("ICSW_DEVICE_TREE_LOADED"), (event, tree) =>
                @tree = tree
                # console.log "tree set for icswSelection", @tree
            )
            @tree = undefined
            @sync_with_db(undefined)
            @user = undefined
            @sel_var_name = "$$saved_selection__$$SESSIONID$$"
            @__user_var_used = false
            $rootScope.$on(ICSW_SIGNALS("ICSW_USER_CHANGED"), ($event, user) =>
                @user = user
                if @user?
                    @sel_var_name = @user.expand_var(@sel_var_name)
                    if user.has_var(@sel_var_name)
                        if not @__user_var_used
                            @__user_var_used = true
                            @_last_stored = user.get_var(@sel_var_name).json_value
                            _stored = angular.fromJson(@_last_stored)
                            @dev_sel = _stored.dev_sel
                            @tot_dev_sel = _stored.tot_dev_sel
                            @sync_with_db(undefined)
                    else
                        @_last_stored = ""
            )

        update: (@cat_sel, @devg_sel, @dev_sel, @tot_dev_sel) ->
            @selection_changed()

        selection_changed: () =>
            if @user
                _new_store = angular.toJson(
                    {
                        dev_sel: @dev_sel
                        tot_dev_sel: @tot_dev_sel
                    }
                )
                if _new_store != @_last_stored
                    @_last_stored = _new_store
                    @user.set_json_var(
                        @sel_var_name
                        @_last_stored
                    )


        sync_with_db: (@db_obj=undefined) =>
            if @db_obj
                @db_idx = @db_obj.idx
                @cat_sel_db = angular.copy(@cat_sel)
                @devg_sel_db = angular.copy(@devg_sel)
                @dev_sel_db = angular.copy(@dev_sel)
                # selection has changed
                @changed = false
                @compare_with_db()
            else
                # unsync
                @db_idx = 0
                delete @cat_sel_db
                delete @devg_sel_db
                delete @dev_sel_db
                @db_obj = {
                    "info": ""
                    "name": "New selection"
                }
                # is disabled on the drop-down selection list
                # selection has changed, dummy flag, should never be used
                @changed = true

        compare_with_db: () =>
            @changed = false
            # compare current selection with _db instances
            for _entry in ["cat_sel", "devg_sel", "dev_sel"]
                _db_entry = "#{_entry}_db"
                if _.sum(@[_entry]) != _.sum(@[_db_entry]) or @[_entry].length != @[_db_entry].length
                    @changed = true
            @create_info()

        create_info: () =>
            icswSavedSelectionService.enrich_selection(@db_obj)
            if @changed
                @db_obj.info = "(*) #{@db_obj.info}"

        toggle_selection: (obj) =>
            # toggle selection of object
            _selected = obj.idx in @dev_sel
            if _selected
                @remove_selection(obj)
            else
                @add_selection(obj)

        add_selection: (obj) =>
            # add selection
            if obj.idx not in @dev_sel
                @dev_sel.push(obj.idx)
                @tot_dev_sel.push(obj.idx)
                @selection_changed()

        remove_selection: (obj) =>
            # remove selection
            if obj.idx in @dev_sel
                _.pull(@dev_sel, obj.idx)
                _.pull(@tot_dev_sel, obj.idx)
                @selection_changed()

        device_is_selected: (obj) =>
            # only works for devices
            return obj.idx in @dev_sel

        deselect_all_devices: (obj) =>
            @dev_sel = []
            @tot_dev_sel = []
            @selection_changed()

        selection_saved: () =>
            # database object saved
            # console.log "resync", @db_obj
            @sync_with_db(@db_obj)

        is_synced: () =>
            return if @db_idx then true else false

        any_selected: () ->
            return if @cat_sel.length + @devg_sel.length + @dev_sel.length + @tot_dev_sel.length then true else false

        any_lazy_selected: () ->
            return if @cat_sel.length + @devg_sel.length then true else false

        resolve_lazy_selection: () ->
            # categories
            for _cat in @cat_sel
                for _cs in @tree.cat_tree.lut[_cat].reference_dict.device
                    @tot_dev_sel.push(_cs)
            @cat_sel = []
            # groups
            for _group in @devg_sel
                for _gs in @tree.group_lut[_group].devices
                    @dev_sel.push(_gs)
                    @tot_dev_sel.push(_gs)
            @devg_sel = []
            @tot_dev_sel = _.uniq(@tot_dev_sel)
            @dev_sel = _.uniq(@dev_sel)
            @selection_changed()

        resolve_dev_name: (dev_idx) =>
            _dev = @tree.all_lut[dev_idx]
            if _dev.is_meta_device
                return "[M] " + _dev.full_name.substring(8)
            else
                return _dev.full_name

        resolve_devices: () =>
            if @dev_sel.length
                _list = ((@resolve_dev_name(_ds) for _ds in @dev_sel))
                _list.sort()
                return _list.join(", ")
            else
                return "---"

        resolve_total_devices: () =>
            if @tot_dev_sel.length
                _list = ((@resolve_dev_name(_ds) for _ds in @tot_dev_sel))
                _list.sort()
                return _list.join(", ")
            else
                return "---"

        resolve_device_groups: () =>
            if @devg_sel.length
                _list = (@tree.group_lut[_dg].name.substring(8) for _dg in @devg_sel)
                _list.sort()
                return _list.join(", ")
            else
                return "---"

        resolve_categories: () ->
            if @cat_sel.length
                _list = ((@tree.cat_tree.lut[_cs].full_name for _cs in @cat_sel))
                _list.sort()
                return _list.join(", ")
            else
                return "---"

        get_devsel_list: () =>
            # all device pks
            dev_pk_list = @tot_dev_sel
            # all non-meta device pks
            dev_pk_nmd_list = []
            # all device_group pks
            devg_pk_list = []
            # all meta device pks
            dev_pk_md_list = []
            for _pk in @tot_dev_sel
                _dev = @tree.all_lut[_pk]
                if _dev
                    if _dev.is_meta_device
                        devg_pk_list.push(_dev.device_group)
                        dev_pk_md_list.push(_pk)
                    else
                        dev_pk_nmd_list.push(_pk)
                else
                    console.log "device with pk #{_pk} is not resolvable"
            return [dev_pk_list, dev_pk_nmd_list, devg_pk_list, dev_pk_md_list]

        category_selected: (cat_idx) ->
            return cat_idx in @cat_sel

        device_group_selected: (devg_idx) ->
            return devg_idx in @devg_sel

        device_selected: (dev_idx) ->
            if dev_idx in @dev_sel or dev_idx in @tot_dev_sel
                return true
            else
                return false

        save_db_obj: () =>
            if @db_obj
                # console.log @db_obj
                # console.log @dev_sel
                @db_obj.categories = (entry for entry in @cat_sel)
                @db_obj.device_groups = (entry for entry in @devg_sel)
                @db_obj.devices = (entry for entry in @dev_sel)
                # console.log @db_obj
                @db_obj.put().then(
                    (old_obj) =>
                        @selection_saved()
                )
        create_saved_selection: (user) =>
            defer = $q.defer()
            _sel = {
                "name": @db_obj.name
                "user": user.user.idx
                "devices": @dev_sel
                "categories": @cat_sel
                "device_groups": @devg_sel
            }
            # console.log "save", _sel
            Restangular.all(ICSW_URLS.REST_DEVICE_SELECTION_LIST.slice(1)).post(_sel).then(
                (data) =>
                    # enrich_selection(data)
                    @sync_with_db(data)
                    defer.resolve(data)
            )
            return defer.promise

        delete_saved_selection: () =>
            defer = $q.defer()
            @db_obj.remove().then(
                () =>
                    @sync_with_db(undefined)
                    defer.resolve(true)
            )
            return defer.promise

        select_parent: () ->
            defer = $q.defer()
            icswSimpleAjaxCall(
                url: ICSW_URLS.DEVICE_SELECT_PARENTS
                data: {
                    angular_sel: angular.toJson(@tot_dev_sel)
                }
                dataType: "json"
            ).then(
                (data) =>
                    @tot_dev_sel = data["new_selection"]
                    defer.resolve(data)
            )
            return defer.promise

]).service("icswSavedSelectionService",
[
    "Restangular", "$q", "ICSW_URLS", "icswUserService",
(
    Restangular, $q, ICSW_URLS, icswUserService
) ->
    enrich_selection = (entry) ->
        _created = moment(entry.date)
        info = [entry.name]
        if entry.devices.length
            info.push("#{entry.devices.length} devs")
        if entry.device_groups.length
            info.push("#{entry.device_groups.length} groups")
        if entry.categories.length
            info.push("#{entry.categories.length} cats")
        info = info.join(", ")
        info = "#{info} (#{_created.format('YYYY-MM-DD HH:mm')})"
        entry.info = info

    _list = []

    load_selections = () ->
        defer = $q.defer()
        icswUserService.load().then(
            (user) ->
                Restangular.all(ICSW_URLS.REST_DEVICE_SELECTION_LIST.slice(1)).getList(
                    {
                        user: user.user.idx
                    }
                ).then(
                    (data) ->
                        (enrich_selection(entry) for entry in data)
                        _list = data
                        defer.resolve(_list)
                )
        )
        return defer.promise

    save_selection = (user, sel) ->
        defer = $q.defer()
        sel.create_saved_selection(user).then(
            (data) ->
                enrich_selection(data)
                _list.push(data)
                defer.resolve(data)
        )
        return defer.promise

    delete_selection = (sel) ->
        defer = $q.defer()
        del_id = sel.db_idx
        sel.delete_saved_selection().then(
            (done) ->
                console.log del_id, (entry.idx for entry in _list)
                _.remove(_list, (entry) -> return entry.idx == del_id)
                defer.resolve(_list)
        )
        return defer.promise

    return {
        "load_selections": () ->
            return load_selections()
        "save_selection": (user, sel) ->
            return save_selection(user, sel)
        "delete_selection": (sel) ->
            return delete_selection(sel)
        "enrich_selection": (obj) ->
            enrich_selection(obj)
    }
]).controller("icswLayoutSelectionController",
[
    "$scope", "icswLayoutSelectionTreeService", "$timeout", "icswDeviceTreeService", "ICSW_SIGNALS",
    "icswSelection", "icswActiveSelectionService", "$q", "icswSavedSelectionService", "icswToolsSimpleModalService",
    "DeviceOverviewService", "ICSW_URLS", 'icswSimpleAjaxCall', "blockUI", "$rootScope", "icswUserService",
    "DeviceOverviewSelection", "hotkeys", "icswComplexModalService", "$templateCache", "$compile",
(
    $scope, icswLayoutSelectionTreeService, $timeout, icswDeviceTreeService, ICSW_SIGNALS,
    icswSelection, icswActiveSelectionService, $q, icswSavedSelectionService, icswToolsSimpleModalService,
    DeviceOverviewService, ICSW_URLS, icswSimpleAjaxCall, blockUI, $rootScope, icswUserService,
    DeviceOverviewSelection, hotkeys, icswComplexModalService, $templateCache, $compile,
) ->
    hotkeys.bindTo($scope).add(
        combo: "ctrl+d"
        description: "Active device tab"
        allowIn: ["INPUT"]
        callback: (event) ->
            $scope.activate_tab("d")
            event.preventDefault()
    ).add(
        combo: "ctrl+g"
        description: "Active group tab"
        allowIn: ["INPUT"]
        callback: (event) ->
            $scope.activate_tab("g")
            event.preventDefault()
    ).add(
        combo: "ctrl+c"
        description: "Active category tab"
        allowIn: ["INPUT"]
        callback: (event) ->
            $scope.activate_tab("c")
            event.preventDefault()
    )
    $scope.show_selection = false
    $scope.saved_selections = []
    $scope.devsel_receivers = icswActiveSelectionService.num_receivers()
    $scope.struct = {
        # device tree
        device_tree: undefined
        # search settings
        search_ok: true
        # is loading
        is_loading: true
        # in sync with a saved selection
        synced: false
        # user
        user: undefined
        # selection
        selection: undefined
        # selection valid
        selection_valid: false
        # class filter name
        class_filter_name: "N/A"
        # selection dict
        selection_dict: {
            d: 0
            g: 0
            c: 0
        }
        # active tab
        active_tab: "d"
        # active tab index
        active_tab_idx: 0
        # for saved selections
        search_str: ""
        selection_for_dropdown: undefined
    }
    # console.log "new ctrl", $scope.$id
    # notifier queue
    notifier_queue = $q.defer()
    notifier_queue.promise.then(
        (ok) ->
        (error) ->
        (info) ->
            # console.log "info"
    )
    # treeconfig for devices
    $scope.tc_devices = new icswLayoutSelectionTreeService(
        $scope
        notifier_queue
        {
            show_tree_expand_buttons: false
            show_descendants: true
        }
    )
    # treeconfig for groups
    $scope.tc_groups = new icswLayoutSelectionTreeService(
        $scope
        notifier_queue
        {
            show_tree_expand_buttons: false
            show_descendants: true
        }
    )
    # treeconfig for categories
    $scope.tc_categories = new icswLayoutSelectionTreeService(
        $scope
        notifier_queue
        {
            show_selection_buttons: true
            show_descendants: true
        }
    )
    # console.log "start"
    # list of receivers
    stop_listen = []
    stop_listen.push(
        $rootScope.$on(ICSW_SIGNALS("ICSW_DSR_REGISTERED"), (event) ->
            $scope.devsel_receivers = icswActiveSelectionService.num_receivers()
            console.log "****+", $scope.devsel_receivers, $scope
        )
    )
    stop_listen.push(
        $rootScope.$on(ICSW_SIGNALS("ICSW_DSR_UNREGISTERED"), (event) ->
            $scope.devsel_receivers = icswActiveSelectionService.num_receivers()
            console.log "****-", $scope.devsel_receivers, $scope
        )
    )
    stop_listen.push(
        $rootScope.$on(ICSW_SIGNALS("ICSW_USER_CHANGED"), (event, new_user) ->
            # console.log "new user", new_user
            if new_user and new_user.idx
                _install_tree(user)
        )
    )
    stop_listen.push(
        $rootScope.$on(ICSW_SIGNALS("ICSW_SELECTOR_SHOW"), (event, cur_state) ->
            # call when the requester is shown
            if icswUserService.user_present()
                #console.log "show_devsel", event, cur_state, $scope, user
                _install_tree(icswUserService.get())
            else
                console.error "No user"
        )
    )
    stop_listen.push(
        $scope.$on("$destroy", (event) ->
            # console.log "Destroy", stop_listen
            notifier_queue.reject("exit")
            (stop_func() for stop_func in stop_listen)
        )
    )

    _set_class_filter_name = () ->
        $scope.struct.class_filter_name = $scope.struct.device_tree.device_class_tree.get_filter_name()

    _install_tree = (user_obj) ->
        icswDeviceTreeService.load($scope.$id).then(
            (new_tree) ->
                $scope.struct.user = user_obj
                user_obj.read_device_class_filter(new_tree.device_class_tree)
                _got_rest_data(new_tree, icswActiveSelectionService.get_selection())
        )

    # get current devsel_receivers
    _got_rest_data = (tree, selection) ->
        $scope.struct.device_tree = tree
        $scope.struct.selection = selection
        $scope.struct.selection_valid = true
        _set_class_filter_name()
        _build_tree()

    _build_tree = () ->
        $scope.tc_devices.clear_root_nodes()
        $scope.tc_groups.clear_root_nodes()
        $scope.tc_categories.clear_root_nodes()
        console.log "got_rest_data (selection)"
        # build category tree
        # tree category lut
        # id -> category entry from tree (with devices)
        t_cat_lut = {}
        # device tree
        _tree = $scope.struct.device_tree
        # flag if we should call devsel after search
        $scope.call_devsel_after_search = false
        for entry in _tree.cat_tree.list
            t_entry = $scope.tc_categories.create_node(
                {
                    folder: true
                    obj: entry.idx
                    show_select: entry.depth > 1
                    _node_type: "c"
                    expand: entry.depth == 0
                    selected: $scope.struct.selection.category_selected(entry.idx)
                }
            )
            t_cat_lut[entry.idx] = t_entry
            if entry.parent
                t_cat_lut[entry.parent].add_child(t_entry)
            else
                $scope.tc_categories.add_root_node(t_entry)
        # build device group tree and top level of device tree
        dg_lut = {}
        for entry in _tree.enabled_list
            if entry.is_meta_device
                _group = _tree.get_group(entry)
                if _.some(_tree.device_class_is_enabled(_tree.all_lut[idx]) for idx in _group.devices)
                    g_entry = $scope.tc_groups.create_node(
                        {
                            obj: entry.device_group
                            folder: true
                            _node_type: "g"
                            selected: $scope.struct.selection.device_group_selected(entry.device_group)
                        }
                    )
                    $scope.tc_groups.add_root_node(g_entry)
                    d_entry = $scope.tc_devices.create_node(
                        {
                            obj: entry.idx
                            folder: true
                            selected: $scope.struct.selection.device_selected(entry.idx)
                            _node_type: "d"
                        }
                    )
                    $scope.tc_devices.add_root_node(d_entry)
                    dg_lut[entry.device_group] = d_entry
        # build devices tree
        for entry in _tree.enabled_list
            if !entry.is_meta_device
                if _tree.device_class_is_enabled(entry)
                    # copy selection state to device selection (the selection state of the meta devices is keeped in sync with the selection states of the devicegroups )
                    d_entry = $scope.tc_devices.create_node(
                        {
                            obj: entry.idx
                            folder: false
                            selected: $scope.struct.selection.device_selected(entry.idx)
                            _node_type: "d"
                        }
                    )
                    dg_lut[entry.device_group].add_child(d_entry)
        for cur_tc in [$scope.tc_devices, $scope.tc_groups, $scope.tc_categories]
            cur_tc.recalc()
            cur_tc.show_selected()
        $scope.struct.is_loading = false
        $scope.selection_changed()

    $scope.toggle_show_selection = () ->
        $scope.show_selection = !$scope.show_selection

    $scope.activate_tab = (t_type) ->
        $scope.struct.active_tab = t_type
        $scope.struct.active_tab_idx = ["d", "g", "c"].indexOf($scope.struct.active_tab)

    $scope.activate_tab($scope.struct.active_tab)

    $scope.get_tc = (short) ->
        return {
            d: $scope.tc_devices
            g: $scope.tc_groups
            c: $scope.tc_categories
        }[short]

    $scope.clear_selection = (tab_name) ->
        _tree = $scope.get_tc(tab_name)
        _tree.clear_selected()
        $scope.struct.search_ok = true
        $scope.selection_changed()

    $scope.clear_search = () ->
        if $scope.cur_search_to
            $timeout.cancel($scope.cur_search_to)
        $scope.struct.search_str = ""
        $scope.struct.search_ok = true

    $scope.update_search = () ->
        if $scope.cur_search_to
            $timeout.cancel($scope.cur_search_to)
        $scope.cur_search_to = $timeout($scope.set_search_filter, 500)

    $scope.set_search_filter = () ->
        $scope.cur_search_to = undefined
        if $scope.struct.search_str == ""
            return

        looks_like_ip_or_mac_start = (in_str) ->
            # accept "192.168." or "AB:AB:AB:
            return /^\d{1,3}\.\d{1,3}\./.test(in_str) || /^([0-9A-Fa-f]{2}[:-]){3}/.test(in_str)

        check_for_post_devsel_call = () ->
            if $scope.call_devsel_after_search
                $scope.call_devsel_after_search = false
                $scope.call_devsel_func()

        if looks_like_ip_or_mac_start($scope.struct.search_str)
            icswSimpleAjaxCall(
                url: ICSW_URLS.DEVICE_GET_MATCHING_DEVICES
                dataType: "json"
                data:
                    search_str: $scope.struct.search_str
            ).then(
                (matching_device_pks) ->
                    cur_tree = $scope.get_tc($scope.struct.active_tab)
                    cur_tree.toggle_tree_state(undefined, -1, false)
                    num_found = 0
                    cur_tree.iter(
                        (entry) ->
                            if entry._node_type == "d"
                                _sel = $scope.struct.device_tree.all_lut[entry.obj].idx in matching_device_pks
                                entry.set_selected(_sel)
                                if _sel
                                    num_found++
                    )
                    $scope.struct.search_ok = num_found > 0
                    cur_tree.show_selected(false)
                    $scope.selection_changed()
                    check_for_post_devsel_call()
            )

        else  # regular search
            _with_slash = false
            try
                cur_re = new RegExp($scope.struct.search_str, "gi")
                if $scope.struct.search_str.match(/\//)
                    _with_slash = true
            catch exc
                cur_re = new RegExp("^$", "gi")
            cur_tree = $scope.get_tc($scope.struct.active_tab)
            cur_tree.toggle_tree_state(undefined, -1, false)
            num_found = 0
            cur_tree.iter(
                (entry, cur_re) ->
                    if entry._node_type == "d"
                        _sel = if $scope.struct.device_tree.all_lut[entry.obj].full_name.match(cur_re) then true else false
                        entry.set_selected(_sel)
                        if _sel
                            num_found++
                    else if entry._node_type == "g"
                        _sel = if $scope.struct.device_tree.group_lut[entry.obj].full_name.match(cur_re) then true else false
                        entry.set_selected(_sel)
                        if _sel
                            num_found++
                    else if entry._node_type == "c"
                        if _with_slash
                            _sel = if $scope.struct.device_tree.cat_tree.lut[entry.obj].full_name.match(cur_re) then true else false
                        else
                            _sel = if $scope.struct.device_tree.cat_tree.lut[entry.obj].name.match(cur_re) then true else false
                        entry.set_selected(_sel)
                        if _sel
                            num_found++
                cur_re
            )
            $scope.struct.search_ok = if num_found > 0 then true else false
            cur_tree.show_selected(false)
            $scope.selection_changed()
            check_for_post_devsel_call()

    $scope.resolve_devices = (sel) ->
        return sel.resolve_devices()

    $scope.resolve_total_devices = (sel) ->
        return sel.resolve_total_devices()

    $scope.resolve_device_groups = (sel) ->
        return sel.resolve_device_groups()

    $scope.resolve_categories = (sel) ->
        return sel.resolve_categories()

    $scope.resolve_lazy_selection = () ->
        $scope.struct.selection.resolve_lazy_selection()
        $scope.tc_groups.clear_selected()
        $scope.tc_categories.clear_selected()
        # select devices
        $scope.tc_devices.iter(
            (node, data) ->
                node.selected = node.obj in $scope.struct.selection.tot_dev_sel
        )
        $scope.tc_devices.recalc()
        $scope.tc_groups.show_selected(false)
        $scope.tc_categories.show_selected(false)
        $scope.tc_devices.show_selected(false)
        $scope.selection_changed()
        $scope.activate_tab("d")

    $scope.show_class_filter = ($event) ->
        sub_scope = $scope.$new(true)
        sub_scope.device_class_tree = $scope.struct.device_tree.device_class_tree
        cur_selection = $scope.struct.user.get_device_class_filter()
        cur_fp = $scope.struct.device_tree.device_class_tree.get_fingerprint()
        sub_scope.selection_changed = () ->
            # need a timeout here because angular syncs the flags during the next digest-cycle
            $timeout(
                () ->
                    $scope.struct.user.write_device_class_filter(sub_scope.device_class_tree)
                0
            )

        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.layout.class.filter"))(sub_scope)
                title: "Select DeviceClasses"
                closeable: true
                ok_label: "select"
                ok_callback: (modal) ->
                    d = $q.defer()
                    d.resolve("resolved")
                    return d.promise
                cancel_callback: (modal) ->
                    $scope.struct.user.restore_device_class_filter(cur_selection, sub_scope.device_class_tree)
                    d = $q.defer()
                    d.resolve("resolved")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
                new_fp = $scope.struct.device_tree.device_class_tree.get_fingerprint()
                _set_class_filter_name()
                if cur_fp != new_fp
                    # fingerprint changed
                    _build_tree()
                # trigger refiltering of list
                # $rootScope.$emit(ICSW_SIGNALS("ICSW_FORCE_TREE_FILTER"))
        )

    $scope.selection_changed = () ->
        dev_sel_nodes = $scope.tc_devices.get_selected(
            (entry) ->
                if entry._node_type == "d" and entry.selected
                    return [entry.obj]
                else
                    return []
        )
        group_sel_nodes = $scope.tc_groups.get_selected(
            (entry) ->
                if entry._node_type == "g" and entry.selected
                    return [entry.obj]
                else
                    return []
        )
        cat_sel_nodes = $scope.tc_categories.get_selected(
            (entry) ->
                if entry._node_type == "c" and entry.selected
                    return [entry.obj]
                else
                    return []
        )
        $scope.struct.selection_dict = {
            "d": dev_sel_nodes.length
            "g": group_sel_nodes.length
            "c": cat_sel_nodes.length
        }
        # direct selected devices
        dev_sel = []
        # total devices select
        tot_dev_sel = []
        # selected devicegroups (==lazy)
        devg_sel = []
        for _ds in dev_sel_nodes
            dev_sel.push(_ds)
            tot_dev_sel.push(_ds)
        for _gs in group_sel_nodes
            devg_sel.push(_gs)
            for _group_dev in $scope.struct.device_tree.group_lut[_gs].devices
                tot_dev_sel.push(_group_dev)
        for _cs in cat_sel_nodes
            for _cat_dev in $scope.struct.device_tree.get_category(_cs).reference_dict.device
                tot_dev_sel.push(_cat_dev)
        $scope.struct.selection.update(cat_sel_nodes, devg_sel, dev_sel, _.uniq(tot_dev_sel))
        if $scope.struct.selection.is_synced()
            # current selection is in sync with a saved one
            $scope.struct.synced = true
            # console.log "sync"
            $scope.struct.selection.compare_with_db()
        else
            # console.log "unsync"
            $scope.struct.synced = false

    $scope.call_devsel_func = () ->
        if $scope.cur_search_to?
            # set flag: call devsel after search is done
            $scope.call_devsel_after_search = true
        else
            icswActiveSelectionService.send_selection($scope.struct.selection)
            $scope.modal.close()

    $scope.enable_saved_selections = () ->
        if not $scope.saved_selections.length
            icswSavedSelectionService.load_selections().then(
                (data) ->
                    $scope.saved_selections = data
            )

    $scope.update_selection = () ->
        $scope.struct.selection.save_db_obj()

    $scope.create_selection = () ->
        _names = (sel.name for sel in $scope.saved_selections)
        # make name unique
        if $scope.struct.selection.name in _names
            if $scope.struct.selection.name.match(/.* \d+$/)
                _parts = $scope.struct.selection.name.split(" ")
                _idx = parseInt(_parts.pop())
                $scope.struct.selection.name = _parts.join(" ")
            else
                _idx = 1
            while true
                _name = $scope.struct.selection.name + " #{_idx}"
                if _name not in _names
                    break
                else
                    _idx++
            $scope.struct.selection.name = _name
        icswSavedSelectionService.save_selection(
            icswUserService.get()
            $scope.struct.selection
        ).then(
            (new_sel) ->
                $scope.struct.selection_for_dropdown = $scope.struct.selection.db_obj
                $scope.struct.synced = true
        )

    $scope.unselect = () ->
        # console.log "unselect"
        $scope.struct.synced = false
        icswActiveSelectionService.unsync_selection()
        $scope.struct.selection_for_dropdown = undefined

    $scope.use_selection = (new_sel, b) ->
        console.log "use_selection"
        $scope.struct.selection_for_dropdown = new_sel
        icswActiveSelectionService.sync_selection(new_sel)
        (cur_tc.clear_selected() for cur_tc in [$scope.tc_devices, $scope.tc_groups, $scope.tc_categories])
        $scope.tc_devices.iter(
            (entry, bla) ->
                if entry._node_type == "d"
                    entry.set_selected($scope.struct.selection.device_selected(entry.obj))
        )
        $scope.tc_groups.iter(
            (entry, bla) ->
                if entry._node_type == "g"
                    entry.set_selected($scope.struct.selection.device_group_selected(entry.obj))
        )
        $scope.tc_categories.iter(
            (entry, bla) ->
                if entry._node_type == "c"
                    entry.set_selected($scope.struct.selection.category_selected(entry.obj))
        )
        # apply new selection
        for cur_tc in [$scope.tc_devices, $scope.tc_groups, $scope.tc_categories]
            cur_tc.recalc()
            cur_tc.show_selected()
        $scope.selection_changed()

    $scope.delete_selection = () ->
        if $scope.struct.synced
            icswToolsSimpleModalService("Delete Selection #{$scope.struct.selection.name} ?").then(
                () ->
                    icswSavedSelectionService.delete_selection($scope.struct.selection).then(
                        (new_list) ->
                            $scope.struct.selection_for_dropdown = undefined
                            $scope.struct.synced = false
                            icswActiveSelectionService.unsync_selection()
                            $scope.saved_selections = new_list
                    )
            )

    $scope.show_current_selection_in_overlay = () ->
        devsel_list = $scope.struct.selection.get_devsel_list()
        selected_devices = ($scope.struct.device_tree.all_lut[_pk] for _pk in devsel_list[0])
        DeviceOverviewSelection.set_selection(selected_devices)
        DeviceOverviewService(event, selected_devices)
        console.log "show_current_selection"

    $scope.select_parents = () ->
        blockUI.start("Selecting parents...")
        $scope.struct.selection.select_parent().then(
            () ->
                $scope.tc_devices.iter(
                    (node, data) ->
                        node.selected = node.obj in $scope.struct.selection.tot_dev_sel
                )
                $scope.tc_devices.recalc()
                $scope.tc_groups.show_selected(false)
                $scope.tc_categories.show_selected(false)
                $scope.tc_devices.show_selected(false)
                $scope.selection_changed()
                $scope.activate_tab("d")
                blockUI.stop()
        )
]).service("icswLayoutSelectionDialogService",
[
    "$q", "$compile", "$templateCache", "$state", "icswToolsSimpleModalService",
    "$rootScope", "ICSW_SIGNALS",
(
    $q, $compile, $templateCache, $state, icswToolsSimpleModalService,
    $rootScope, ICSW_SIGNALS
) ->
    # dialog_div =
    prev_left = undefined
    prev_top = undefined
    _active = false
    quick_dialog = () ->
        if !_active
            _active = true
            state_name = $state.current.name
            sel_scope = $rootScope.$new()
            dialog_div = $compile($templateCache.get("icsw.layout.selection.modify"))(sel_scope)
            console.log "SelectionDialog", state_name
            # signal controller
            $rootScope.$emit(ICSW_SIGNALS("ICSW_SELECTOR_SHOW"), state_name)
            BootstrapDialog.show
                message: dialog_div
                title: "Device Selection"
                draggable: true
                animate: false
                closable: true
                onshown: (ref) ->
                    # hack to position to the left
                    _tw = ref.getModal().width()
                    _diag = ref.getModalDialog()
                    if prev_left?
                        $(_diag[0]).css("left", prev_left)
                        $(_diag[0]).css("top", prev_top)
                    else
                        $(_diag[0]).css("left", - (_tw - 600)/2)
                    sel_scope.modal = ref
                onhidden: (ref) ->
                    _diag = ref.getModalDialog()
                    prev_left = $(_diag[0]).css("left")
                    prev_top = $(_diag[0]).css("top")
                    sel_scope.$destroy()
                    _active = false
                buttons: [
                    {
                        icon: "glyphicon glyphicon-ok"
                        cssClass: "btn-warning"
                        label: "close"
                        action: (ref) ->
                            ref.close()
                    }
                ]
    return {
        quick_dialog: () ->
            return quick_dialog()
    }
]).service("icswLayoutSelectionTreeService",
[
    "DeviceOverviewService", "icswReactTreeConfig", "icswDeviceTreeService",
    "DeviceOverviewSelection",
(
    DeviceOverviewService, icswReactTreeConfig, icswDeviceTreeService,
    DeviceOverviewSelection
) ->
    class icswLayoutSelectionTree extends icswReactTreeConfig
        constructor: (@scope, @notifier, args) ->
            # args.debug_mode = true
            super(args)
            @current = undefined

        ensure_current: () =>
            if not @current
                @current = icswDeviceTreeService.current()

        handle_click: (event, entry) =>
            @ensure_current()
            if entry._node_type == "d"
                dev = @current.all_lut[entry.obj]
                DeviceOverviewSelection.set_selection([dev])
                DeviceOverviewService(event)
                @notifier.notify("go")
            else
                entry.set_selected(not entry.selected)
                @notifier.notify("go")
            # need $apply() here, $digest is not enough

        get_name: (t_entry) =>
            @ensure_current()
            entry = @get_dev_entry(t_entry)
            if t_entry._node_type == "f"
                if entry.parent
                    return "#{entry.name} (*.#{entry.full_name})"
                else
                    return "[TLN]"
            else if t_entry._node_type == "c"
                if entry.depth
                    _res = entry.name
                    cat = @current.cat_tree.lut[t_entry.obj]
                    if cat.reference_dict.device.length
                        _res = "#{_res} (#{cat.reference_dict.device.length} devices)"
                else
                    _res = "[TOP]"
                return _res
            else if t_entry._node_type == "g"
                _res = entry.name
                group = @current.group_lut[t_entry.obj]
                # ignore meta device
                if group.num_devices
                    _res = "#{_res} (#{group.num_devices} devices)"
                return _res
            else
                info_f = []
                if entry.is_meta_device
                    d_name = entry.full_name.slice(8)
                else
                    d_name = entry.full_name
                if entry.comment
                    info_f.push(entry.comment)
                if info_f.length
                    d_name = "#{d_name} (" + info_f.join(", ") + ")"
                return d_name

        get_icon_class: (t_entry) =>
            if t_entry._node_type == "d"
                entry = @get_dev_entry(t_entry)
                if entry.is_meta_device
                    return "dynatree-icon"
                else
                    return ""
            else
                return "dynatree-icon"

        get_dev_entry: (t_entry) =>
            if t_entry._node_type == "g"
                return @scope.struct.device_tree.group_lut[t_entry.obj]
            else if t_entry._node_type == "c"
                return @scope.struct.device_tree.cat_tree.lut[t_entry.obj]
            else
                return @scope.struct.device_tree.all_lut[t_entry.obj]

        selection_changed: () =>
            @scope.selection_changed()
            @notifier.notify("go")
])
