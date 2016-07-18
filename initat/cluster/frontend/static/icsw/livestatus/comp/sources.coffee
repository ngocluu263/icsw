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

# livestatus sources and filter functions (components)

angular.module(
    "icsw.livestatus.comp.sources",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.router",
    ]
).service("icswSaltMonitoringResultService", [() ->

    _parse_custom_variables = (cvs) ->
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
                    _list = (parseInt(_sv) for _sv in _cv[int_mkey] when _sv != "-")
                    if _list.length
                        _cv[int_mkey] = _list
                    else
                        delete _cv[int_mkey]
        return _cv

    _get_diff_time = (ts) ->
        if parseInt(ts)
            return moment.unix(ts).fromNow(true)
        else
            return "never"

    _get_attempt_info = (entry) ->
        if entry.max_check_attempts == null
            return "N/A"
        else
            try
                max = parseInt(entry.max_check_attempts)
                cur = parseInt(entry.current_attempt)
                if max == cur
                    return "#{cur}"
                else
                    return "#{cur} / #{max}"
            catch error
                return "e"
            
    _get_attempt_class = (entry) ->
        if entry.max_check_attempts == null
            _r_str = "default"
        else
            try
                max = parseInt(entry.max_check_attempts)
                cur = parseInt(entry.current_attempt)
                if max == cur
                    _r_str = "info"
                else
                    _r_str = "success"
            catch error
                _r_str = "danger"
        return "label-#{_r_str}"
            
    _sanitize_entry = (entry) ->
        entry.$$dummy = false
        entry.state = parseInt(entry.state)
        if entry.state_type in ["0", "1"]
            entry.state_type = parseInt(entry.state_type)
        else
            entry.state_type = null
        if entry.check_type in ["0", "1"]
            entry.check_type = parseInt(entry.check_type)
        else
            entry.check_type = null
        entry.$$icswStateTypeString = {
            null: "???"
            0: "soft"
            1: "hard"
        }[entry.state_type]
        entry.$$icswCheckTypeString = {
            null: "???"
            0: "active"
            1: "passive"
        }[entry.check_type]
        entry.$$icswPassiveCheck = if entry.check_type then true else false
        entry.$$icswAttemptLabelClass = _get_attempt_class(entry)
        entry.$$icswAttemptInfo = _get_attempt_info(entry)
        try
            if parseInt(entry.current_attempt) == 1
                _si = true
            else
                _si = true
        catch error
           _si = true
        entry.$$icswShowAttemptInfo = _si
        entry.$$icswLastCheckString = _get_diff_time(entry.last_check)
        entry.$$icswLastStateChangeString = _get_diff_time(entry.last_state_change)

        # custom variables

        entry.custom_variables = _parse_custom_variables(entry.custom_variables)

    _get_dummy_entry = (display_name, ct) ->
        entry = {
            $$burst_fill_color: "#dddddd"
            display_name: display_name
            $$ct: ct
            $$dummy: false
        }
        return entry

    get_dummy_service_entry = (display_name) ->
        entry = _get_dummy_entry(display_name, "service")
        # is a dummy entry
        entry.$$dummy = true
        entry.state = "4"
        entry.state_type = "1"
        entry.check_type = "0"
        salt_service_state(entry)
        return entry

    get_device_group_entry = (display_name) ->
        entry = _get_dummy_entry(display_name, "devicegroup")
        return entry

    get_system_entry = (display_name) ->
        entry = _get_dummy_entry(display_name, "system")
        return entry

    get_unmonitored_device_entry = (dev) ->
        # dev ... device_tree device
        entry = _get_dummy_entry(dev.full_name, "device")
        entry.$$dummy = true
        # important: state type is 1 (== hard state) and check_type is 0 (== active)
        entry.state = "4"
        entry.state_type = "1"
        entry.check_type = "0"
        # fake custom vars
        entry.custom_variables = "DEVICE_PK|#{dev.idx},UUID|#{dev.uuid}"
        return entry

    _device_lut = {
        0: {
            color: "#66dd66"
            info: "Up"
        }
        1: {
            color: "#ff7777"
            info: "Down"
        }
        2: {
            color: "#ff0000"
            info: "Unreachable"
        }
        3: {
            color: "#dddddd"
            info: "Unknown"
        }
        4: {
            color: "#888888"
            info: "not monitored"
        }
    }

    _service_lut = {
        0: {
            color: "#66dd66"
            info: "OK"
        }
        1: {
            color: "#dddd88"
            info: "Warning"
        }
        2: {
            color: "#ff7777"
            info: "Critical"
        }
        3: {
            color: "#ff0000"
            info: "Unknown"
        }
        4: {
            color: "#888888"
            info: "not monitored"
        }
    }
    _struct = {
        device_lut: _device_lut
        service_lut: _service_lut
        device_states: [0, 1, 2, 3, 4]
        service_states: [0, 1, 2, 3, 4]
    }
    salt_device_state = (entry) ->
        entry.$$burst_fill_color = _device_lut[entry.state].color
        entry.className = {
            0: "svg_ok"
            1: "svg_warn"
            2: "svg_crit"
            3: "svg_unknown"
            4: "svg_unknown"
        }[entry.state]
        _r_str = {
            0: "success"
            1: "danger"
            2: "danger"
            3: "warning"
            4: "danger"
        }[entry.state]
        entry.$$icswStateClass = _r_str
        # entry.$$icswStateLabelClass = "label-#{_r_str}"
        entry.$$icswStateTextClass = "text-#{_r_str}"
        entry.$$icswStateString = {
            0: "OK"
            1: "Critical"
            2: "Unreachable"
            3: "Not set"
            4: "Not monitored"
        }[entry.state]

    salt_service_state = (entry) ->
        _r_str = {
            0: "success"
            1: "warning"
            2: "danger"
            3: "danger"
            # special state: unmonitored
            4: "danger"
        }[entry.state]
        entry.className = {
            0: "svg_ok"
            1: "svg_warn"
            2: "svg_crit"
            3: "svg_danger"
            4: "svg_unknown"
        }[entry.state]
        entry.$$burst_fill_color = _service_lut[entry.state].color
        entry.$$icswStateClass = _r_str
        # entry.$$icswStateLabelClass = "label-#{_r_str}"
        entry.$$icswStateTextClass = "text-#{_r_str}"
        entry.$$icswStateString = {
            0: "OK"
            1: "Warning"
            2: "Critical"
            3: "Unknown"
            4: "unmon"
        }[entry.state]

    salt_host = (entry, device_tree, cat_tree, device_cat_pks) ->
        if not entry.$$icswSalted?
            entry.$$service_list = []
            entry.$$icswSalted = true
            # set default values
            entry.$$ct = "device"
            # sanitize entries
            _sanitize_entry(entry)
            # host state class
            salt_device_state(entry)
            entry.$$icswDevice = device_tree.all_lut[entry.custom_variables.device_pk]
            # for display
            entry.display_name = entry.$$icswDevice.full_name
            # link back, highly usefull
            entry.$$icswDevice.$$host_mon_result = entry
            entry.$$icswDeviceGroup = device_tree.group_lut[entry.$$icswDevice.device_group]
            entry.$$device_categories = _.intersection(entry.$$icswDevice.categories, device_cat_pks)
            if entry.$$device_categories.length
                entry.$$icswCategories = (cat_tree.lut[_cat].name for _cat in entry.$$device_categories).join(", ")
            else
                entry.$$icswCategories = "---"
        return entry

    salt_service = (entry, cat_tree) ->
        if not entry.$$icswSalted?
            entry.$$icswSalted = true
            # set default values
            entry.$$ct = "service"
            # sanitize entries
            _sanitize_entry(entry)
            # service state class
            salt_service_state(entry)
            # resolve categories
            if entry.custom_variables.cat_pks?
                entry.$$icswCategories = (cat_tree.lut[_cat].name for _cat in entry.custom_variables.cat_pks).join(", ")
            else
                entry.$$icswCategories = "---"
            entry.$$search_string = "#{entry.plugin_output} #{entry.description}" 
        return entry

    build_circle_info = (in_type, in_dict, detail_dict) ->
        # transform a device or service dict (state -> num) to an array
        # detail_dict: to add detailed info (categories, location, ...)
        # which is usable for device_circle_info
        _r_list = []
        _lut = _struct["#{in_type}_lut"]
        for _state in _struct["#{in_type}_states"]
            if _state of in_dict
                _count = in_dict[_state]
                _ps = if _count > 1 then "s" else ""
                _info_str = "#{_count} #{in_type}#{_ps} #{_lut[_state].info}"
                if detail_dict?
                    _sub_keys = _.keys(detail_dict[_state])
                    _info_str = "#{_info_str}, #{_sub_keys.length} subelements"
                _info = [_count, _lut[_state].color, _info_str]
                if detail_dict?
                    _info.push(detail_dict[_state])
                _r_list.push(_info)
        return _r_list

    return {
        get_unmonitored_device_entry: get_unmonitored_device_entry

        get_dummy_service_entry: get_dummy_service_entry

        get_device_group_entry: get_device_group_entry

        get_system_entry: get_system_entry

        salt_device_state: salt_device_state

        salt_host: salt_host

        salt_service: salt_service

        build_circle_info: build_circle_info
    }
]).service("icswMonitoringResult",
[
    "$q", "icswTools", "icswSaltMonitoringResultService",
(
    $q, icswTools, icswSaltMonitoringResultService,
) ->
    class icswMonitoringResult
        constructor: () ->
            @id = icswTools.get_unique_id("monres")
            # selection generation
            @sel_generation = 0
            # result generation
            @generation = 0
            # notifier for new data
            @result_notifier = $q.defer()
            @hosts = []
            @services = []
            # counter dicts
            @mon_cat_counters = {}
            @device_cat_counters = {}
            @_create_used_fields()
            @__luts_set = false

        new_selection: () =>
            # hm, not needed ... ?
            @sel_generation++

        stop_receive: () =>
            @result_notifier.reject("stop")

        copy_from: (src) =>
            # copy objects from src
            @update(src.hosts, src.services, src.mon_cat_counters, src.device_cat_counters)
            
        update: (hosts, services, mon_cat_counters, device_cat_counters) =>
            @generation++
            @__luts_set = false
            @hosts.length = 0
            for entry in hosts
                @hosts.push(entry)
            @services.length = 0
            for entry in services
                @services.push(entry)
            @mon_cat_counters = mon_cat_counters
            @device_cat_counters = device_cat_counters
            @_create_used_fields()
            # console.log "update", @generation
            @notify()

        notify: () =>
            @result_notifier.notify(@generation)

        # helper functions
        _copy_list: (attr_name, src_data) =>
            @[attr_name].length = 0
            for entry in src_data[attr_name]
                @[attr_name].push(entry)

        _copy_dict: (attr_name, src_data) =>
            @[attr_name] = _.cloneDeep(src_data[attr_name])

        _create_used_fields: () =>
            # used monitoring categories
            @used_mon_cats = (parseInt(_v) for _v in _.keys(@mon_cat_counters))
            # used device categories
            @used_device_cats = (parseInt(_v) for _v in _.keys(@device_cat_counters))

        apply_base_filter: (filter, src_data) =>
            # apply base livestatus filter
            @__luts_set = false
            # for linked mode
            _host_pks = []

            @hosts.length = 0
            device_cat_counters = {}
            # _device_cats = []
            for entry in src_data.hosts
                if filter.host_types[entry.state_type] and filter.host_states[entry.state]
                    @hosts.push(entry)
                    device_cat_counters = icswTools.merge_count_dict(device_cat_counters, _.countBy(entry.$$device_categories))
                    _host_pks.push(entry.$$icswDevice.idx)

            @services.length = 0
            mon_cat_counters = {}
            for entry in src_data.services
                if filter.linked and entry.$$host_mon_result.$$icswDevice.idx not in _host_pks
                    true
                else if filter.service_types[entry.state_type] and filter.service_states[entry.state]
                    @services.push(entry)
                    if entry.custom_variables? and entry.custom_variables.cat_pks?
                        mon_cat_counters = icswTools.merge_count_dict(mon_cat_counters, _.countBy(entry.custom_variables.cat_pks))

            # reduce mon and device cats
            @device_cat_counters = device_cat_counters
            @mon_cat_counters = mon_cat_counters
            @_create_used_fields()

            # bump generation counter
            @generation++

        apply_category_filter: (cat_list, src_data, filter_name) =>
            # filter name is mon or device
            @__luts_set = false
            # show uncategorized entries
            _zero_cf = 0 in cat_list
            if filter_name == "mon"
                # copy hosts
                @_copy_list("hosts", src_data)
                @_copy_dict("device_cat_counters", src_data)
                # filter services
                @services.length = 0
                mon_cat_counters = {}
                for entry in src_data.services
                    _add = true
                    if entry.custom_variables? and entry.custom_variables.cat_pks?
                        if not _.intersection(cat_list, entry.custom_variables.cat_pks).length
                            _add = false
                    else if not _zero_cf
                        _add = false
                    if _add
                        @services.push(entry)
                        mon_cat_counters = icswTools.merge_count_dict(mon_cat_counters, _.countBy(entry.custom_variables.cat_pks))
                @mon_cat_counters = mon_cat_counters
            else
                _host_pks = []
                # device filter
                @hosts.length = 0
                device_cat_counters = {}
                for entry in src_data.hosts
                    _add = true
                    if entry.$$device_categories.length
                        if not _.intersection(cat_list, entry.$$device_categories).length
                            _add = false
                    else if not _zero_cf
                        _add = false
                    if _add
                        @hosts.push(entry)
                        _host_pks.push(entry.$$icswDevice.idx)
                        device_cat_counters = icswTools.merge_count_dict(device_cat_counters, _.countBy(entry.$$device_categories))
                @device_cat_counters = device_cat_counters
                # only take services on a valid host
                @services.length = 0
                mon_cat_counters = {}
                for entry in src_data.services
                    if entry.$$host_mon_result.$$icswDevice.idx in _host_pks
                        @services.push(entry)
                        mon_cat_counters = icswTools.merge_count_dict(mon_cat_counters, _.countBy(entry.custom_variables.cat_pks))
                @mon_cat_counters = mon_cat_counters

            @_create_used_fields()
            # bump generation counter
            @generation++
            
        build_luts: () =>
            if @__luts_set
                return
            # lookup tables
            @__luts_set = true
            _srv_lut = {}
            _srv_cat_lut = {}
            for srv in @services
                if srv.state not of _srv_lut
                    _srv_lut[srv.state] = 0
                    _srv_cat_lut[srv.state] = {}
                _srv_lut[srv.state]++
                if srv.custom_variables? and srv.custom_variables.cat_pks?
                    _cats = srv.custom_variables.cat_pks
                else
                    # no category
                    _cats = [0]
                for _cat in _cats
                    if _cat not of _srv_cat_lut[srv.state]
                        _srv_cat_lut[srv.state][_cat] = 0
                    _srv_cat_lut[srv.state][_cat]++
            _host_lut = {}
            _host_cat_lut = {}
            for host in @hosts
                if host.state not of _host_lut
                    _host_lut[host.state] = 0
                    _host_cat_lut[host.state] = {}
                _host_lut[host.state]++
                for _cat in host.$$device_categories
                    if _cat not of _host_cat_lut[host.state]
                        _host_cat_lut[host.state][_cat] = 0
                    _host_cat_lut[host.state][_cat]++
            @service_circle_data = icswSaltMonitoringResultService.build_circle_info("service", _srv_lut)
            @device_circle_data = icswSaltMonitoringResultService.build_circle_info("device", _host_lut)
            @service_circle_data_details = icswSaltMonitoringResultService.build_circle_info("service", _srv_lut, _srv_cat_lut)
            @device_circle_data_details = icswSaltMonitoringResultService.build_circle_info("device", _host_lut, _host_cat_lut)

]).service("icswDeviceLivestatusDataService",
[
    "ICSW_URLS", "$interval", "$timeout", "icswSimpleAjaxCall", "$q", "icswDeviceTreeService",
    "icswMonitoringResult", "icswSaltMonitoringResultService", "icswCategoryTreeService", "icswTools",
(
    ICSW_URLS, $interval, $timeout, icswSimpleAjaxCall, $q, icswDeviceTreeService,
    icswMonitoringResult, icswSaltMonitoringResultService, icswCategoryTreeService, icswTools,
) ->
    # dict: device.idx -> watcher ids
    watch_dict = {}

    # dict: watcher ids -> Monitoring result
    result_dict = {}

    destroyed_list = []
    cur_interval = undefined
    cur_xhr = undefined
    schedule_start_timeout = undefined

    # for lookup
    device_tree = undefined
    category_tree = undefined

    watchers_present = () ->
        # whether any watchers are present
        return _.keys(result_dict).length > 0

    schedule_load = () ->
        # called when new listeners register
        # don't update immediately, wait until more controllers have registered
        if not schedule_start_timeout?
            schedule_start_timeout = $timeout(load_data, 1)

    start_interval = () ->
        # start regular update
        # this is additional to schedule_load
        if cur_interval?
            $interval.cancel(cur_interval)
        cur_interval = $interval(load_data, 20000) #20000)

    stop_interval = () ->
        # stop regular update
        if cur_interval?
            $interval.cancel(cur_interval)
        if cur_xhr?
            cur_xhr.abort()

    remove_watchers_by_client = (client) ->
        remove_device_watchers_by_client(client)
        # remove from result list
        # console.log "RWBC", client.toString(), result_dict[client.toString()]
        result_dict[client.toString()].stop_receive()
        delete result_dict[client.toString()]

    remove_device_watchers_by_client = (client) ->
        client = client.toString()
        for dev, watchers of watch_dict
            _.remove(watchers, (elem) -> return elem == client)

    load_data = () ->
        if schedule_start_timeout?
            $timeout.cancel(schedule_start_timeout)
            schedule_start_timeout = undefined

        # only continue if anyone is actually watching
        if watchers_present()

            watched_devs = []
            for dev of watch_dict
                if watch_dict[dev].length > 0
                    watched_devs.push(dev)

            _waiters = [
                icswSimpleAjaxCall(
                    url: ICSW_URLS.MON_GET_NODE_STATUS
                    data: {
                        pk_list: angular.toJson(watched_devs)
                    }
                    show_error: false
                )
            ]
            if not device_tree?
                _load_device_tree = true
                _waiters.push(
                    icswDeviceTreeService.load("liveStatusDataService")
                )
                _waiters.push(
                    icswCategoryTreeService.load("liveStatusDataService")
                )
            else
                _load_device_tree = false
            $q.allSettled(
                _waiters
            ).then(
                (result) ->
                    if _load_device_tree
                        # DeviceTreeService was requested
                        device_tree = result[1].value
                        category_tree = result[2].value
                    service_entries = []
                    host_entries = []
                    mon_cat_counters = {}
                    device_cat_counters = {}
                    if result[0].state == "fulfilled"
                        # fill service and host_entries, used cats
                        xml = result[0].value
                        $(xml).find("value[name='service_result']").each (idx, node) =>
                            service_entries = service_entries.concat(angular.fromJson($(node).text()))
                        $(xml).find("value[name='host_result']").each (idx, node) =>
                            host_entries = host_entries.concat(angular.fromJson($(node).text()))
                        _unknown_hosts = (parseInt(_idx) for _idx in watched_devs)
                        # get all device cats
                        _dev_cat_pks = (_entry.idx for _entry in category_tree.list when _entry.full_name.match(/\/device\//))
                        for entry in host_entries
                            icswSaltMonitoringResultService.salt_host(entry, device_tree, category_tree, _dev_cat_pks)
                            device_cat_counters = icswTools.merge_count_dict(device_cat_counters, _.countBy(entry.$$device_categories))
                            # for _dc in entry.$$
                            _.remove(_unknown_hosts, (_idx) -> return _idx == entry.$$icswDevice.idx)
                        for _idx in _unknown_hosts
                            if _idx of device_tree.all_lut
                                dev = device_tree.all_lut[_idx]
                                _um_entry = icswSaltMonitoringResultService.get_unmonitored_device_entry(dev)
                                icswSaltMonitoringResultService.salt_host(_um_entry, device_tree, category_tree, _dev_cat_pks)
                                device_cat_counters = icswTools.merge_count_dict(device_cat_counters, _.countBy(_um_entry.$$device_categories))
                                host_entries.push(_um_entry)
                        srv_id = 0
                        for entry in service_entries
                            srv_id++
                            entry.$$idx = srv_id
                            icswSaltMonitoringResultService.salt_service(entry, category_tree)
                            # host mon result
                            h_m_result = device_tree.all_lut[entry.custom_variables.device_pk].$$host_mon_result
                            # link
                            h_m_result.$$service_list.push(entry)
                            entry.$$host_mon_result = h_m_result
                            if entry.custom_variables and entry.custom_variables.cat_pks?
                                mon_cat_counters = icswTools.merge_count_dict(mon_cat_counters, _.countBy(entry.custom_variables.cat_pks))
                    else
                        # invalidate results
                        for dev_idx, watchers of watch_dict
                            if dev_idx of device_tree.all_lut
                                device_tree.all_lut[dev_idx].$$host_mon_result = undefined
                    for client, _result of result_dict
                        # signal clients even when no results were received
                        hosts_client = []
                        services_client = []
                        # host_lut_client = {}
                        for dev_idx, watchers of watch_dict
                            if client in watchers and dev_idx of device_tree.all_lut
                                dev = device_tree.all_lut[dev_idx]
                                if dev.$$host_mon_result?
                                    entry = dev.$$host_mon_result
                                    hosts_client.push(entry)
                                    for check in entry.$$service_list
                                        services_client.push(check)
                        _result.update(hosts_client, services_client, mon_cat_counters, device_cat_counters)
            )

    return {
        # not needed here
        # resolve_host: (name) ->
        #    return _host_lut[name]

        retain: (client, dev_list) ->
            _defer = $q.defer()
            # get data for devices of dev_list for client (same client instance must be passed to cancel())

            # remove watchers in case of updates
            remove_device_watchers_by_client(client)

            client = client.toString()
            if client not in destroyed_list  # when client get the destroy event, they may still execute data, so we need to catch this here
                if not watchers_present()
                    # if no watchers have been present, there also was no regular update
                    start_interval()

                if dev_list.length
                    # console.log "w", dev_list
                    for dev in dev_list
                        if not angular.isObject(dev)
                            console.error "device #{dev} for retain() is not an object"
                        else
                            if not watch_dict[dev.idx]?
                                watch_dict[dev.idx] = []

                            if client not in watch_dict[dev.idx]
                                watch_dict[dev.idx].push(client)

                if client not of result_dict
                    console.log "new client", client
                    result_dict[client] = new icswMonitoringResult()
                else
                    # console.log "k", client
                    # not really needed ?
                    result_dict[client].new_selection()

                _defer.resolve(result_dict[client])

                schedule_load()
            else
                _defer.reject("client in destroyed list")
                throw new Error("client #{client} in destroyed_list")
            # the promise resolves always immediately
            return _defer.promise

        destroy: (client) ->
            client = client.toString()
            destroyed_list.push(client)
            # don't watch for client anymore
            remove_watchers_by_client(client)

            if not watchers_present()
                stop_interval()

        stop: (client) ->
            client = client.toString()
            # don't watch for client anymore
            remove_watchers_by_client(client)

            if not watchers_present()
                stop_interval()
    }
]).service("icswLivestatusSelDevices",
[
    "$q", "$rootScope", "icswMonLivestatusPipeBase", "$timeout", "ICSW_SIGNALS",
    "icswDeviceTreeService", "icswDeviceLivestatusDataService", "icswTools",
    "icswActiveSelectionService", "icswMonitoringResult",
(
    $q, $rootScope, icswMonLivestatusPipeBase, $timeout, ICSW_SIGNALS,
    icswDeviceTreeService, icswDeviceLivestatusDataService, icswTools,
    icswActiveSelectionService, icswMonitoringResult,
) ->
    class icswLivestatusSelDevices extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusSelDevices", false, true)
            # pipe flags
            @__dp_async_emit = true

            @struct = {
                # local id
                local_id: icswTools.get_unique_id()
                # device list to emit
                device_list: []
                # device tree
                device_tree: undefined
                # raw selection
                raw_selection: undefined
                # monresult to emit
                mon_result: new icswMonitoringResult()
            }
            # todo: get the current selection after the pipe is fully initialised
            @dereg = $rootScope.$on(ICSW_SIGNALS("ICSW_OVERVIEW_EMIT_SELECTION"), (event) =>
                @get_selection()
            )
            icswActiveSelectionService.register_receiver()
            icswDeviceTreeService.load(@struct.local_id).then(
                (tree) =>
                    @struct.device_tree = tree
                    @check_raw_selection()
            )
            @get_selection()
            @set_async_emit_data(@struct.mon_result)

        get_selection: () =>
            @struct.raw_selection = icswActiveSelectionService.current().tot_dev_sel
            @check_raw_selection()

        check_raw_selection: () =>
            if @struct.device_tree? and @struct.raw_selection?
                @struct.device_list.length = 0
                for pk in @struct.raw_selection
                    if @struct.device_tree.all_lut[pk]?
                        _dev = @struct.device_tree.all_lut[pk]
                        if not _dev.is_meta_device
                            @struct.device_list.push(_dev)
                # we use MonitoringResult as a container to send the device selection down the pipe
                # console.log "EMIT"
                # here we go
                @struct.mon_result.update(@struct.device_list, [], [], [])

        pipeline_pre_close: () =>
            icswActiveSelectionService.unregister_receiver()
            # console.log "PPC"
            @dereg()

]).service("icswLivestatusDataSource",
[
    "$q", "$rootScope", "icswMonLivestatusPipeBase", "$timeout",
    "icswDeviceTreeService", "icswDeviceLivestatusDataService", "icswTools",
(
    $q, $rootScope, icswMonLivestatusPipeBase, $timeout,
    icswDeviceTreeService, icswDeviceLivestatusDataService, icswTools,
) ->
    class icswLivestatusDataSource extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusDataSource", true, true)
            @__dp_async_emit = true
            @struct = {
                # local id, created for every call to start()
                local_id: undefined
                # device list
                devices: []
                # is updating
                updating: false
                # data fetch timeout
                fetch_timeout: undefined
                # monitoring data
                is_running: true
                # monitoring_data: undefined
                monitoring_data: undefined
            }

        set_running_flag: (flag) =>
            @struct.is_running = flag

        new_data_received: (data) =>
            @struct.devices.length = 0
            for dev in data.hosts
                if not dev.is_meta_device
                    @struct.devices.push(dev)
            @start()
            # important because we are an asynchronous emitter
            return null

        stop_update: () =>
            if @struct.fetch_timeout
                $timeout.cancel(@struct.fetch_timeout)
                @struct.fetch_timeout = undefined
            if @struct.monitoring_data?
                @struct.monitoring_data.stop_receive()
                # destroy current fetcher
                icswDeviceLivestatusDataService.destroy(@struct.local_id)

        pipeline_pre_close: () =>
            if @struct.monitoring_data?
                icswDeviceLivestatusDataService.destroy(@struct.local_id)

        start: () =>
            @stop_update()
            @struct.updating = true
            @struct.local_id = icswTools.get_unique_id()
            wait_list = [
                icswDeviceLivestatusDataService.retain(@struct.local_id, @struct.devices)
            ]
            $q.all(wait_list).then(
                (data) =>
                    @struct.updating = false
                    @struct.monitoring_data = data[0]
                    @set_async_emit_data(@struct.monitoring_data)
            )
]).service("icswLivestatusLocationDisplay",
[
    "$q", "icswMonLivestatusPipeBase", "icswMonitoringResult",
(
    $q, icswMonLivestatusPipeBase, icswMonitoringResult,
) ->
    class icswLivestatusLocationDisplay extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusLocationDisplay", true, false)
            @set_template(
                '<icsw-livestatus-location-display icsw-connect-element="con_element"></icsw-livestatus-location-display>'
                "LocationDisplay"
                8
                8
            )
            @new_data_notifier = $q.defer()
            #  @new_data_notifier = $q.defer()

        new_data_received: (data) ->
            @new_data_notifier.notify(data)

        pipeline_reject_called: (reject) ->
            @new_data_notifier.reject("stop")
            
]).directive("icswLivestatusLocationDisplay",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.config.category.location.show")
        scope: {
            con_element: "=icswConnectElement"
        }
        controller: "icswConfigCategoryLocationCtrl"
        link: (scope, element, attrs) ->
            scope.set_mode("show")
    }
]).service("icswLivestatusMapDisplay",
[
    "$q", "icswMonLivestatusPipeBase", "icswMonitoringResult",
(
    $q, icswMonLivestatusPipeBase, icswMonitoringResult,
) ->
    class icswLivestatusMapDisplay extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusMapDisplay", true, false)
            @set_template(
                '<icsw-device-livestatus-maplist icsw-connect-element="con_element"></icsw-device-livestatus-maplist>'
                "LocationDisplay"
                10
                16
            )
            @new_data_notifier = $q.defer()
            #  @new_data_notifier = $q.defer()

        new_data_received: (data) ->
            @new_data_notifier.notify(data)

        pipeline_reject_called: (reject) ->
            @new_data_notifier.reject("stop")

]).directive("icswDeviceLivestatusMaplist",
[
    "$compile", "$templateCache", "icswCachingCall", "$q", "ICSW_URLS", "$timeout",
(
    $compile, $templateCache, icswCachingCall, $q, ICSW_URLS, $timeout,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.livestatus.maplist")
        scope: {
            con_element: "=icswConnectElement"
        }
        controller: "icswDeviceLivestatusMaplistCtrl"
        link: (scope, element, attrs) ->
            scope.link(scope.con_element.new_data_notifier)
    }
]).controller("icswDeviceLivestatusMaplistCtrl",
[
    "$scope", "icswCategoryTreeService", "$q", "$timeout", "$compile", "$templateCache",
    "icswComplexModalService", "toaster",
(
    $scope, icswCategoryTreeService, $q, $timeout, $compile, $templateCache,
    icswComplexModalService, toaster,
) ->

    $scope.struct = {
        # data valid
        data_valid: false
        # category tree
        cat_tree: undefined
        # gfx sizes
        gfx_sizes: ["1024x768", "1280x1024", "1920x1200", "800x600", "640x400"]
        # cur gfx
        cur_gfx_size: undefined
        # any maps present
        maps_present: false
        # monitoring data
        monitoring_data: undefined
        # location list
        loc_gfx_list: []
        # autorotate
        autorotate: false
        # page idx for autorotate
        page_idx: 1
        # page idx set by uib-tab
        cur_page_idx: 1
        # notifier for maps
        notifier: $q.defer()
        # current device idxs
        device_idxs: []
    }
    $scope.struct.cur_gfx_size = $scope.struct.gfx_sizes[0]

    load = () ->
        $scope.struct.data_valid = false
        $scope.struct.maps_present = false
        $q.all(
            [
                icswCategoryTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.cat_tree = data[0]
                $scope.struct.data_valid = true
                check_for_maps()
        )

    check_for_maps = () ->
        dev_idxs = (dev.$$icswDevice.idx for dev in $scope.struct.monitoring_data.hosts)
        if _.difference(dev_idxs, $scope.struct.device_idxs).length
            $scope.struct.device_idxs = dev_idxs
            # check for valid maps for current device selection
            $scope.struct.loc_gfx_list.length = 0
            $scope.struct.page_idx = 1
            _deactivate_rotation()
            loc_idx_used = []
            for gfx in $scope.struct.cat_tree.gfx_list
                gfx.$$filtered_dml_list = []
                for dml in gfx.$dml_list
                    if dml.device in dev_idxs
                        if dml.location_gfx not in loc_idx_used
                            loc_idx_used.push(gfx.idx)
                            $scope.struct.loc_gfx_list.push(gfx)
                            gfx.$$page_idx = $scope.struct.loc_gfx_list.length
                        gfx.$$filtered_dml_list.push(dml)
            $scope.struct.maps_present = $scope.struct.loc_gfx_list.length > 0
        $scope.struct.notifier.notify()

    $scope.link = (notifier) ->
        load_called = false
        notifier.promise.then(
            (resolved) ->
            (rejected) ->
                # rejected, done
                $scope.struct.notifier.reject("stop")
            (data) ->
                if not load_called
                    load_called = true
                    $scope.struct.monitoring_data = data
                    load()
                else if $scope.struct.data_valid
                    check_for_maps()
        )

    # rotation functions

    _activate_rotation = () ->
        _pi = $scope.struct.page_idx
        _pi++
        if _pi < 1
            _pi = 1
        if _pi > $scope.struct.loc_gfx_list.length
            _pi = 1
        $scope.struct.page_idx = _pi
        $scope.struct.autorotate_timeout = $timeout(_activate_rotation, 8000)

    _deactivate_rotation = () ->
        $scope.struct.autorotate = false
        if $scope.struct.autorotate_timeout
            $timeout.cancel($scope.struct.autorotate_timeout)
            $scope.struct.autorotate_timeout = undefined

    $scope.toggle_autorotate = () ->
        $scope.struct.autorotate = !$scope.struct.autorotate
        if $scope.struct.autorotate
            _activate_rotation()
        else
            _deactivate_rotation()

    $scope.set_page_idx = (loc_gfx) ->
        $scope.struct.cur_page_idx = loc_gfx.$$page_idx

    $scope.show_settings = () ->
        sub_scope = $scope.$new(false)
        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.device.livestatus.maplist.settings"))(sub_scope)
                title: "Map settings"
                # css_class: "modal-wide"
                ok_label: "close"
                closable: true
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "", 0)
                        d.reject("form not valid")
                    else
                        d.resolve("updated")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
        )

]).factory("icswDeviceLivestatusLocationMapReact",
[
    "$q", "icswDeviceLivestatusReactBurst",
(
    $q, icswDeviceLivestatusReactBurst,
) ->
    {div, h4, g, image, svg, polyline} = React.DOM

    return React.createClass(
        propTypes: {
            location_gfx: React.PropTypes.object
            monitoring_data: React.PropTypes.object
            draw_parameters: React.PropTypes.object
            device_tree: React.PropTypes.object
            notifier: React.PropTypes.object
        }

        getInitialState: () ->
            return {
                width: 640
                height: 400
                counter: 0
            }

        set_size: (size_str) ->
            [_width, _height] = size_str.split("x")
            @setState(
                {
                    width: parseInt(_width)
                    height: parseInt(_height)
                }
            )

        componentWillMount: () ->
            @props.notifier.promise.then(
                () ->
                () ->
                    # will get called when the pipeline shuts down
                (c) =>
                    @force_redraw()
            )

        force_redraw: () ->
            @setState(
                {counter: @state.counter + 1}
            )

        render: () ->
            _gfx = @props.location_gfx
            # target width and height
            {width, height} = @state
            # gfx width and height
            _gfx_width = _gfx.width
            _gfx_height = _gfx.height
            # scale
            _scale_x = width / _gfx_width
            _scale_y = height / _gfx_height
            _scale = _.min([_scale_x, _scale_y])
            # console.log _scale_x, _scale_y, _scale
            _header = _gfx.name
            if _gfx.comment
                _header = "#{_header} (#{_gfx.comment})"
            _header = "#{_header} (#{_gfx_width} x #{_gfx_height}) * scale (#{_.round(_scale, 3)}) = (#{_.round(_gfx_width * _scale, 3)} x #{_.round(_gfx_height * _scale, 3)})"
            _header = "#{_header}, #{_gfx.$$filtered_dml_list.length} devices"

            _dml_list = [
                image(
                    {
                        key: "bgimage"
                        width: _gfx_width
                        height: _gfx_height
                        href: _gfx.image_url
                        preserveAspectRatio: "none"
                    }
                )
                polyline(
                    {
                        key: "imageborder"
                        style: {fill:"none", stroke:"black", strokeWidth:"3"}
                        points: "0,0 #{_gfx_width - 1},0 #{_gfx_width - 1},#{_gfx_height - 1} 0,#{_gfx_height - 1} 0 0"
                    }
                )
            ]
            # console.log @props
            for dml in _gfx.$$filtered_dml_list
                # build node
                node = {
                    id: dml.device
                    x: dml.pos_x
                    y: dml.pos_y
                }
                _dml_list.push(
                    React.createElement(
                        icswDeviceLivestatusReactBurst
                        {
                            node: node
                            key: "dml_node_#{dml.device}"
                            monitoring_data: @props.monitoring_data
                            draw_parameters: @props.draw_parameters
                        }
                    )
                )
            # console.log width, height, _gfx_width, _gfx_height
            return div(
                {
                    key: "top"
                }
                [
                    h4(
                        {
                            key: "header"
                        }
                        _header
                    )
                    svg(
                        {
                            key: "svgouter"
                            width: width
                            height: height
                            preserveAspectRatio: "xMidYMid meet"
                            viewBox: "0 0 #{_gfx_width} #{_gfx_height}"
                        }
                        [
                            g(
                                {
                                    key: "gouter"
                                    # scale not needed because of viewbox
                                    # transform: "scale(#{_scale})"
                                }
                                _dml_list
                            )
                        ]
                    )

                ]
            )
    )
]).directive("icswDeviceLivestatusLocationMap",
[
    "$templateCache", "$compile", "Restangular", "icswDeviceLivestatusLocationMapReact",
    "icswBurstDrawParameters", "icswDeviceTreeService", "$q",
(
    $templateCache, $compile, Restangular, icswDeviceLivestatusLocationMapReact,
    icswBurstDrawParameters, icswDeviceTreeService, $q,
) ->
    return {
        restrict: "EA"
        scope:
            loc_gfx: "=icswLocationGfx"
            monitoring_data: "=icswMonitoringData"
            gfx_size: "=icswGfxSize"
            # to notify when the data changes
            notifier: "=icswNotifier"
        link : (scope, element, attrs) ->
            draw_params = new icswBurstDrawParameters(
                {
                    inner_radius: 0
                    outer_radius: 90
                }
            )
            $q.all(
                [
                    icswDeviceTreeService.load(scope.$id)
                ]
            ).then(
                (data) ->
                    device_tree = data[0]
                    # console.log scope.monitoring_data, scope.filter
                    react_el = ReactDOM.render(
                        React.createElement(
                            icswDeviceLivestatusLocationMapReact
                            {
                                location_gfx: scope.loc_gfx
                                monitoring_data: scope.monitoring_data
                                draw_parameters: draw_params
                                device_tree: device_tree
                                notifier: scope.notifier
                            }
                        )
                        element[0]
                    )
                    scope.monitoring_data.result_notifier.promise.then(
                        () ->
                        () ->
                        (generation) =>
                            # console.log "gen", @props.livestatus_filter, @monitoring_data
                            react_el.force_redraw()
                    )
                    scope.$watch("gfx_size", (new_val) ->
                        react_el.set_size(new_val)
                    )
            )
    }
])
