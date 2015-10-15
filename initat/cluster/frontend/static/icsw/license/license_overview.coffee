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

# NOTE: ui.bootstrap and angular-dimple both define a bar directive and therefore can not be used in the same module
lic_module = angular.module("icsw.license.overview",
        ["ngResource", "ngCookies", "ngSanitize", "init.csw.filters", "ui.bootstrap", "ui.codemirror", "icsw.d3", "icsw.dimple",
         "icsw.tools.angular-dimple-init", "ui.bootstrap.datetimepicker", "restangular", "icsw.tools"])

lic_module.controller("icswLicenseOverviewCtrl",
    ["$scope", "$compile", "$filter", "$templateCache", "restDataSource", "$q", "$modal", "access_level_service",
     "$timeout", "$sce", "$resource", "d3_service", "dimple_service", "ICSW_URLS",
    ($scope, $compile, $filter, $templateCache, restDataSource, $q, $modal, access_level_service,
     $timeout, $sce, $resource, d3_service, dimple_service, ICSW_URLS) ->
        wait_list = restDataSource.add_sources([
            [ICSW_URLS.REST_DEVICE_LIST, {}],
            [ICSW_URLS.REST_EXT_LICENSE_LIST, {}],
        ])
        $q.all(wait_list).then( (data) ->
            $scope.device_list = data[0]
            $scope.ext_license_list = data[1]

            # for testing:
            # $scope.ext_license_list[1].selected = true
            # $scope.license_select_change()

            $scope.update_lic_overview_data()
        )

        $scope.$watch('timerange', (unused) -> $scope.update_lic_overview_data())
        $scope.$watch('licdaterangestart', (unused) -> $scope.update_lic_overview_data())
        $scope.$watch('multi_view', (unused) -> $scope.update_lic_overview_data())

        $scope.view_mode = 'default'

        $scope.set_view_mode = (mode) ->
            if mode == $scope.view_mode
                $scope.view_mode = 'default'
            else
                $scope.view_mode = mode

        $scope.update_lic_overview_data = () ->
            if $scope.ext_license_list
                for lic in $scope.ext_license_list
                    if $scope.multi_view
                        lic.usage = ""
                    else
                        do (lic) ->
                            lic_utils.get_lic_data($resource, 'default', lic.idx, $scope.timerange, $scope.licdaterangestart, ICSW_URLS, (new_data) ->
                                if new_data.length > 0
                                    lic.usage = "(" + lic_utils.calc_avg_usage(new_data) + "%)"
                                else
                                    lic.usage = ""
                            )
        $scope.dimpleloaded = false
        d3_service.d3().then( (d3) ->
            dimple_service.dimple().then( (dimple) ->
                $scope.dimpleloaded = true
            )
        )
        $scope.license_select_change = () ->
            $scope.ext_license_selected = []
            if $scope.ext_license_list
                for lic in $scope.ext_license_list
                    if lic.selected
                        $scope.ext_license_selected.push(lic)
        $scope.license_select_change()  # init by empty list

        $scope.get_li_sel_class = (li) ->
            if li.selected
                return "btn btn-xs btn-success"
            else
                return "btn btn-xs"
        $scope.toggle_li_sel = (li) ->
            li.selected = !li.selected
            $scope.license_select_change()

        $scope.set_timerange = (tr) ->
            $scope.timerange = tr
        $scope.set_timerange("week")
        $scope.licdaterangestart = moment().startOf("day")
        $scope.multi_view = false
        $scope.cur_time = moment().format()
        # for testing:
        $scope.licdaterangestart = moment("Tue Oct 07 2014 00:00:00 GMT+0200 (CEST)")
    #$scope.cur_time = "Wed Oct 15 2014 00:00:00 GMT+0200 (CEST)"

]).directive("icswLicenseOverview", ["$templateCache", ($templateCache) ->
    restrict: "EA"
    templateUrl: "icsw.license.overview"

]).directive("icswLicenseGraph", ["$templateCache", "$resource", "ICSW_URLS", "icswSimpleAjaxCall", ($templateCache, $resource, ICSW_URLS, icswSimpleAjaxCall) ->
    return {
    restrict : "EA"
    template : """
{% verbatim %}
<div ng-if="dimpleloaded">
    <div ng-if="!fixed_range">
        <h3>License: {{ lic_name }} {{ header_addition }}</h3>
    </div>
    <div ng-if="lic_data_show.length > 0">
        <graph data="lic_data_show" width="{{lic_graph_width}}" height="{{lic_graph_height}}">
            <x field="date" order-by="full_date" title="null"></x>
            <y field="value" title="License usage"></y>
            <stacked-area field="type"/>
            <!--
            the data is meant differently than displayed in legend currently
            -->
            <legend></legend>
        </graph>
    </div>
    <div ng-if="lic_data_show.length == 0">
        no data available
    </div>
</div>
{% endverbatim %}
"""
    scope : {
        timerange: '='
        dimpleloaded: '='
        licdaterangestart: '='
        viewmode: '='
    }
    link : (scope, el, attrs) ->
        # can't reuse other attributes as they are shared with parent scope
        scope.fixed_range = attrs.fixedtimerange? && attrs.fixedlicdaterangestart?
        scope.lic_id = attrs.lic
        scope.lic_name = attrs.licname

        scope.set_lic_data = () ->
            # we get lic_data and lic_data_min_max by default
            list = switch
                when scope.viewmode == "show_min_max" then "lic_data_min_max"
                when scope.viewmode == "show_user"    then "lic_data_user"
                when scope.viewmode == "show_device"  then "lic_data_device"
                when scope.viewmode == "show_version" then "lic_data_version"
                else "lic_data"

            # set or retrieve
            if scope[list]
                console.log "use data", list, scope[list]
                console.log _.map(scope[list], (x) -> x.full_date)

                # this is not nice, but we sometimes need apply, and finding out whether we are in an apply is an anti-pattern
                scope.lic_data_show = scope[list]

                scope.$apply(
                        scope.lic_data_show = scope[list]
                )
            else
                console.log "retrieve data", list, scope.viewmode
                scope.update_lic_data(scope.viewmode)

        scope.update_lic_data = (viewmode, reset=false) ->
            if reset
                scope.lic_data = null
                scope.lic_data_min_max = null
                scope.lic_data_version = null
                scope.lic_data_user = null
                scope.lic_data_device = null

            # call with argument to allow obtaining general data when in view mode
            tr = if scope.fixed_range then attrs.fixedtimerange else scope.timerange
            start_date = if scope.fixed_range then attrs.fixedlicdaterangestart else scope.licdaterangestart

            # prepare data for dimple
            # only define continuation function per mode
            create_common = (entry) -> return {"date": entry.display_date, "full_date": entry.full_start_date}
            scope.lic_graph_width = 500
            scope.lic_graph_height = 300
            if viewmode == 'default' || viewmode == "show_min_max"
                cont = (new_data, dates) ->
                    console.log "calc default data"
                    scope.lic_data = []
                    scope.lic_data_min_max = []
                    for entry in new_data
                        common = create_common(entry)

                        # we have an entry for this
                        _.remove(dates, (elem) -> elem.date == common.date)

                        scope.lic_data.push(_.merge({ "type" : "used", "value": entry.used, "order": 1 }, common))
                        scope.lic_data.push(_.merge({ "type" : "unused", "value": entry.issued - entry.used, "order": 2 }, common))

                        scope.lic_data_min_max.push(_.merge({ "type": "min used", "value": entry.used_min, "order": 1 }, common))
                        scope.lic_data_min_max.push(_.merge({ "type": "avg used", "value": entry.used - entry.used_min, "order": 2 }, common))
                        scope.lic_data_min_max.push(_.merge({ "type": "max used", "value": entry.used_max - entry.used, "order": 3 }, common))
                        scope.lic_data_min_max.push(_.merge({ "type": "unused", "value": entry.issued_max - entry.used_max, "order": 4 }, common))  # use issued_max as used_max can be greater than issued

                    if new_data.length != 0  # we have got data, add missing ones
                        for date in dates
                            scope.lic_data.push({ "type" : "used",   "date": date.date, "full_date": date.full_date, "value" : 0,  "order" : 1 })
                            scope.lic_data.push({ "type" : "unused", "date": date.date, "full_date": date.full_date, "value" : 0,  "order" : 2 })

                            scope.lic_data_min_max.push({ "type" : "min used", "date" : date.date, "full_date": date.full_date, "value" : 0,  "order" : 1 })
                            scope.lic_data_min_max.push({ "type" : "avg used", "date" : date.date, "full_date": date.full_date, "value" : 0,  "order" : 2 })
                            scope.lic_data_min_max.push({ "type" : "max used", "date" : date.date, "full_date": date.full_date, "value" : 0,  "order" : 3 })
                            scope.lic_data_min_max.push({ "type" : "unused",   "date" : date.date, "full_date": date.full_date, "value" : 0,  "order" : 4 })

                    if new_data.length > 0
                        scope.header_addition = "(" + lic_utils.calc_avg_usage(new_data) + "% usage)"
            else if viewmode == 'show_version'
                cont = (new_data, dates) ->
                    console.log "calc version data"
                    scope.lic_data_version = []
                    types = []
                    for entry in new_data
                        common = create_common(entry)

                        type = "#{entry.ext_license_version_name} (#{entry.vendor_name})"
                        types.push type
                        scope.lic_data_version.push(_.merge({ "type" : type, "value" : entry.frequency, "order" : 0}, common))

                    if new_data.length != 0  # we have got some data, add missing ones
                        for type in _.uniq(types)
                            for date in dates
                                if _.find(scope.lic_data_version, (elem) -> elem.date == date.date && elem.type == type) == undefined
                                    scope.lic_data_version.push({ "type" : type, "date": date.date, "full_date": date.full_date, "value" : 0, "order" : 0 })
            else if viewmode == 'show_user' || viewmode == 'show_device'
                list = switch
                    when viewmode == 'show_user' then "lic_data_user"
                    else "lic_data_device"
                cont = (new_data, dates) ->
                    console.log "calc version "+viewmode
                    scope[list] = []
                    types = []
                    for entry in new_data
                        types.push entry.type
                        common = create_common(entry)
                        scope[list].push(_.merge({ "type" : entry.type, "value" : entry.val, "order" : 0}, common))


                    # TODO: this does not work yet, the angular-dimple directive does not care about changes after initialisation
                    if types.length > 6
                        scope.lic_graph_width = 800
                        scope.lic_graph_height = 600
                    else
                        scope.lic_graph_width = 500
                        scope.lic_graph_height = 300

                    # TODO: extract into function together with code above
                    if new_data.length != 0  # we have got some data, add missing ones
                        for type in _.uniq(types)
                            for date in dates
                                if _.find(scope[list], (elem) -> elem.date == date.date && elem.type == type) == undefined
                                    scope[list].push({ "type" : type, "date": date.date, "full_date": date.full_date, "value" : 0, "order" : 0 })

            lic_utils.get_lic_data($resource, viewmode, scope.lic_id, tr, start_date, ICSW_URLS, (new_data) ->
                # also query all possible dates to check for missing ones (dimple needs all of them)
                icswSimpleAjaxCall(
                    url: ICSW_URLS.LIC_GET_LICENSE_OVERVIEW_STEPS
                    data:
                        "date": moment(start_date).unix()  # ask server in utc
                        "duration_type" : tr
                    dataType : "json"
                ).then((steps_json) ->
                    cont(new_data, steps_json)
                    scope.set_lic_data()
                )
            )

        if !scope.fixed_range
            # need to watch by string and not by var, probably because var originates from parent scope
            scope.$watch('timerange', (unused) -> scope.update_lic_data(scope.viewmode, true))
            scope.$watch('licdaterangestart', (unused) -> scope.update_lic_data(scope.viewmode, true))
        else
            # no updates for fixed range
            scope.update_lic_data(scope.viewmode)
        scope.$watch('viewmode', (unused) -> scope.set_lic_data())
    }
])

# TODO: make service out of this
lic_utils = {
    get_lic_data: ($resource, viewmode, lic_id, timerange, start_date, ICSW_URLS, cont) ->
        lic_resource = switch
            when viewmode == "show_version" then $resource(ICSW_URLS.LIC_LICENSE_VERSION_STATE_COARSE_LIST, {})
            when viewmode == "show_user" then $resource(ICSW_URLS.LIC_LICENSE_USER_COARSE_LIST, {})
            when viewmode == "show_device" then $resource(ICSW_URLS.LIC_LICENSE_DEVICE_COARSE_LIST, {})
            else $resource(ICSW_URLS.LIC_LICENSE_STATE_COARSE_LIST, {})  # this is default and min_max
        query_data = {
            'lic_id': lic_id
            'duration_type' : timerange
            'date' : moment(start_date).unix()  # ask server in utc
        }
        lic_resource.query(query_data, (new_data) ->
            cont(new_data)
        )
    calc_avg_usage: (new_data) ->
        sum_used = 0
        sum_issued = 0
        for entry in new_data
            sum_used += entry.used
            sum_issued += entry.issued
        return Math.round( 100 * (sum_used / sum_issued) )
}

