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

angular.module(
    "icsw.svg_tools",
    []
).factory("svg_tools", () ->
    return {
        has_class_svg: (obj, has) ->
            classes = obj.attr("class")
            if !classes
                return false
            return if classes.search(has) == -1 then false else true
        get_abs_coordinate : (svg_el, x, y) ->
            screen_ctm = svg_el.getScreenCTM()
            svg_point = svg_el.createSVGPoint()
            svg_point.x = x
            svg_point.y = y
            first = svg_point.matrixTransform(screen_ctm.inverse())
            return first
            glob_to_local = event.target.getTransformToElement(scope.svg_el)
            second = first.matrixTransform(glob_to_local.inverse())
            return second
    }
)

angular.module(
    "icsw.mouseCapture",
    []
).factory('mouseCaptureFactory', ["$rootScope", ($rootScope) ->
    $element = document
    mouse_capture_config = null
    mouse_move = (event) ->
        if mouse_capture_config and mouse_capture_config.mouse_move
            mouse_capture_config.mouse_move(event)
            $rootScope.$digest()
    mouse_up = (event) ->
        if mouse_capture_config and mouse_capture_config.mouse_up
            mouse_capture_config.mouse_up(event)
            $rootScope.$digest()
    return {
        register_element: (element) ->
            $element = element
        acquire: (event, config) ->
            this.release()
            mouse_capture_config = config
            $element.mousemove(mouse_move)
            $element.mouseup(mouse_up)
        release: () ->
            if mouse_capture_config
                if mouse_capture_config.released
                    mouse_capture_config.released()
                mouse_capture_config = null;
                $element.unbind("mousemove", mouse_move)
                $element.unbind("mouseup", mouse_up)
    }
]).directive('icswMouseCapture', () ->
    return {
        restrict: "A"
        controller: ["$scope", "$element", "mouseCaptureFactory", ($scope, $element, mouseCaptureFactory) ->
            mouseCaptureFactory.register_element($element)
        ]
    }
)

angular.module(
    "icsw.dragging",
    [
        "icsw.mouseCapture"
    ]
).factory("dragging", ["$rootScope", "mouseCaptureFactory", ($rootScope, mouseCaptureFactory) ->
    return {
        start_drag: (event, threshold, config) ->
            dragging = false
            x = event.clientX
            y = event.clientY
            mouse_move = (event) ->
                if !dragging
                    if Math.abs(event.clientX - x) > threshold or Math.abs(event.clientY - y) > threshold
                        dragging = true;
                        if config.dragStarted
                            config.dragStarted(x, y, event)
                        if config.dragging
                            config.dragging(event.clientX, event.clientY, event)
                else 
                    if config.dragging
                        config.dragging(event.clientX, event.clientY, event);
                    x = event.clientX
                    y = event.clientY
            released = () ->
                if dragging
                    if config.dragEnded
                        config.dragEnded()
                else 
                    if config.clicked
                        config.clicked()
            mouse_up = (event) ->
                mouseCaptureFactory.release()
                event.stopPropagation()
                event.preventDefault()
            mouseCaptureFactory.acquire(event, {
                mouse_move: mouse_move
                mouse_up: mouse_up
                released: released
            })
            event.stopPropagation()
            event.preventDefault()
    }
])

angular.module(
    "icsw.device.network",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "icsw.d3", "ui.select",
        "angular-ladda", "icsw.dragging", "monospaced.mousewheel", "icsw.svg_tools", "icsw.tools", "icsw.tools.table",
    ]
).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.devicenetwork", {
            url: "/network"
            template: '<icsw-device-network-total></icsw-device-network-total>'
            data:
                pageTitle: "Network"
                rights: ["device.change_network"]
                menuEntry:
                    menukey: "dev"
                    icon: "fa-sitemap"
                    ordering: 30
        }
    )
]).controller("icswDeviceNetworkCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "restDataSource",
    "$q", "$uibModal", "icswAcessLevelService", "$rootScope", "$timeout", "blockUI", "icswTools", "icswToolsButtonConfigService", "ICSW_URLS",
    "icswSimpleAjaxCall", "icswToolsSimpleModalService", "icswDeviceTreeService", "icswNetworkTreeService",
    "icswDomainTreeService", "icswPeerInformationService", "icswDeviceTreeHelperService", "icswComplexModalService",
    "icswNetworkDeviceBackup", "toaster", "icswNetworkIPBackup", "icswPeerInformationBackup",
(
    $scope, $compile, $filter, $templateCache, Restangular, restDataSource,
    $q, $uibModal, icswAcessLevelService, $rootScope, $timeout, blockUI, icswTools, icswToolsButtonConfigService, ICSW_URLS,
    icswSimpleAjaxCall, icswToolsSimpleModalService, icswDeviceTreeService, icswNetworkTreeService,
    icswDomainTreeService, icswPeerInformationService, icswDeviceTreeHelperService, icswComplexModalService,
    icswNetworkDeviceBackup, toaster, icswNetworkIPBackup, icswPeerInformationBackup
) ->
    $scope.icswToolsButtonConfigService = icswToolsButtonConfigService
    icswAcessLevelService.install($scope)
    # copy flags
    $scope.show_copy_button = false
    # accordion flags
    $scope.device_open = true
    $scope.netdevice_open = true
    $scope.netip_open = false
    $scope.peer_open = false
    $scope.copy_coms = false
    # mixins

    $scope.peer_edit = new angular_edit_mixin($scope, $templateCache, $compile, Restangular, $q, "np")
    $scope.peer_edit.create_template = "peer.information.form"
    $scope.peer_edit.edit_template = "peer.information.form"
    #$scope.peer_edit.edit_template = "netip_template.html"
    $scope.peer_edit.create_rest_url = Restangular.all(ICSW_URLS.REST_PEER_INFORMATION_LIST.slice(1))
    $scope.peer_edit.modify_rest_url = ICSW_URLS.REST_PEER_INFORMATION_DETAIL.slice(1).slice(0, -2)
    $scope.peer_edit.new_object_at_tail = false
    $scope.peer_edit.use_promise = true

    $scope.boot_edit = new angular_edit_mixin($scope, $templateCache, $compile, Restangular, $q, "nb")
    $scope.boot_edit.edit_template = "device.boot.form"
    $scope.boot_edit.put_parameters = {"only_boot" : true}
    $scope.boot_edit.modify_rest_url = ICSW_URLS.REST_DEVICE_TREE_DETAIL.slice(1).slice(0, -2)
    $scope.boot_edit.new_object_at_tail = false
    $scope.boot_edit.use_promise = true

    $scope.scan_mixin = new angular_modal_mixin($scope, $templateCache, $compile, $q, "Scan network")
    $scope.scan_mixin.template = "device.network.scan.form"
    $scope.scan_mixin.cssClass = "modal-tall"

    $scope.ethtool_autoneg = [
        {"id": 0, "option": "default"},
        {"id": 1, "option": "on"},
        {"id": 2, "option": "off"},
    ]
    $scope.ethtool_duplex = [
        {"id": 0, "option": "default"},
        {"id": 1, "option": "on"},
        {"id": 2, "option": "off"},
    ]
    $scope.ethtool_speed = [
        {"id": 0, "option": "default"},
        {"id": 1, "option": "10 MBit"},
        {"id": 2, "option": "100 MBit"},
        {"id": 3, "option": "1 GBit"},
        {"id": 4, "option": "10 GBit"},
    ]
    $scope.devsel_list = []
    $scope.devices = []
    $scope.local_helper_obj = undefined
    $scope.remote_helper_obj = undefined
    $scope.new_devsel = (_dev_sel) ->
        dev_sel = (dev for dev in _dev_sel when not dev.is_meta_device)
        wait_list = [
            icswDeviceTreeService.fetch($scope.$id)
            icswNetworkTreeService.fetch($scope.$id)
            icswDomainTreeService.fetch($scope.$id)
            icswPeerInformationService.load($scope.$id, dev_sel)
        ]
        $q.all(wait_list).then(
            (data) ->
                $scope.device_tree = data[0]
                $scope.network_tree = data[1]
                $scope.domain_tree = data[2]
                $scope.peer_list = data[3]
                hs = icswDeviceTreeHelperService.create($scope.device_tree, dev_sel)
                $scope.device_tree.enrich_devices(hs, ["network_info"]).then(
                    (done) ->
                        # check if some devices have missing network_info
                        missing_list = $scope.peer_list.find_missing_devices($scope.device_tree)
                        defer = $q.defer()
                        if missing_list.length
                            # enrich devices with missing peer info
                            _en_devices = ($scope.device_tree.all_lut[pk] for pk in missing_list)
                            # temoprary hs
                            $scope.device_tree.enrich_devices(
                                icswDeviceTreeHelperService.create($scope.device_tree, _en_devices)
                                ["network_info"]
                            ).then(
                                (done) ->
                                    defer.resolve("remote enriched")
                            )
                        else
                            defer.resolve("nothing missing")
                        defer.promise.then(
                            (done) ->
                                # every device in the device tree is now fully populated
                                remote = $scope.peer_list.find_remote_devices($scope.device_tree, dev_sel)
                                temp_hs = icswDeviceTreeHelperService.create($scope.device_tree, ($scope.device_tree.all_lut[rem] for rem in remote))
                                # dummy call to enrich_devices, only used to create the lists and luts
                                $scope.device_tree.enrich_devices(
                                    temp_hs
                                    ["network_info"]
                                ).then(
                                    (done) ->
                                        # everything is now in place
                                        $scope.devices = dev_sel
                                        $scope.local_helper_obj = hs
                                        $scope.remote_helper_obj = temp_hs
                                        $scope.peer_list.enrich_device_tree($scope.device_tree, $scope.local_helper_obj, $scope.remote_helper_obj)
                                        console.log "done", $scope.local_helper_obj
                                )
                        )
                )
        )

    $scope.get_netdevice_boot_info = (nd) ->
        num_boot = nd.num_bootips
        if num_boot == 0
            return ""
        else if num_boot == 1
            return "(b)"
        else
            return "(#{num_boot})"

    $scope.no_objects_defined = (dev) ->
        return if (dev.netdevice_set.length == 0) then true else false

    $scope.get_route_peers = () ->
        return (entry for entry in $scope.nd_peers when entry.routing)

    $scope.set_scan_mode = (sm) ->
        $scope.scan_device.scan_mode = sm
        $scope.scan_device["scan_#{sm}_active"] = true
    $scope.has_com_capability = (dev, cc) ->
        return cc in dev.com_caps
    $scope.scan_device_network = (dev, event) ->
        $scope._current_dev = dev
        $scope.scan_device = dev
        network_type_names = []
        ip_dict = {}
        for ndev in dev.netdevice_set
            for ip in ndev.net_ip_set
                if ip.network of $scope.network_lut
                    network = $scope.network_lut[ip.network]
                    if network.network_type_identifier != "l" and not (network.netmask == "255.0.0.0" and network.network == "127.0.0.0")
                        if network.network_type_name not of ip_dict
                            ip_dict[network.network_type_name] = []
                            network_type_names.push(network.network_type_name)
                        ip_dict[network.network_type_name].push(ip.ip)
        for key, value of ip_dict
            ip_dict[key] = _.uniq(_.sortBy(value))
        network_type_names = _.sortBy(network_type_names)
        dev.ip_dict = ip_dict
        dev.network_type_names = network_type_names

        dev.manual_address = ""
        # set ip if there is only one
        if Object.keys(ip_dict).length == 1
            nw_ip_addresses = ip_dict[ Object.keys(ip_dict)[0] ]
            if nw_ip_addresses.length == 1
                dev.manual_address = nw_ip_addresses[0]

        dev.snmp_community = "public"
        if not dev.com_caps?
            # init com_caps array if not already set
            dev.com_caps = []
        dev.snmp_version = "2c"
        dev.remove_not_found = false
        dev.strict_mode = true
        dev.modify_peering = false
        dev.wmi_username = "Administrator"
        dev.wmi_password = ""
        dev.wmi_discard_disabled_interfaces = true
        dev.scan_base_active = false
        dev.scan_hm_active = false
        dev.scan_snmp_active = false
        if not $scope.no_objects_defined(dev) and $scope.has_com_capability(dev, "snmp")
            $scope.set_scan_mode("snmp")
        else
            $scope.set_scan_mode("base")
        $scope.scan_mixin.edit(dev, event).then(
            (mod_obj) ->
                true
        )
    $scope.fetch_device_network = () ->
        blockUI.start()
        _dev = $scope._current_dev
        _dev.scan_address = _dev.manual_address
        # intermediate state to trigger reload
        _dev.active_scan = "waiting"
        icswSimpleAjaxCall(
            url     : ICSW_URLS.DEVICE_SCAN_DEVICE_NETWORK
            data    :
                "dev" : angular.toJson($scope.scan_device)
        ).then((xml) ->
            blockUI.stop()
            $scope.scan_mixin.close_modal()
            $scope.update_scans()
        )
    $scope.update_scans = () ->
        Restangular.all(ICSW_URLS.NETWORK_GET_ACTIVE_SCANS.slice(1)).getList({"pks" : angular.toJson($scope.devsel_list)}).then(
            (data) ->
                any_scans_running = false
                for obj in data
                    dev = $scope.dev_lut[obj["pk"]]
                    dev.previous_scan = dev.active_scan
                    dev.active_scan = obj.active_scan
                    if dev.active_scan != dev.previous_scan
                        if not dev.active_scan
                            # scan finished
                            $q.all(
                                [
                                    Restangular.all(ICSW_URLS.REST_DEVICE_TREE_LIST.slice(1)).getList({"with_network" : true, "pks" : angular.toJson([dev.idx]), "olp" : "backbone.device.change_network"})
                                    Restangular.all(ICSW_URLS.REST_PEER_INFORMATION_LIST.slice(1)).getList(),
                                    Restangular.all(ICSW_URLS.REST_NETWORK_LIST.slice(1)).getList(),
                                ]
                            ).then((data) ->
                                $scope.networks = data[2]
                                $scope.peers = data[1]
                                $scope.network_lut = icswTools.build_lut($scope.networks)
                                $scope.update_device(data[0][0])
                            )
                    if obj.active_scan
                        any_scans_running = true
                if any_scans_running
                    $timeout($scope.update_scans, 5000)
        )
    $scope.update_device = (new_dev) ->
        cur_devs = []
        for dev in $scope.devices
            if dev.idx == new_dev.idx
                cur_devs.push(new_dev)
            else
                cur_devs.push(dev)
        $scope.devices = cur_devs
        $scope.build_luts()

    $scope.create_netip_ok = (obj) ->
        if $scope.network_tree.nw_list.length and obj.netdevice_set.length
            return true
        else
            return false

    $scope.create_peer_ok = (obj) ->
        if obj.netdevice_set.length
            return true
        else
            return false

    $scope.edit_boot_settings = (obj, event) ->
        $scope.boot_edit.edit(obj, event).then(
            (mod_dev) ->
                true
        )
    $scope.check_for_peer_change = (ndev) ->
        # at first remove from list
        $scope.nd_peers = (entry for entry in $scope.nd_peers when entry.idx != ndev.idx)
        if ndev.routing
            _cd = $scope.dev_lut[ndev.device]
            ndev.fqdn = _cd.full_name
            ndev.device_name = _cd.name
            ndev.device_group_name = _cd.device_group_name
            $scope.nd_peers.push(ndev)
        $scope.build_luts()

    $scope.get_peer_src_info = (_edit_obj) ->
        if $scope.source_is_local
            _nd = $scope.nd_lut[$scope._edit_obj.s_netdevice]
        else
            _nd = $scope.nd_lut[$scope._edit_obj.d_netdevice]
        if _nd
            return _nd.devname + " on " + $scope.dev_lut[_nd.device].name
        else
            return "???"

    $scope.delete_peer_information = (ndip_obj, event) ->
        # find device / netdevice
        peer = ndip_obj.peer
        $scope.peer_edit.delete_list = undefined
        $scope.peer_edit.delete_obj(peer).then(
            (res) ->
                if res
                    if peer.s_netdevice of $scope.nd_lut
                        $scope.nd_lut[peer.s_netdevice].peers = (entry for entry in $scope.nd_lut[peer.s_netdevice].peers when entry.peer.idx != peer.idx)
                    if peer.d_netdevice of $scope.nd_lut
                        $scope.nd_lut[peer.d_netdevice].peers = (entry for entry in $scope.nd_lut[peer.d_netdevice].peers when entry.peer.idx != peer.idx)
                    delete $scope.peer_lut[peer.idx]
        )
    $scope.create_peer_information_dev = (obj, event) ->
        $scope._current_dev = obj
        $scope.source_is_local = true
        $scope.peer_edit.create_list = undefined
        $scope.peer_edit.new_object = (scope) ->
            return {
                "s_netdevice" : (entry.idx for entry in obj.netdevice_set)[0]
                "penalty" : 1
            }
        $scope.create_peer_information(event)
    $scope.create_peer_information_nd = (obj, event) ->
        $scope._current_dev = $scope.dev_lut[obj.device]
        $scope.source_is_local = true
        $scope.peer_edit.create_list = undefined
        $scope.peer_edit.new_object = (scope) ->
            return {
                "s_netdevice" : obj.idx
                "penalty" : 1
            }
        $scope.create_peer_information(event)
    $scope.create_peer_information = (event) ->
        $scope.peer_edit.create(event).then(
            (peer) ->
                if peer != false
                    $scope.peer_lut[peer.idx] = peer
                    if peer.s_netdevice of $scope.nd_lut
                        $scope.nd_lut[peer.s_netdevice].peers.push({"peer" : peer, "netdevice" : peer.s_netdevice, "target" : peer.d_netdevice})
                    if peer.d_netdevice of $scope.nd_lut and peer.s_netdevice != peer.d_netdevice
                        $scope.nd_lut[peer.d_netdevice].peers.push({"peer" : peer, "netdevice" : peer.d_netdevice, "target" : peer.s_netdevice})
        )
    $scope.ethtool_options = (ndip_obj, type) ->
        if type == "a"
            eth_opt = ndip_obj.ethtool_options & 3
            return {
                0: "default"
                1: "on"
                2: "off"
            }[eth_opt]
        else if type == "d"
            eth_opt = (ndip_obj.ethtool_options >> 2) & 3
            return {
                0: "default"
                1: "on"
                2: "off"
            }[eth_opt]
        else if type == "s"
            eth_opt = (ndip_obj.ethtool_options >> 4) & 7
            return {
                0: "default"
                1: "10 MBit"
                2: "100 MBit"
                3: "1 GBit"
                4: "10 GBit"
            }[eth_opt]

    $scope.get_peer_target = (ndip_obj) ->
        # FIXME
        return "peer_target"
        if ndip_obj.target of $scope.nd_lut
            peer = $scope.nd_lut[ndip_obj.target]
            _dev = $scope.dev_lut[peer.device]
            if _dev.domain_tree_node of $scope.dtn_lut
                _domain = "." + $scope.dtn_lut[_dev.domain_tree_node].full_name
            else
                _domain = ""
            return "#{peer.devname} (#{peer.penalty}) on " + String(_dev.name) + _domain
        else
            if ndip_obj.target of $scope.nd_peer_lut
                peer = $scope.nd_peer_lut[ndip_obj.target]
                return "#{peer.devname} (#{peer.penalty}) on #{peer.fqdn}"
            else
                return "N/A (disabled device ?)"

    $scope.get_peer_type = (peer) ->
        _local_devs = (dev.idx for dev in $scope.devices)
        r_list = []
        for c_id in [peer.s_device, peer.d_device]
            r_list.push(if (c_id in _local_devs) then "sel" else "N/S")
        return r_list.join(", ")

    $scope.toggle_copy_com = () ->
        $scope.copy_coms = !$scope.copy_coms
    $scope.copy_com_class = () ->
        if $scope.copy_coms
            return "btn btn-sm btn-success"
        else
            return "btn btn-sm btn-default"
    $scope.copy_com_value = () ->
        if $scope.copy_coms
            return "Copy Coms and Schemes"
        else
            return "start with empty Coms and Schemes"

    $scope.copy_network = (src_obj, event) ->
        icswToolsSimpleModalService("Overwrite all networks with the one from #{src_obj.full_name} ?").then(
            () ->
                blockUI.start()
                icswSimpleAjaxCall(
                    url     : ICSW_URLS.NETWORK_COPY_NETWORK
                    data    : {
                        "source_dev" : src_obj.idx
                        "copy_coms"  : $scope.copy_coms
                        "all_devs"   : angular.toJson($scope.devsel_list)
                    }
                ).then((xml) ->
                    blockUI.stop()
                    $scope.reload()
                )
        )

    $scope.edit_peer = (cur_obj, obj_type, $event, create_mode) ->
        # cur_obj is device, netdevice of ip, obj_type is 'dev', 'nd' or 'ip'
        # create or edit
        if create_mode
            edit_obj = {
                "ip" : "0.0.0.0"
                "_changed_by_user_": false
                "network" : $scope.network_tree.nw_list[0].idx
                # take first domain tree node
                "domain_tree_node" : $scope.domain_tree.list[0].idx
            }
            if obj_type == "dev"
                title = "Create new IP on device '#{cur_obj.full_name}'"
                edit_obj.netdevice = cur_obj.netdevice_set[0].idx
                dev = cur_obj
            else if obj_type == "nd"
                title = "Create new IP on netdevice '#{cur_obj.devname}'"
                edit_obj.netdevice = cur_obj.idx
                dev = $scope.device_tree.all_lut[cur_obj.device]
        else
            edit_obj = cur_obj
            dbu = new icswPeerInformationBackup()
            dbu.create_backup(edit_obj)
            title = "Edit Peer Information"
            peer_info = ""
            # build peering lists


        # which template to use
        template_name = "icsw.peer.form"
        sub_scope = $scope.$new(false)
        sub_scope.edit_obj = edit_obj
        # create link
        sub_scope.source_helper = $scope.peer_list.build_peer_helper($scope.device_tree, cur_obj, $scope.local_helper_obj, $scope.remote_helper_obj, "s")
        sub_scope.dest_helper = $scope.peer_list.build_peer_helper($scope.device_tree, cur_obj, $scope.local_helper_obj, $scope.remote_helper_obj, "d")
        sub_scope.create_mode = create_mode

        # add functions

        # init form
        icswComplexModalService(
            {
                message: $compile($templateCache.get(template_name))(sub_scope)
                ok_label: if create_mode then "Create" else "Modify"
                title: title
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "", 0)
                        d.reject("form not valid")
                    else
                        nd = $scope.local_helper_obj.netdevice_lut[sub_scope.edit_obj.netdevice]
                        if create_mode
                            $scope.device_tree.create_netip(sub_scope.edit_obj, nd).then(
                                (ok) ->
                                    d.resolve("netip created")
                                (notok) ->
                                    d.reject("netip not created")
                            )
                        else
                            Restangular.restangularizeElement(null, sub_scope.edit_obj, ICSW_URLS.REST_PEER_INFORMATION_DETAIL.slice(1).slice(0, -2))
                            sub_scope.edit_obj.put().then(
                                (data) ->
                                    # ToDo, FIXME, handle change (test?), move to DeviceTreeService
                                    # icswTools.handle_reset(data, cur_f, $scope.edit_obj.idx)
                                    console.log "data", data
                                    d.resolve("save")
                                (reject) ->
                                    # ToDo, FIXME, handle rest (test?)
                                    # icswTools.handle_reset(resp.data, cur_f, $scope.edit_obj.idx)
                                    # two possibilites: restore and continue or reject, right now we use the second path
                                    # dbu.restore_backup(obj)
                                    d.reject("not saved")
                            )
                    return d.promise
                cancel_callback: (modal) ->
                    if not create_mode
                        dbu.restore_backup(edit_obj)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                console.log "Peer requester closed, trigger redraw"
                sub_scope.$destroy()
                # trigger rebuild of lists
                # $rootScope.$emit(ICSW_SIGNALS("ICSW_FORCE_TREE_FILTER"))
                # recreate helper luts
                $scope.peer_list.build_luts()
                $scope.peer_list.enrich_device_tree($scope.device_tree, $scope.local_helper_obj, $scope.remote_helper_obj)
                $scope.device_tree.build_helper_luts(
                    ["network_info"]
                    $scope.local_helper_obj
                )
        )

    $scope.edit_netip = (cur_obj, obj_type, $event, create_mode) ->
        # cur_obj is device, netdevice of ip, obj_type is 'dev', 'nd' or 'ip'
        # create or edit
        if create_mode
            edit_obj = {
                "ip" : "0.0.0.0"
                "_changed_by_user_": false
                "network" : $scope.network_tree.nw_list[0].idx
                # take first domain tree node
                "domain_tree_node" : $scope.domain_tree.list[0].idx
            }
            if obj_type == "dev"
                title = "Create new IP on device '#{cur_obj.full_name}'"
                edit_obj.netdevice = cur_obj.netdevice_set[0].idx
                dev = cur_obj
            else if obj_type == "nd"
                title = "Create new IP on netdevice '#{cur_obj.devname}'"
                edit_obj.netdevice = cur_obj.idx
                dev = $scope.device_tree.all_lut[cur_obj.device]
        else
            edit_obj = cur_obj
            dbu = new icswNetworkIPBackup()
            dbu.create_backup(edit_obj)
            title = "Edit IP #{edit_obj.ip}"
            dev = $scope.device_tree.all_lut[$scope.local_helper_obj.netdevice_lut[edit_obj.netdevice].device]

        # which template to use
        template_name = "icsw.net.ip.form"
        sub_scope = $scope.$new(false)
        sub_scope.edit_obj = edit_obj
        sub_scope.device = dev
        sub_scope.create_mode = create_mode

        # add functions

        sub_scope.get_free_ip = (obj) ->
            blockUI.start("requesting free IP...")
            icswSimpleAjaxCall(
                url: ICSW_URLS.NETWORK_GET_FREE_IP
                data: {
                    "netip": angular.toJson(obj)
                }
                dataType: "json"
            ).then(
                (json) ->
                    blockUI.stop()
                    if json["ip"]?
                        obj.ip = json["ip"]
            )

        sub_scope.network_changed = (obj) ->
            if obj.ip == "0.0.0.0" or not obj._changed_by_user_
                sub_scope.get_free_ip(obj)
            if not obj._changed_by_user_
                _nw = $scope.network_tree.nw_lut[obj.network]
                if _nw.preferred_domain_tree_node
                    obj.domain_tree_node = _nw.preferred_domain_tree_node

        # init form
        icswComplexModalService(
            {
                message: $compile($templateCache.get(template_name))(sub_scope)
                ok_label: if create_mode then "Create" else "Modify"
                title: title
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "", 0)
                        d.reject("form not valid")
                    else
                        nd = $scope.local_helper_obj.netdevice_lut[sub_scope.edit_obj.netdevice]
                        if create_mode
                            $scope.device_tree.create_netip(sub_scope.edit_obj, nd).then(
                                (ok) ->
                                    d.resolve("netip created")
                                (notok) ->
                                    d.reject("netip not created")
                            )
                        else
                            Restangular.restangularizeElement(null, sub_scope.edit_obj, ICSW_URLS.REST_NET_IP_DETAIL.slice(1).slice(0, -2))
                            sub_scope.edit_obj.put().then(
                                (data) ->
                                    # ToDo, FIXME, handle change (test?), move to DeviceTreeService
                                    # icswTools.handle_reset(data, cur_f, $scope.edit_obj.idx)
                                    console.log "data", data
                                    d.resolve("save")
                                (reject) ->
                                    # ToDo, FIXME, handle rest (test?)
                                    # icswTools.handle_reset(resp.data, cur_f, $scope.edit_obj.idx)
                                    # two possibilites: restore and continue or reject, right now we use the second path
                                    # dbu.restore_backup(obj)
                                    d.reject("not saved")
                            )
                    return d.promise
                cancel_callback: (modal) ->
                    if not create_mode
                        dbu.restore_backup(edit_obj)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                console.log "NetIP requester closed, trigger redraw"
                sub_scope.$destroy()
                # trigger rebuild of lists
                # $rootScope.$emit(ICSW_SIGNALS("ICSW_FORCE_TREE_FILTER"))
                # recreate helper luts
                $scope.device_tree.build_helper_luts(
                    ["network_info"]
                    $scope.local_helper_obj
                )
        )

    $scope.delete_netip = (ip, event) ->
        icswToolsSimpleModalService("Really delete IP #{ip.ip} ?").then(
            () =>
                nd = $scope.local_helper_obj.netdevice_lut[ip.netdevice]
                $scope.device_tree.delete_netip(ip, nd).then(
                    () ->
                        $scope.device_tree.build_helper_luts(
                            ["network_info"]
                            $scope.local_helper_obj
                        )
                )
        )

    $scope.edit_netdevice = (nd_obj, $event, create_mode) ->
        # create or edit
        if create_mode
            # nd_obj is the parent device
            new_type = $scope.network_tree.nw_device_type_list[0]
            mac_bytes = new_type.mac_bytes
            default_ms = ("00" for idx in [0..mac_bytes]).join(":")
            edit_obj = {
                "device": nd_obj.idx
                "devname" : "eth0"
                "enabled" : true
                "netdevice_speed" : (entry.idx for entry in $scope.network_tree.nw_speed_list when entry.speed_bps == 1000000000 and entry.full_duplex)[0]
                "ignore_netdevice_speed": false
                "desired_status": "i"
                "penalty" : 1
                "net_ip_set" : []
                "ethtool_options" : 0
                "ethtool_autoneg" : 0
                "ethtool_speed" : 0
                "ethtool_duplex" : 0
                "mtu": 1500
                "macaddr": default_ms
                "fake_macaddr": default_ms
                # dummy value
                "network_device_type" : new_type.idx
            }
            title = "Create new netdevice on '#{nd_obj.full_name}'"
        else
            edit_obj = nd_obj
            dbu = new icswNetworkDeviceBackup()
            dbu.create_backup(edit_obj)
            title = "Edit netdevice #{edit_obj.devname}"
        # which template to use
        template_name = "icsw.netdevice.form"
        sub_scope = $scope.$new(false)
        sub_scope.edit_obj = edit_obj

        # set helper functions and arrays
        sub_scope.desired_stati = [
            {"short": "i", "info_string": "ignore"}
            {"short": "u", "info_string": "must be up"}
            {"short": "d", "info_string": "must be down"}
        ]
        sub_scope.update_ethtool = (ndip_obj) ->
            ndip_obj.ethtool_options = (parseInt(ndip_obj.ethtool_speed) << 4) | (parseInt(ndip_obj.ethtool_duplex) << 2) < (parseInt(ndip_obj.ethtool_autoneg))

        sub_scope.get_vlan_masters = (cur_nd) ->
            _cd = $scope.device_tree.all_lut[cur_nd.device]
            return (entry for entry in _cd.netdevice_set when entry.idx != cur_nd.idx and not entry.is_bridge and not entry.is_bond)

        sub_scope.get_bridge_masters = (cur_nd) ->
            _cd = $scope.device_tree.all_lut[cur_nd.device]
            return (entry for entry in _cd.netdevice_set when entry.idx != cur_nd.idx and entry.is_bridge)

        sub_scope.get_bond_masters = (cur_nd) ->
            _cd = $scope.device_tree.all_lut[cur_nd.device]
            return (entry for entry in _cd.netdevice_set when entry.idx != cur_nd.idx and entry.is_bond)

        sub_scope.has_bridge_slaves = (nd) ->
            dev = $scope.device_tree.all_lut[nd.device]
            if nd.is_bridge
                return if (sub_nd.devname for sub_nd in dev.netdevice_set when sub_nd.bridge_device == nd.idx).length then true else false
            else
                return false

        sub_scope.has_bond_slaves = (nd) ->
            dev = $scope.device_tree.all_lut[nd.device]
            if nd.is_bond
                return if (sub_nd.devname for sub_nd in dev.netdevice_set when sub_nd.bond_master == nd.idx).length then true else false
            else
                return false

        # init form
        icswComplexModalService(
            {
                message: $compile($templateCache.get(template_name))(sub_scope)
                ok_label: if create_mode then "Create" else "Modify"
                title: title
                ok_callback: (modal) ->
                    d = $q.defer()
                    if sub_scope.form_data.$invalid
                        toaster.pop("warning", "form validation problem", "", 0)
                        d.reject("form not valid")
                    else
                        if create_mode
                            $scope.device_tree.create_netdevice(sub_scope.edit_obj).then(
                                (ok) ->
                                    d.resolve("netdevice created")
                                (notok) ->
                                    d.reject("netdevice not created")
                            )
                        else
                            Restangular.restangularizeElement(null, sub_scope.edit_obj, ICSW_URLS.REST_NETDEVICE_DETAIL.slice(1).slice(0, -2))
                            sub_scope.edit_obj.put().then(
                                (data) ->
                                    # ToDo, FIXME, handle change (test?), move to DeviceTreeService
                                    # icswTools.handle_reset(data, cur_f, $scope.edit_obj.idx)
                                    console.log "data", data
                                    d.resolve("save")
                                (reject) ->
                                    # ToDo, FIXME, handle rest (test?)
                                    # icswTools.handle_reset(resp.data, cur_f, $scope.edit_obj.idx)
                                    # two possibilites: restore and continue or reject, right now we use the second path
                                    # dbu.restore_backup(obj)
                                    d.reject("not saved")
                            )
                    return d.promise
                cancel_callback: (modal) ->
                    if not create_mode
                        dbu.restore_backup(edit_obj)
                    d = $q.defer()
                    d.resolve("cancel")
                    return d.promise
            }
        ).then(
            (fin) ->
                console.log "NetDevice requester closed, trigger redraw"
                sub_scope.$destroy()
                # trigger rebuild of lists
                # $rootScope.$emit(ICSW_SIGNALS("ICSW_FORCE_TREE_FILTER"))
                # recreate helper luts
                $scope.device_tree.build_helper_luts(
                    ["network_info"]
                    $scope.local_helper_obj
                )
        )

    $scope.delete_netdevice = (nd, event) ->
        icswToolsSimpleModalService("Really delete netdevice #{nd.devname} ?").then(
            () ->
                $scope.device_tree.delete_netdevice(nd).then(
                    () ->
                        $scope.device_tree.build_helper_luts(
                            ["network_info"]
                            $scope.local_helper_obj
                        )
                )
        )

]).controller("icswDeviceNetworkNetdeviceRowCtrl", ["$scope", ($scope) ->
    $scope.get_num_peers_nd = (nd) ->
        if nd.idx of $scope.peer_list.nd_lut
            return $scope.peer_list.nd_lut[nd.idx].length
        else
            return 0

    $scope.get_nd_flags = (nd) ->
        _f = []
        if nd.routing
            _f.push("extrouting")
        if nd.inter_device_routing
            _f.push("introuting")
        if !nd.enabled
            _f.push("disabled")
        return _f.join(", ")

    $scope.get_netdevice_name = (nd) ->
        nd_name = nd.devname
        if nd.description
            nd_name = "#{nd_name} (#{nd.description})"
        if nd.vlan_id
            nd_name = "#{nd_name}, VLAN #{nd.vlan_id}"
            if nd.master_device
                nd_name = "#{nd_name} on " + String($scope.local_helper_obj.netdevice_lut[nd.master_device].devname)
        return nd_name

    $scope.get_bond_info = (nd) ->
        dev = $scope.device_tree.all_lut[nd.device]
        if nd.is_bond
            slaves = (sub_nd.devname for sub_nd in dev.netdevice_set when sub_nd.bond_master == nd.idx)
            if slaves.length
                return "master (" + slaves.join(", ") + ")"
            else
                return "master"
        else if nd.bond_master
            return "slave (" + $scope.local_helper_obj.netdevice_lut[nd.bond_master].devname + ")"
        else
            return "-"

    $scope.build_netdevice_tooltip = (ndev) ->
        device = $scope.device_tree.all_lut[ndev.device]
        info_f = [
            "<div class='text-left'>",
            "device: #{device.full_name}<br>"
        ]
        if ndev.snmp_idx
            info_f.push(
                "SNMP: yes (#{ndev.snmp_idx})<br>"
            )
        else
            info_f.push(
                "SNMP: no<br>"
            )
        info_f.push("enabled: " + if ndev.enabled then "yes" else "no")
        info_f.push("<hr>")
        info_f.push("driver: #{ndev.driver}<br>")
        info_f.push("driver options: #{ndev.driver_options}<br>")
        info_f.push("fake MACAddress: #{ndev.fake_macaddr}<br>")
        info_f.push("force write DHCP: " + if ndev.dhcp_device then "yes" else "no")
        info_f.push("<hr>")
        info_f.push("Autonegotiation: " + $scope.ethtool_options(ndev, "a") + "<br>")
        info_f.push("Duplex: " + $scope.ethtool_options(ndev, "a") +  "<br>")
        info_f.push("Speed: " + $scope.ethtool_options(ndev, "a") + "<br>")
        info_f.push("<hr>")
        info_f.push("Monitoring: " + $scope.get_netdevice_speed(ndev))
        info_f.push("</div>")
        return info_f.join("")

    $scope.get_bridge_info = (nd) ->
        dev = $scope.device_tree.all_lut[nd.device]
        if nd.is_bridge
            slaves = (sub_nd.devname for sub_nd in dev.netdevice_set when sub_nd.bridge_device == nd.idx)
            if slaves.length
                return "bridge" + " (" + slaves.join(", ") + ")"
            else
                return "bridge"
        else if nd.bridge_device
            return "slave (" + $scope.local_helper_obj.netdevice_lut[nd.bridge_device].devname + ")"
        else
            return "-"

    $scope.get_network_type = (ndip_obj) ->
        if ndip_obj.snmp_network_type
            return $scope.network_tree.nw_snmp_type_lut[ndip_obj.snmp_network_type].if_label
        else
            return $scope.network_tree.nw_device_type_lut[ndip_obj.network_device_type].info_string

    $scope.get_snmp_ao_status = (ndip_obj) ->
        as = ndip_obj.snmp_admin_status
        os = ndip_obj.snmp_oper_status
        if as == 0 and os == 0
            return ""
        else if as == 1 and os == 1
            return "up"
        else
            _r_f = []
            _r_f.push(
                {
                    1: "up"
                    2: "down"
                    3: "testing"
                }[as]
            )
            _r_f.push(
                {
                    1: "up"
                    2: "down"
                    3: "testing"
                    4: "unknown"
                    5: "dormant"
                    6: "notpresent"
                    7: "lowerLayerDown"
                }[os]
            )
            return _r_f.join(", ")

    $scope.get_snmp_ao_status_class = (ndip_obj) ->
        as = ndip_obj.snmp_admin_status
        os = ndip_obj.snmp_oper_status
        if as == 0 and os == 0
            return ""
        else if as == 1 and os == 1
            return "success text-center"
        else
            return "warning text-center"

    $scope.get_desired_status = (ndip_obj) ->
        return {
            "i": "ignore"
            "u": "up"
            "d" : "down"
        }[ndip_obj.desired_status]

    $scope.get_netdevice_speed = (ndip_obj) ->
        sp = ndip_obj.netdevice_speed
        if sp of $scope.network_tree.nw_speed_lut
            return $scope.network_tree.nw_speed_lut[sp].info_string
        else
            return "-"

]).directive("icswDeviceNetworkNetdeviceRow", ["$templateCache", "$compile", ($templateCache, $compile) ->
    return {
        restrict : "EA"
        template: $templateCache.get("icsw.device.network.netdevice.row")
        scope: false
        controller: "icswDeviceNetworkNetdeviceRowCtrl"
    }
]).directive("icswDeviceComCapabilities", ["$templateCache", "$compile", "icswCachingCall", "ICSW_URLS", ($templateCache, $compile, icswCachingCall, ICSW_URLS) ->
    return {
        restrict : "EA"
        template: $templateCache.get("icsw.device.com.capabilities")
        scope:
            device: "=device"
            detail: "=detail"
        link: (scope, el, attrs) ->
            console.log scope.device
            scope.com_class = () ->
                if scope.pending
                    return "btn-warning"
                else if scope.com_caps.length
                    return "btn-success"
                else
                    return "btn-danger"
            scope.com_caps = []
            scope.$watch("device.active_scan", (new_val) ->
                if new_val == "base"
                    el.find("span.ladda-label").text("...")
                    scope.pending = true
                else
                    update_com_cap()
            )
            update_com_cap = () ->
                el.find("span.ladda-label").text("...")
                scope.pending = true
                icswCachingCall.fetch(scope.$id, ICSW_URLS.REST_DEVICE_COM_CAPABILITIES, {"devices": "<PKS>"}, [scope.device.idx]).then(
                    (data) ->
                        console.log "update_com_cap ***", data
                        scope.com_caps = if data[0]? then data[0] else []
                        scope.pending = false
                        if scope.com_caps.length
                            scope.device.com_caps = (_entry.matchcode for _entry in scope.com_caps)
                            scope.device.com_cap_names = (_entry.name for _entry in scope.com_caps)
                            if scope.detail?
                                el.find("span.ladda-label").text(scope.device.com_cap_names.join(", "))
                            else
                                el.find("span.ladda-label").text(scope.device.com_caps.join(", "))
                        else
                            el.find("span.ladda-label").text("N/A")
                )
            update_com_cap()
    }
]).controller("icswDeviceNetworkIpRowCtrl", ["$scope", ($scope) ->
    $scope.get_netdevice_name_from_ip = (nd) ->
        nd = $scope.local_helper_obj.netdevice_lut[nd.netdevice]
        nd_name = nd.devname
        if nd.description
            nd_name = "#{nd_name} (#{nd.description})"
        if nd.vlan_id
            nd_name = "#{nd_name}, VLAN #{nd.vlan_id}"
            if nd.master_device
                nd_name = "#{nd_name} on " + String($scope.local_helper_obj.netdevice_lut[nd.master_device].devname)
        return nd_name

    $scope.get_devname_from_ip = (ip_obj) ->
        return $scope.device_tree.all_lut[$scope.local_helper_obj.netdevice_lut[ip_obj.netdevice].device].full_name

    $scope.get_network_name_from_ip = (ip_obj) ->
        return $scope.network_tree.nw_lut[ip_obj.network].info_string

    $scope.get_domain_tree_name_from_ip = (ip_obj) ->
        return $scope.domain_tree.lut[ip_obj.domain_tree_node].tree_info
]).directive("icswDeviceNetworkIpRow", ["$templateCache", "$compile", ($templateCache, $compile) ->
    return {
        restrict : "EA"
        template: $templateCache.get("icsw.device.network.ip.row")
        scope: false
        controller: "icswDeviceNetworkIpRowCtrl"
    }
]).controller("icswDeviceNetworkDeviceRowCtrl", ["$scope", ($scope) ->

    $scope.get_bootdevice_info_class = (obj) ->
        num_bootips = $scope.get_num_bootips(obj)
        if obj.dhcp_error
            return "btn-danger"
        else
            if num_bootips == 0
                return "btn-warning"
            else if num_bootips == 1
                return "btn-success"
            else
                return "btn-danger"

    $scope.get_num_bootips = (obj) ->
        return obj.$$_enrichment_info.num_boot_ips

    $scope.get_boot_value = (obj) ->
        num_bootips = $scope.get_num_bootips(obj)
        r_val = "#{num_bootips} IPs (" + (if obj.dhcp_write then "write" else "no write") + " / " + (if obj.dhcp_mac then "greedy" else "not greedy") + ")"
        if obj.dhcp_error
            r_val = "#{r_val}, #{obj.dhcp_error}"
        if obj.dhcp_write != obj.dhcp_written
            r_val = "#{r_val}, DHCP is " + (if obj.dhcp_written then "" else "not") + " written"
        return r_val

    $scope.build_device_tooltip = (dev) ->
        group = $scope.device_tree.group_lut[dev.device_group]
        return "<div class='text-left'>Group: #{group.name}<br>Comment: #{dev.comment}<br></div>"

]).directive("icswDeviceNetworkDeviceRow", ["$templateCache", "$compile", ($templateCache, $compile) ->
    return {
        restrict : "EA"
        template: $templateCache.get("icsw.device.network.device.row")
        scope: false
        controller: "icswDeviceNetworkDeviceRowCtrl"
    }
]).controller("icswDeviceNetworkPeerRowCtrl", ["$scope", ($scope) ->
    get_netdevice_from_peer = (peer_obj, ptype) ->
        if peer_obj["$$#{ptype}_type"] == "l"
            ho = $scope.local_helper_obj
            o_ho = $scope.remote_helper_obj
        else
            ho = $scope.remote_helper_obj
            o_ho = $scope.local_helper_obj
        _pk = peer_obj["#{ptype}_netdevice"]
        if _pk of ho.netdevice_lut
            return ho.netdevice_lut[_pk]
        else
            # undefined, may happen during edit
            # use the other helper object
            return o_ho.netdevice_lut[_pk]

    $scope.get_peer_class = (peer_obj, ptype) ->
        nd = get_netdevice_from_peer(peer_obj, ptype)
        if nd.routing
            return "warning"
        else
            return ""

    $scope.get_devname_from_peer = (peer_obj, ptype) ->
        nd = get_netdevice_from_peer(peer_obj, ptype)
        dev = $scope.device_tree.all_lut[nd.device]
        return dev.full_name

    $scope.get_netdevice_name_from_peer = (peer_obj, ptype) ->
        nd = get_netdevice_from_peer(peer_obj, ptype)
        return "#{nd.devname} (#{nd.penalty})"

    $scope.get_ip_list_from_peer = (peer_obj, ptype) ->
        nd = get_netdevice_from_peer(peer_obj, ptype)
        ip_list = (ip.ip for ip in nd.net_ip_set)
        if ip_list.length
            return ip_list.join(", ")
        else
            return "---"

    $scope.get_peer_cost = (peer_obj) ->
        s_nd = get_netdevice_from_peer(peer_obj, "s")
        d_nd = get_netdevice_from_peer(peer_obj, "d")
        return s_nd.penalty + peer_obj.penalty + d_nd.penalty

]).directive("icswDeviceNetworkPeerRow", ["$templateCache", "$compile", ($templateCache, $compile) ->
    return {
        restrict : "EA"
        template: $templateCache.get("icsw.device.network.peer.row")
        scope: false
        controller: "icswDeviceNetworkPeerRowCtrl"
    }
]).directive("icswDeviceNetworkOverview", ["$templateCache", ($templateCache) ->
    return {
        scope: true
        restrict : "EA"
        link: (scope, el, attrs) ->
            if attrs["showCopyButton"]?
                scope.show_copy_button = true
        template : $templateCache.get("icsw.device.network.overview")
        controller: "icswDeviceNetworkCtrl"
    }
]).directive("icswDeviceNetworkTotal", ["$templateCache", "$rootScope", "ICSW_SIGNALS", ($templateCache, $rootScope, ICSW_SIGNALS) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.device.network.total")
        link: (scope, element, attrs) ->
            scope.select_tab = (name) ->
                $rootScope.$emit(ICSW_SIGNALS("ICSW_NETWORK_TAB_SELECTED"), name)
    }
]).controller("icswDeviceNetworkClusterCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q", "icswAcessLevelService", "ICSW_URLS", "icswSimpleAjaxCall",
    "blockUI", "ICSW_SIGNALS", "$rootScope", "icswComplexModalService",
(
    $scope, $compile, $filter, $templateCache, Restangular, $q, icswAcessLevelService, ICSW_URLS, icswSimpleAjaxCall,
    blockUI, ICSW_SIGNALS, $rootScope, icswComplexModalService
) ->
    icswAcessLevelService.install($scope)
    # msgbus.receive("devicelist", $scope, (name, args) ->
    #     $scope.devices = args[1]
    # )
    $scope.clusters = []
    $scope.devices = []

    $scope.new_devsel = (_dev_sel, _devg_sel) ->
        $scope.devices = _dev_sel

    $scope.reload = () ->
        blockUI.start("loading NetworkClusters")
        icswSimpleAjaxCall(
            url      : ICSW_URLS.NETWORK_GET_CLUSTERS
            dataType : "json"
        ).then(
            (json) ->
                blockUI.stop()
                $scope.clusters = json
        )

    $scope.is_selected = (cluster) ->
        _sel = _.intersection(cluster.device_pks, $scope.devices)
        return if _sel.length then "yes (#{_sel.length})" else "no"

    $scope.show_cluster = (cluster) ->
        Restangular.all(ICSW_URLS.REST_DEVICE_TREE_LIST.slice(1)).getList({"pks" : angular.toJson(cluster.device_pks), "ignore_meta_devices" : true}).then(
            (data) ->
                child_scope = $scope.$new(false)
                child_scope.cluster = cluster
                child_scope.devices = []
                child_scope.devices = data
                icswComplexModalService(
                    {
                        message: $compile($templateCache.get("icsw.device.network.cluster.info"))(child_scope)
                        title: "Devices in cluster (#{child_scope.cluster.device_pks.length})"
                        # css_class: "modal-wide"
                        ok_label: "Close"
                        closable: true
                        ok_callback: (modal) ->
                            d = $q.defer()
                            d.resolve("ok")
                            return d.promise
                    }
                ).then(
                    (fin) ->
                        console.log "finish"
                        child_scope.$destroy()
                )
        )

    $rootScope.$on(ICSW_SIGNALS("ICSW_NETWORK_TAB_SELECTED"), (event, name) ->
        if name == "cluster"
            $scope.reload()
    )
]).controller("icswDeviceNetworkGraphCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q", "$uibModal", "icswAcessLevelService", "icswLivestatusFilterFactory",
    ($scope, $compile, $filter, $templateCache, Restangular, $q, $uibModal, icswAcessLevelService, icswLivestatusFilterFactory) ->
        icswAcessLevelService.install($scope)
        $scope.graph_sel = "sel"
        $scope.show_livestatus = false
        $scope.devices = []
        $scope.new_devsel = (_dev_sel) ->
            $scope.devices = _dev_sel
        $scope.ls_filter = new icswLivestatusFilterFactory()
]).directive("icswDeviceNetworkNodeTransform", [() ->
    return {
        restrict: "A"
        link: (scope, element, attrs) ->
            scope.$watch(attrs["icswDeviceNetworkNodeTransform"], (transform_node) ->
                scope.$watch(attrs["redraw"], (new_val) ->
                    if transform_node.x?
                        element.attr("transform", "translate(#{transform_node.x},#{transform_node.y})")
                )
            )
    }
]).directive("icswDeviceNetworkNodeDblClick", ["DeviceOverviewService", (DeviceOverviewService) ->
    return {
        restrict: "A"
        link: (scope, element, attrs) ->
            scope.click_node = null
            scope.double_click = (event) ->
                # beef up node structure
                if scope.click_node?
                    scope.click_node.idx = scope.click_node.id
                    #scope.click_node.device_type_identifier = "D"
                    DeviceOverviewService.NewOverview(event, [scope.click_node])
            scope.$watch(attrs["icswDeviceNetworkNodeDblClick"], (click_node) ->
                scope.click_node = click_node
            )
    }
]).directive("icswDeviceNetworkHostLivestatus", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.network.host.livestatus")
        scope:
             devicepk: "=devicepk"
             ls_filter: "=lsFilter"
        replace: true
    }
]).directive("icswDeviceNetworkHostNode", ["dragging", "$templateCache", (dragging, $templateCache) ->
    return {
        restrict : "EA"
        templateNamespace: "svg"
        replace: true
        scope:
            node: "=node"
            redraw: "=redraw"
        template: $templateCache.get("icsw.device.network.host.node")
        link : (scope, element, attrs) ->
            scope.stroke_width = 1
            scope.focus = true
            scope.mousedown = false
            scope.$watch("node", (new_val) ->
                scope.node = new_val
                scope.fill_color = "white"
                scope.stroke_width = Math.max(Math.min(new_val.num_nds, 3), 1)
                scope.stroke_color = if new_val.num_nds then "grey" else "red"
            )
            scope.mouse_click = () ->
                if scope.node.ignore_click
                    scope.node.ignore_click = false
                else
                    scope.node.fixed = !scope.node.fixed
                    scope.fill_color = if scope.node.fixed then "red" else "white"
            scope.mouse_enter = () ->
                scope.focus = true
                scope.stroke_width++
            scope.mouse_leave = () ->
                scope.focus = false
                scope.mousedown = false
                scope.stroke_width--
    }
]).directive("icswDeviceNetworkHostLink", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        templateNamespace: "svg"
        replace: true
        scope: 
            link: "=link"
            redraw: "=redraw"
        template: $templateCache.get("icsw.device.network.host.link")
        link : (scope, element, attrs) ->
            scope.$watch("link", (new_val) ->
                scope.link = new_val
                #scope.stroke_width = if new_val.num_nds then new_val.num_nds else 1
                #scope.stroke_color = if new_val.num_nds then "grey" else "red"
            )
            scope.$watch("redraw", () ->
                element.attr("x1", scope.link.x1c)
                element.attr("y1", scope.link.y1c)
                element.attr("x2", scope.link.x2c)
                element.attr("y2", scope.link.y2c)
            )
    }
]).directive("icswDeviceNetworkGraph", ["$templateCache", "msgbus", ($templateCache, msgbus) ->
    return {
        restrict : "EA"
        replace: true
        template: $templateCache.get("icsw.device.network.graph")
        link: (scope, element, attrs) ->
            if not attrs["devicepk"]?
                msgbus.emit("devselreceiver")
                msgbus.receive("devicelist", scope, (name, args) ->
                    scope.new_devsel(args[1])
                )
            scope.prev_size = {width:100, height:100}
            scope.get_element_dimensions = () ->
                return {"h": element.height(), "w": element.width()}
            scope.size = {
                width: 1200
                height: 800
            }
            scope.zoom = {
                factor: 1.0
            }
            scope.offset = {
                x: 0
                y: 0
            }
            scope.$watch(
                scope.get_element_dimensions
                (new_val) ->
                    scope.prev_size = {width: scope.size.width, height:scope.size.height}
                    #scope.size.width = new_val["w"]
                    #scope.size.height = new_val["h"]
                    #console.log scope.prev_size, scope.size
                true
            )
            element.bind("resize", () ->
                console.log "Resize"
                scope.$apply()
            )
    }
]).directive("icswDeviceNetworkGraph2", ["d3_service", "dragging", "svg_tools", "blockUI", "ICSW_URLS", "$templateCache", "icswSimpleAjaxCall", (d3_service, dragging, svg_tools, blockUI, ICSW_URLS, $templateCache, icswSimpleAjaxCall) ->
    return {
        restrict : "EA"
        templateNamespace: "svg"
        replace: true
        template: $templateCache.get("icsw.device.network.graph2")
        link : (scope, element, attrs) ->
            scope.cur_scale = 1.0
            scope.cur_trans = [0, 0]
            scope.nodes = []
            scope.links = []
            scope.redraw_nodes = 0
            d3_service.d3().then((d3) ->
                scope.svg_el = element[0]
                svg = d3.select(scope.svg_el)
                #svg.attr("height", scope.size.height)
                scope.force = d3.layout.force().charge(-220).gravity(0.02).linkDistance(150).size([scope.size.width, scope.size.height])
                  .linkDistance((d) -> return 100).on("tick", scope.tick)
                scope.fetch_data()
            scope.fetch_data = () ->
                blockUI.start(
                    "loading, please wait..."
                )
                icswSimpleAjaxCall(
                    url      : ICSW_URLS.NETWORK_JSON_NETWORK
                    data     : 
                        "graph_sel" : scope.graph_sel
                    dataType : "json"
                ).then((json) ->
                    blockUI.stop()
                    scope.json_data = json
                    scope.draw_graph()
                )
            )
            scope.draw_graph = () ->
                scope.iter = 0
                scope.force.nodes(scope.json_data.nodes).links(scope.json_data.links)
                scope.node_lut = {}
                scope.nodes = scope.json_data.nodes
                scope.links = scope.json_data.links
                for node in scope.nodes
                    node.fixed = false
                    node.dragging = false
                    node.ignore_click = false
                    scope.node_lut[node.id] = node
                scope.redraw_nodes++
                scope.force.start()
            scope.find_element = (s_target) ->
                if svg_tools.has_class_svg(s_target, "draggable")
                    return s_target
                s_target = s_target.parent()
                if s_target.length
                    return scope.find_element(s_target)
                else
                    return null
            scope.mouse_down = (event) ->
                drag_el = scope.find_element($(event.target))
                if drag_el.length
                    el_scope = angular.element(drag_el[0]).scope()
                else
                    el_scope = null
                if el_scope
                    drag_el_tag = drag_el.prop("tagName")
                    if drag_el_tag == "svg"
                        dragging.start_drag(event, 0, {
                            dragStarted: (x, y, event) ->
                                scope.sx = x - scope.offset.x
                                scope.sy = y - scope.offset.y
                            dragging: (x, y) ->
                                scope.offset = {
                                   x: x - scope.sx
                                   y: y - scope.sy
                                }
                            dragEnded: () ->
                        })
                    else
                        drag_node = el_scope.node
                        scope.redraw_nodes++
                        dragging.start_drag(event, 1, {
                            dragStarted: (x, y, event) ->
                                drag_node.dragging = true
                                drag_node.fixed = true
                                drag_node.ignore_click = true
                                scope.start_drag_point = scope.rescale(
                                    svg_tools.get_abs_coordinate(scope.svg_el, x, y)
                                )
                                scope.force.start()
                            dragging: (x, y) ->
                                cur_point = scope.rescale(
                                    svg_tools.get_abs_coordinate(scope.svg_el, x, y)
                                )
                                drag_node.x = cur_point.x
                                drag_node.y = cur_point.y
                                drag_node.px = cur_point.x
                                drag_node.py = cur_point.y
                                scope.tick()
                            dragEnded: () ->
                                drag_node.dragging = false
                        })
            scope.rescale = (point) ->
                point.x -= scope.offset.x
                point.y -= scope.offset.y
                point.x /= scope.zoom.factor
                point.y /= scope.zoom.factor
                return point
            scope.iter = 0
            scope.mouse_wheel = (event, delta, deltax, deltay) ->
                scale_point = scope.rescale(
                    svg_tools.get_abs_coordinate(scope.svg_el, event.originalEvent.clientX, event.originalEvent.clientY)
                )
                prev_factor = scope.zoom.factor
                if delta > 0
                    scope.zoom.factor *= 1.05
                else
                    scope.zoom.factor /= 1.05
                scope.offset.x += scale_point.x * (prev_factor - scope.zoom.factor)
                scope.offset.y += scale_point.y * (prev_factor - scope.zoom.factor)
                event.stopPropagation()
                event.preventDefault()
            scope.tick = () ->
                scope.iter++
                #console.log "t"
                for node in scope.force.nodes()
                    t_node = scope.node_lut[node.id]
                    #if t_node.fixed
                        #console.log "*", t_node
                    #    t_node.x = node.x
                    #    t_node.y = node.y
                for link in scope.links
                    s_node = scope.node_lut[link.source.id]
                    d_node = scope.node_lut[link.target.id]
                    link.x1c = s_node.x
                    link.y1c = s_node.y
                    link.x2c = d_node.x
                    link.y2c = d_node.y

                # scope.$apply(() ->
                if true
                    # FIXME, ToDo
                    # console.log "REDRAW"
                    scope.redraw_nodes++
                # )
    }
]).service('icswNetworkDeviceTypeService',
[
    "ICSW_URLS", "icswNetworkTreeService", "$q", "icswComplexModalService", "$compile", "$templateCache",
    "toaster", "icswNetworkDeviceTypeBackup", "icswToolsSimpleModalService",
(
    ICSW_URLS, icswNetworkTreeService, $q, icswComplexModalService, $compile, $templateCache,
    toaster, icswNetworkDeviceTypeBackup, icswToolsSimpleModalService
) ->
    nw_tree = undefined
    return {
        fetch: (scope) ->
            console.log "start fetch"
            defer = $q.defer()
            icswNetworkTreeService.fetch(scope.$id).then(
                (net_tree) ->
                    nw_tree = net_tree
                    defer.resolve(net_tree.nw_device_type_list)
            )
            return defer.promise

        create_or_edit: (scope, event, create, obj_or_parent) ->
            if create
                obj_or_parent = {
                    "identifier"  : "eth"
                    "description" : "new network device type"
                    "name_re"     : "^eth.*$"
                    "mac_bytes"   : 6
                    "allow_virtual_interfaces" : true
                }
            else
                dbu = new icswNetworkDeviceTypeBackup()
                dbu.create_backup(obj_or_parent)
            scope.edit_obj = obj_or_parent
            sub_scope = scope.$new(false)
            icswComplexModalService(
                {
                    message: $compile($templateCache.get("network.device.type.form"))(sub_scope)
                    title: "Network device type"
                    css_class: "modal-wide"
                    ok_label: if create then "Create" else "Modify"
                    closable: true
                    ok_callback: (modal) ->
                        d = $q.defer()
                        if scope.form_data.$invalid
                            toaster.pop("warning", "form validation problem", "", 0)
                            d.reject("form not valid")
                        else
                            if create
                                nw_tree.create_network_device_type(scope.edit_obj).then(
                                    (ok) ->
                                        d.resolve("created")
                                    (notok) ->
                                        d.reject("not created")
                                )
                            else
                                scope.edit_obj.put().then(
                                    (ok) ->
                                        nw_tree.reorder()
                                        d.resolve("updated")
                                    (not_ok) ->
                                        d.reject("not updated")
                                )
                        return d.promise
                    cancel_callback: (modal) ->
                        if not create
                            dbu.restore_backup(obj_or_parent)
                        d = $q.defer()
                        d.resolve("cancel")
                        return d.promise
                }
            ).then(
                (fin) ->
                    console.log "finish"
                    sub_scope.$destroy()
            )
        delete: (obj) ->
            icswToolsSimpleModalService("Really delete Network DeviceType '#{obj.description}' ?").then(
                (ok) ->
                    nw_tree.delete_network_device_type(obj).then(
                        (ok) ->
                    )
            )
    }
]).service('icswNetworkTypeService',
[
    "ICSW_URLS", "icswNetworkTreeService", "$q", "icswComplexModalService", "$compile", "$templateCache",
    "toaster", "icswNetworkTypeBackup", "icswToolsSimpleModalService",
(
    ICSW_URLS, icswNetworkTreeService, $q, icswComplexModalService, $compile, $templateCache,
    toaster, icswNetworkTypeBackup, icswToolsSimpleModalService
) ->
    nw_types_dict = [
        {"value":"b", "name":"boot"}
        {"value":"p", "name":"prod"}
        {"value":"s", "name":"slave"}
        {"value":"o", "name":"other"}
        {"value":"l", "name":"local"}
    ]
    # will be set below
    nw_tree = undefined
    return {
        fetch: (scope) ->
            console.log "start fetch"
            defer = $q.defer()
            icswNetworkTreeService.fetch(scope.$id).then(
                (net_tree) ->
                    nw_tree = net_tree
                    defer.resolve(net_tree.nw_type_list)
            )
            return defer.promise
        create_or_edit: (scope, event, create, obj_or_parent) ->
            if create
                obj_or_parent = {
                    "identifier": "p"
                    "description": "new Network type"
                }
            else
                dbu = new icswNetworkTypeBackup()
                dbu.create_backup(obj_or_parent)
            scope.edit_obj = obj_or_parent
            sub_scope = scope.$new(false)
            icswComplexModalService(
                {
                    message: $compile($templateCache.get("network.type.form"))(sub_scope)
                    title: "Network type"
                    css_class: "modal-wide"
                    ok_label: if create then "Create" else "Modify"
                    closable: true
                    ok_callback: (modal) ->
                        d = $q.defer()
                        if scope.form_data.$invalid
                            toaster.pop("warning", "form validation problem", "", 0)
                            d.reject("form not valid")
                        else
                            if create
                                nw_tree.create_network_type(scope.edit_obj).then(
                                    (ok) ->
                                        d.resolve("created")
                                    (notok) ->
                                        d.reject("not created")
                                )
                            else
                                scope.edit_obj.put().then(
                                    (ok) ->
                                        nw_tree.reorder()
                                        d.resolve("updated")
                                    (not_ok) ->
                                        d.reject("not updated")
                                )
                        return d.promise
                    cancel_callback: (modal) ->
                        if not create
                            dbu.restore_backup(obj_or_parent)
                        d = $q.defer()
                        d.resolve("cancel")
                        return d.promise
                }
            ).then(
                (fin) ->
                    console.log "finish"
                    sub_scope.$destroy()
            )
        delete: (obj) ->
            icswToolsSimpleModalService("Really delete NetworkType '#{obj.description}' ?").then(
                (ok) ->
                    nw_tree.delete_network_type(obj).then(
                        (ok) ->
                    )
            )
        network_types       : nw_types_dict  # for create/edit dialog
        resolve_type: (id) ->
            return (val for val in nw_types_dict when val.value == id)[0].name
    }
]).directive("icswNetworkList", [
    "Restangular", "$templateCache",
(
    Restangular, $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.network.list")
        controller: "icswNetworkListCtrl"
    }
]).controller("icswNetworkListCtrl", [
    "$scope",
(
    $scope
) ->
    console.log "icswnetworklistctrl", $scope
]).service('icswNetworkListService',
[
    "Restangular", "$q", "icswTools", "ICSW_URLS", "icswDomainTreeService", "icswSimpleAjaxCall", "blockUI",
    "icswNetworkTreeService", "icswNetworkBackup", "icswComplexModalService", "$compile", "$templateCache",
    "toaster",
(
    Restangular, $q, icswTools, ICSW_URLS, icswDomainTreeService, icswSimpleAjaxCall, blockUI,
    icswNetworkTreeService, icswNetworkBackup, icswComplexModalService, $compile, $templateCache,
    toaster
) ->

    # networks_rest = Restangular.all(ICSW_URLS.REST_NETWORK_LIST.slice(1)).getList({"_with_ip_info" : true}).$object
    # network_types_rest = Restangular.all(ICSW_URLS.REST_NETWORK_TYPE_LIST.slice(1)).getList({"_with_ip_info" : true}).$object
    # network_device_types_rest = Restangular.all(ICSW_URLS.REST_NETWORK_DEVICE_TYPE_LIST.slice(1)).getList({"_with_ip_info" : true}).$object
    # domain_tree_node_list = []
    # domain_tree_node_dict = {}

    get_defer = (q_type) ->
        d = $q.defer()
        result = q_type.then(
           (response) ->
               d.resolve(response)
        )
        return d.promise

    hide_network =  () ->
        network_display.active_network = null
        network_display.iplist = []

    long2ip = (long) ->
        a = (long & (0xff << 24)) >>> 24
        b = (long & (0xff << 16)) >>> 16
        c = (long & (0xff << 8)) >>> 8
        d = long & 0xff
        return [a, b, c, d].join('.')

    ip2long = (ip) ->
        b = (ip + '').split('.')
        if b.length is 0 or b.length > 4 then throw new Error('Invalid IP')
        for byte, i in b
            if isNaN parseInt(byte, 10) then throw new Error("Invalid byte: #{byte}")
            if byte < 0 or byte > 255 then throw new Error("Invalid byte: #{byte}")
        return ((b[0] or 0) << 24 | (b[1] or 0) << 16 | (b[2] or 0) << 8 | (b[3] or 0)) >>> 0

    reload_networks = (scope) ->
        # blockUI
        blockUI.start()
        icswNetworkTreeService.load("rescan").then(
            (done) ->
                blockUI.stop()
        )

    # network currently displayed
    network_display = {}

    # trees
    nw_tree = undefined
    domain_tree = undefined

    return {
        fetch: (scope) ->
            console.log "start fetch"
            defer = $q.defer()
            $q.all(
                [
                    icswNetworkTreeService.fetch(scope.$id)
                    icswDomainTreeService.fetch(scope.$id)
                ]
            ).then(
                (data) ->
                    nw_tree = data[0]
                    domain_tree = data[1]
                    defer.resolve(nw_tree.nw_list)
            )
            return defer.promise

        # reload

        reload_networks: () ->
            reload_networks()
            hide_network()

        # rescan

        rescan_networks: () ->
            console.log "reimplement rescan"

        # access functions

        nw_tree: () ->
            return nw_tree

        domain_tree: () ->
            return domain_tree

        create_or_edit: (scope, event, create, obj_or_parent) ->
            if create
                obj_or_parent = {
                    "identifier"   : "new network",
                    "network_type" : (entry.idx for entry in nw_tree.nw_type_list when entry.identifier == "o")[0]
                    "enforce_unique_ips" : true
                    "num_ip"       : 0
                    "gw_pri"       : 1
                }
            else
                dbu = new icswNetworkBackup()
                dbu.create_backup(obj_or_parent)
            scope.edit_obj = obj_or_parent
            sub_scope = scope.$new(false)
            icswComplexModalService(
                {
                    message: $compile($templateCache.get("network.form"))(sub_scope)
                    title: "Network"
                    css_class: "modal-wide"
                    ok_label: if create then "Create" else "Modify"
                    closable: true
                    ok_callback: (modal) ->
                        d = $q.defer()
                        if scope.form_data.$invalid
                            toaster.pop("warning", "form validation problem", "", 0)
                            d.reject("form not valid")
                        else
                            if create
                                nw_tree.create_network(scope.edit_obj).then(
                                    (ok) ->
                                        d.resolve("created")
                                    (notok) ->
                                        d.reject("not created")
                                )
                            else
                                scope.edit_obj.put().then(
                                    (ok) ->
                                        nw_tree.reorder()
                                        d.resolve("updated")
                                    (not_ok) ->
                                        d.reject("not updated")
                                )
                        return d.promise
                    cancel_callback: (modal) ->
                        if not create
                            dbu.restore_backup(obj_or_parent)
                        d = $q.defer()
                        d.resolve("cancel")
                        return d.promise
                }
            ).then(
                (fin) ->
                    console.log "finish"
                    sub_scope.$destroy()
            )

        get_production_networks : () ->
            prod_idx = (entry for entry in nw_tree.nw_type_list when entry.identifier == "p")[0].idx
            return (entry for entry in nw_tree.nw_list when entry.network_type == prod_idx)

        is_slave_network : (nw_type) ->
            if nw_type
                return nw_tree.nw_type_lut[nw_type].identifier == "s"
            else
                return false

        has_master_network : (edit_obj) ->
            return if edit_obj.master_network then true else false

        get_master_network_id: (edit_obj) ->
            if edit_obj.master_network
                return nw_tree.nw_lut[edit_obj.master_network].identifier
            else
                return "---"

        preferred_dtn: (edit_obj) ->
            if edit_obj.preferred_domain_tree_node
                return domain_tree.lut[edit_obj.preferred_domain_tree_node].full_name
            else
                return "---"

        get_network_device_types: (edit_obj) ->
            if edit_obj.network_device_type.length
                return (nw_tree.nw_device_type_lut[nd].identifier for nd in edit_obj.network_device_type).join(", ")
            else
                return "---"

        delete_confirm_str  : (obj) -> return "Really delete Network '#{obj.identifier}' ?"

        network_display     : network_display

        hide_network : () ->
            return hide_network()

        show_network        : (obj) ->
            if network_display.active_network == obj
                hide_network()
            else
                network_display.active_network = obj
                q_list = [
                    get_defer(Restangular.all(ICSW_URLS.REST_NET_IP_LIST.slice(1)).getList({"network" : obj.idx, "_order_by" : "ip"}))
                    get_defer(Restangular.all(ICSW_URLS.REST_NETDEVICE_LIST.slice(1)).getList({"net_ip__network" : obj.idx}))
                    get_defer(Restangular.all(ICSW_URLS.REST_DEVICE_LIST.slice(1)).getList({"netdevice__net_ip__network" : obj.idx}))
                ]
                $q.all(q_list).then(
                    (data) ->
                        iplist = data[0]
                        netdevices = icswTools.build_lut(data[1])
                        devices = icswTools.build_lut(data[2])
                        for entry in iplist
                            nd = netdevices[entry.netdevice]
                            entry.netdevice_name = nd.devname
                            entry.device_full_name = devices[nd.device].full_name
                        network_display.iplist = iplist
                )

        # range functions

        autorange_set : (edit_obj) ->
            if edit_obj.start_range == "0.0.0.0" and edit_obj.end_range == "0.0.0.0"
                return false
            else
                return true

        clear_range : (edit_obj) ->
            edit_obj.start_range = "0.0.0.0"
            edit_obj.end_range = "0.0.0.0"

        enter_range : (edit_obj) ->
            # click on range field
            sr = edit_obj.start_range
            er = edit_obj.end_range
            if (not sr and not er) or (sr == "0.0.0.0" and er == "0.0.0.0")
                sr = ip2long(edit_obj.network) + 1
                er = ip2long(edit_obj.network) + (4294967295 - ip2long(edit_obj.netmask)) - 1
                # range valid, set
                if sr < er
                    edit_obj.start_range = long2ip(sr)
                    edit_obj.end_range = long2ip(er)

        range_check : (edit_obj) ->
            # check the range parameters
            sr = edit_obj.start_range
            er = edit_obj.end_range
            if sr and er
                sr = ip2long(sr)
                er = ip2long(er)
                min = ip2long(edit_obj.network) + 1
                max = ip2long(edit_obj.network) + (4294967295 - ip2long(edit_obj.netmask)) - 1
                # todo, improve checks

        # autocomplete network settings

        network_or_netmask_blur : (edit_obj) ->
            # calculate broadcast and gateway automatically

            # validation ensures that if it is not undefined, then it is a valid entry
            if edit_obj.network? and edit_obj.netmask?

                ip_long = ip2long(edit_obj.network)
                mask_long = ip2long(edit_obj.netmask)

                base_long = ip_long & mask_long
                bcast_long = (ip_long & mask_long) | (4294967295 - mask_long)

                # only set if there is no previous value
                if ! edit_obj.broadcast?
                    edit_obj.broadcast = long2ip(bcast_long)
                if ! edit_obj.gateway?
                    edit_obj.gateway = long2ip(base_long)
    }
])
