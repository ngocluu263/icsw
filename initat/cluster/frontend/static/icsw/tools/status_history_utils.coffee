

angular.module(
    "icsw.tools.status_history_utils", ["icsw.tools.piechart", "restangular"]
).directive('icswToolsDeviceHistStatusOverview', ["$parse", "status_utils_functions", ($parse, status_utils_functions) ->
    # shows piechart and possibly table of historic device status
    # used in status history page and monitoring overview
    return {
        restrict: 'E',
        scope: {
            data: "="  # if data is passed right through here, the other attributes are discarded
                       # data must be defined if we are not below the status history ctrl
            deviceid: "="
        },
        require: '?^icswDeviceStatusHistoryOverview'
        templateUrl: "icsw.tools.device_hist_status"
        link: (scope, element, attrs, status_history_ctrl) ->
            scope.show_table = scope.$eval(attrs.showTable)

            # TODO: make this into a filter, then remove also from serviceHist*
            scope.float_format = (n) -> return (n*100).toFixed(2) + "%"

            scope.pie_data = []
            weights = {
                "Up": -10
                "Down": -8
                "Unreachable": -6
                "Undetermined": -4
            }

            colors = {
                "Up": "#66dd66"
                "Down": "#ff7777"
                "Unreachable": "#f0ad4e"
                "Undetermined": "#c7c7c7"
            }

            scope.update_from_server = () ->
                if status_history_ctrl.time_frame?
                    cont = (new_data) ->
                        new_data = new_data[Object.keys(new_data)[0]]  # there is only one device
                        [scope.host_data, scope.pie_data] = status_utils_functions.preprocess_state_data(new_data, weights, colors, scope.float_format)

                    status_utils_functions.get_device_data(
                        [scope.deviceid],
                        status_history_ctrl.time_frame.date_gui,
                        status_history_ctrl.time_frame.duration_type,
                        cont)
                else
                    scope.host_data = []
                    scope.pie_data = []

            scope.update_from_local_data = () ->
                if scope.data?
                    [scope.host_data, scope.pie_data] = status_utils_functions.preprocess_state_data(scope.data, weights, colors, scope.float_format)

            if attrs.data?
                scope.$watch('data', (unused) -> scope.update_from_local_data())
            else
                scope.$watchGroup(
                    ['deviceid', () -> return status_history_ctrl.time_frame]
                    (unused) -> scope.update_from_server())
    }
]).directive('icswToolsServiceHistStatusOverview', ["$parse", "status_utils_functions", ($parse, status_utils_functions) ->
    # shows piechart of state of service. shows how many service are in which state at a given time frame
    # currently only used in monitoring_overview
    return {
        restrict: 'E',
        scope: {
            data: "="  # if data is passed right through here, the other attributes are discarded
                       # data must be defined if we are not below the status history ctrl
            deviceid: "="
        },
        templateUrl: "icsw.tools.service_hist_status"
        require: '?^icswDeviceStatusHistoryCtrl'
        link: (scope, element, attrs, status_history_ctrl) ->

            # TODO: see above
            scope.float_format = (n) -> return (n*100).toFixed(2) + "%"

            scope.pie_data = []

            scope.update_from_server = () ->
                if status_history_ctrl.time_frame?
                    cont = (new_data) ->
                        new_data = new_data[Object.keys(new_data)[0]]  # there is only one device
                        new_data = new_data['main']  # only main data here
                        [scope.service_data, scope.pie_data] = status_utils_functions.preprocess_service_state_data(new_data)

                    status_utils_functions.get_service_data(
                        [scope.deviceid],
                        status_history_ctrl.time_frame.date_gui,
                        status_history_ctrl.time_frame.time_range,
                        cont,
                        merge_services=1)

            scope.update_from_local_data = () ->
                if scope.data?
                    [scope.service_data, scope.pie_data] = status_utils_functions.preprocess_service_state_data(scope.data)

            if attrs.data?
                scope.$watch('data', (unused) -> scope.update_from_local_data())
            else
                scope.$watchGroup(
                    ['deviceid', () -> return status_history_ctrl.time_frame]
                    (unused) -> scope.update_from_server())
    }
]).service('status_utils_functions', ["Restangular", "ICSW_URLS", (Restangular, ICSW_URLS) ->
    service_colors = {
            "Ok": "#66dd66"
            "Warning": "#f0ad4e"
            "Critical": "#ff7777"
            "Unknown": "#c7c7c7"
            "Undetermined": "#c7c7c7"
        }
    get_device_data = (device_ids, start_date, timerange, cont) ->
        query_data = {
            'device_ids': device_ids.join(),
            'date': moment(start_date).unix()  # ask server in utc
            'duration_type': timerange,
        }
        base = Restangular.all(ICSW_URLS.MON_GET_HIST_DEVICE_DATA.slice(1))
        base.getList(query_data).then((new_data) ->
            # customGET fucks up the query data, so just fake lists
            obj = new_data.plain()[0]
            cont(obj)
        )
    get_service_data = (device_ids, start_date, timerange, cont, merge_services=0) ->
        # merge_services: boolean as int
        expect_array = merge_services != 0
        query_data = {
            'device_ids': device_ids.join(),
            'date': moment(start_date).unix()  # ask server in utc
            'duration_type': timerange,
            'merge_services': merge_services,
        }
        base = Restangular.all(ICSW_URLS.MON_GET_HIST_SERVICE_DATA.slice(1))
        # we always return a list for easier REST handling
        base.getList(query_data).then((data_pseudo_list) ->
            # need plain() to get rid of restangular stuff
            console.log 'new get_service_data: ', data_pseudo_list.plain()[0]
            cont(data_pseudo_list.plain()[0])
        )
    get_timespan = (start_date, timerange, cont) ->
        query_data = {
            'date': moment(start_date).unix()  # ask server in utc
            'duration_type': timerange,
        }
        base = Restangular.all(ICSW_URLS.MON_GET_HIST_TIMESPAN.slice(1))
        base.getList(query_data).then(cont)
    float_format = (n) -> return (n*100).toFixed(2) + "%"
    preprocess_state_data = (new_data, weights, colors) ->
        formatted_data = _.cloneDeep(new_data)
        for key of weights
            if not _.any(new_data, (d) -> return d['state'] == key)
                formatted_data.push({'state': key, 'value': 0})

        for d in formatted_data
            d['value'] = float_format(d['value'])
        final_data = _.sortBy(formatted_data, (d) -> return weights[d['state']])

        new_data = _.sortBy(new_data, (d) -> return weights[d['state']])

        pie_data = []
        for d in new_data
            if d['state'] != "Flapping"  # can't display flapping in pie
                pie_data.push {
                    'title': d['state']
                    'value': Math.round(d['value']*10000) / 100
                    'color': colors[d['state']]
                }
        return [final_data, pie_data]
    preprocess_service_state_data = (new_data, float_format) ->
        weights = {
            "Ok": -10
            "Warning": -9
            "Critical": -8
            "Unknown": -5
            "Undetermined": -4
        }
        return preprocess_state_data(new_data, weights, service_colors, float_format)
    return {
        float_format: float_format
        get_device_data: get_device_data
        get_service_data: get_service_data
        get_timespan: get_timespan
        preprocess_state_data: preprocess_state_data
        preprocess_service_state_data: preprocess_service_state_data
        service_colors: service_colors
    }
]).directive("icswToolsServiceHistLineGraph", ["status_utils_functions", (status_utils_functions) ->
    return {
        restrict: 'E'
        scope   : {
            'data' : '='
        }
        require : "^icswDeviceStatusHistoryOverview"
        template: """
<svg ng-attr-width="{{width}}" height="30">
    <g>
        <rect ng-repeat="entry in data_display" ng-attr-x="{{entry.pos_x}}"  y="5"
              ng-attr-width="{{entry.width}}" ng-attr-height="{{entry.height}}" rx="1" ry="1"
              ng-attr-style="fill:{{entry.color}};stroke-width:0;stroke:rgb(0,0,0)"></rect>
    </g>
    <g>
        <text ng-repeat="marker in timemarker_display" ng-attr-x="{{marker.pos_x}}" y="30"  style="fill:black;" font-size="10px" text-anchor="middle" alignment-baseline="baseline">{{marker.text}}</text>
    </g>
</svg>
"""
        link: (scope, element, attrs, status_history_ctrl) ->
            scope.width = 300
            scope.side_margin = 15
            scope.draw_width = scope.width - 2 * scope.side_margin

            scope.update = () ->

                console.log 'upd line gr', scope.data
                time_frame = status_history_ctrl.time_frame

                if time_frame?

                    scope.timemarker_display = []
                    time_marker = status_history_ctrl.get_time_marker()
                    for marker, index in time_marker
                        scope.timemarker_display.push(
                            {
                                text: marker
                                pos_x: scope.side_margin + index * scope.draw_width / (time_marker.length-1)
                            }

                        )
                        # console.log ' posx mark', scope.side_margin + index * scope.draw_width / (scope.timemarker.length-1)

                    total_duration = time_frame.end.diff(time_frame.start)

                    scope.data_display = []

                    pos_x = scope.side_margin

                    last_date = time_frame.start

                    for entry, index in scope.data.concat('last')
                            if entry == 'last'
                                cur_date = time_frame.end
                            else
                                cur_date = moment.utc(entry.date)

                            duration = cur_date.diff(last_date)

                            entry_width = scope.draw_width * duration / total_duration

                            if index != 0
                                last_state = scope.data[index-1].state

                                scope.data_display.push(
                                    {
                                        pos_x : pos_x
                                        width : entry_width
                                        color : status_utils_functions.service_colors[last_state]
                                        height: 15
                                    }
                                )

                                # console.log 'entry ', pos_x, pos_x + entry_width

                            pos_x += entry_width

                            last_date = cur_date

                    console.log 'done'
                else
                    scope.data = []

            scope.$watchGroup(['data', () -> return status_history_ctrl.time_frame],  (unused) -> scope.update() )
    }
])
