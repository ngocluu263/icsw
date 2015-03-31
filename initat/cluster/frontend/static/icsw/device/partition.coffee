# Copyright (C) 2012-2015 init.at
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
    "icsw.device.partition"
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "icsw.d3", "icsw.tools.button"
    ]
).directive("icswDevicePartitionOverview", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.device.partition.overview")
        link : (scope, el, attrs) ->
        controller: ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "$q", "$modal", "blockUI", "ICSW_URLS", "icswCallAjaxService", "icswParseXMLResponseService",
        ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, $q, $modal, blockUI, ICSW_URLS, icswCallAjaxService, icswParseXMLResponseService) ->
            $scope.entries = []
            $scope.active_dev = undefined
            $scope.devsel_list = []
            $scope.new_devsel = (_dev_sel, _devg_sel) ->
                $scope.devsel_list = _dev_sel
                $scope.reload()
            $scope.reload = () ->
                active_tab = (dev for dev in $scope.entries when dev.tab_active)
                restDataSource.reload([ICSW_URLS.REST_DEVICE_TREE_LIST, {"with_disk_info" : true, "with_meta_devices" : false, "pks" : angular.toJson($scope.devsel_list), "olp" : "backbone.device.change_monitoring"}]).then((data) ->
                    $scope.entries = (dev for dev in data)
                    if active_tab.length
                        for dev in $scope.entries
                            if dev.idx == active_tab[0].idx
                                dev.tab_active = true
                )
            $scope.get_vg = (dev, vg_idx) ->
                return (cur_vg for cur_vg in dev.act_partition_table.lvm_vg_set when cur_vg.idx == vg_idx)[0]
            $scope.clear = (pk) ->
                if pk?
                    blockUI.start()
                    icswCallAjaxService
                        url     : ICSW_URLS.MON_CLEAR_PARTITION
                        data    : {
                            "pk" : pk
                        }
                        success : (xml) ->
                            blockUI.stop()
                            icswParseXMLResponseService(xml)
                            $scope.reload()
            $scope.fetch = (pk) ->
                if pk?
                    blockUI.start()
                    icswCallAjaxService
                        url     : ICSW_URLS.MON_FETCH_PARTITION
                        data    : {
                            "pk" : pk
                        }
                        success : (xml) ->
                            blockUI.stop()
                            icswParseXMLResponseService(xml)
                            $scope.reload()
            $scope.use = (pk) ->
                if pk?
                    blockUI.start()
                    icswCallAjaxService
                        url     : ICSW_URLS.MON_USE_PARTITION
                        data    : {
                            "pk" : pk
                        }
                        success : (xml) ->
                            blockUI.stop()
                            icswParseXMLResponseService(xml)
                            $scope.reload()
        ]
    }
])
