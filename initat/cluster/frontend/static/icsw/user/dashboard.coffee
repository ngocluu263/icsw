DT_FORM = "YYYY-MM-DD HH:mm"

# dashboard depends on user module
dashboard_module = angular.module(
    "icsw.user.dashboard",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular",
        "noVNC", "ui.select", "icsw.tools", "icsw.user.password", "icsw.user",
    ]
).controller("icswUserJobInfoCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$timeout", "$modal", "ICSW_URLS",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $timeout, $modal, ICSW_URLS)->
        $scope.jobs_waiting = []
        $scope.jobs_running = []
        $scope.jobs_finished = []
        $scope.jobinfo_valid = false
        class jobinfo_timedelta
            constructor: (@name, @timedelta_description) ->
        $scope.all_timedeltas = [
            new jobinfo_timedelta("last 15 minutes", [15, "minutes"])
            new jobinfo_timedelta("last hour", [1, "hours"])
            new jobinfo_timedelta("last 4 hours", [4, "hours"])
            new jobinfo_timedelta("last day", [1, "days"])
            new jobinfo_timedelta("last week", [1, "weeks"])
        ]
        $scope.set_jobinfo_timedelta = (ts) ->
            $scope.last_jobinfo_timedelta = ts
            jobsfrom = moment().subtract(
                ts.timedelta_description[0],
                ts.timedelta_description[1]
            ).unix()
            call_ajax
                  url      : ICSW_URLS.RMS_GET_RMS_JOBINFO
                  data     :
                      "jobinfo_jobsfrom" : jobsfrom
                  dataType : "json"
                  success  : (json) =>
                      $scope.$apply(
                          $scope.jobinfo_valid = true
                          $scope.jobs_running = json.jobs_running
                          $scope.jobs_waiting = json.jobs_waiting
                          $scope.jobs_finished = json.jobs_finished
                      )
        $scope.set_jobinfo_timedelta( $scope.all_timedeltas[1] )
        listmax = 15
        jobidToString = (j) -> 
            if j[1] != ""
                return " "+j[0]+":"+j[1]
            else
                return " "+j[0]
                    
        $scope.longListToString = (l) ->
            if l.length < listmax
                return [jobidToString(i) for i in l].toString()
            else
                return (jobidToString(i) for i in l[0..listmax]).toString() + ", ..."
]).directive("icswUserJobInfo", ["$templateCache", ($templateCache) ->
        restrict : "EA"
        template : $templateCache.get("icsw.user.job.info")
        link: (scope, element, attrs) ->
]).directive("icswUserVduOverview", ["$compile", "$templateCache", "icswTools", "ICSW_URLS", ($compile, $templateCache, icswTools, ICSW_URLS) ->
        restrict : "EA"
        template : $templateCache.get("icsw.user.vdu.overview")
        link: (scope, element, attrs) ->
            scope.object = undefined
            
            scope.ips_for_devices = {}
            scope.ips_loaded = false

            scope.single_vdus_index = '{{ vdus_index }}' # from django via get parameter FIXME
            scope.single_vdus = undefined
            scope.show_single_vdus = false

            scope.virtual_desktop_sessions = []
            scope.virtual_desktop_user_setting = []
            scope.$watch(attrs["object"], (new_val) ->
                scope.object = new_val
                    
                if scope.object?
                    scope.virtual_desktop_sessions = scope.virtual_desktop_user_setting.filter((vdus) ->  vdus.user == scope.object.idx && vdus.to_delete == false)
                    # get all ips
                    scope.retrieve_device_ip vdus.device for vdus in scope.virtual_desktop_sessions

                    if scope.single_vdus_index
                        scope.single_vdus = scope.virtual_desktop_user_setting.filter((vdus) -> vdus.idx == scope.single_vdus_index)[0]
                        scope.show_single_vdus = true
            )
            scope.get_vnc_display_attribute_value = (geometry) ->
                [w, h] = screen_size.parse_screen_size(geometry)
                return "{width:"+w+",height:"+h+",fitTo:'width',}"
            scope.get_device_by_index = (index) ->
                return _.find(scope.device, (vd) -> vd.idx == index)
            scope.get_virtual_desktop_protocol = (index) ->
                return _.find(scope.virtual_desktop_protocol, (vd) -> vd.idx == index)
            scope.get_window_manager = (index) ->
                return _.find(scope.window_manager, (vd) -> vd.idx == index)
            scope.open_vdus_in_new_tab = (vdus) ->
                url = ICSW_URLS.MAIN_VIRTUAL_DESKTOP_VIEWER
                window.open(url + "?vdus_index="+vdus.idx)
            scope.show_viewer_command_line = (vdus) ->
                vdus.show_viewer_command_line = !vdus.show_viewer_command_line
            scope.retrieve_device_ip = (index) ->
                # set some dummy value so that the vnc directive doesn't complain
                dummy_ip = "0.0.0.0"
                scope.ips_for_devices[index] = dummy_ip
                call_ajax
                    url      : ICSW_URLS.USER_GET_DEVICE_IP
                    data     :
                        "device" : index
                    dataType : "json"
                    success  : (json) =>
                        scope.$apply(
                            scope.ips_for_devices[index] = json.ip
                            if _.indexOf(scope.ips_for_devices, dummy_ip) == -1
                                # all are loaded
                                scope.ips_loaded = true

                                # calc command lines
                                for vdus in scope.virtual_desktop_sessions
                                    vdus.viewer_cmd_line = virtual_desktop_utils.get_viewer_command_line(vdus, scope.ips_for_devices[vdus.device]) 
                        )
                
            scope.download_vdus_start_script = (vdus) ->
                # create .vnc file (supported by at least tightvnc and realvnc on windows)
                content = ["[Connection]\n",
                          "Host=#{ scope.ips_for_devices[vdus.device] }:#{ vdus.effective_port }\n",
                          "Password=#{ vdus.vnc_obfuscated_password }\n"]
                blob = new Blob(content, {type: "text/plain;charset=utf-8"});
                # use FileSaver.js
                saveAs(blob, "#{ scope.get_device_by_index(vdus.device).name }.vnc");
]).controller("icswUserIndexCtrl", ["$scope", "$timeout", "$window", "ICSW_URLS",
    ($scope, $timeout, $window, ICSW_URLS) ->
        $scope.ICSW_URLS = ICSW_URLS
        $scope.show_index = true
        $scope.quick_open = true
        $scope.ext_open = false
        $scope.diskusage_open = true
        $scope.vdesktop_open = true
        $scope.jobinfo_open = true
        $scope.show_devices = false
        $scope.CLUSTER_LICENSE = $window.CLUSTER_LICENSE
        $scope.GLOBAL_PERMISSIONS = $window.GLOBAL_PERMISSIONS
        $scope.OBJECT_PERMISSIONS = $window.OBJECT_PERMISSIONS
        $scope.NUM_QUOTA_SERVERS = $window.NUM_QUOTA_SERVERS
        $scope.check_perm = (p_name) ->
            if p_name of GLOBAL_PERMISSIONS
                return true
            else if p_name of OBJECT_PERMISSIONS
                return true
            else
                return false
]).directive("indexView", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.user.index")
        link : (scope, element, attrs) ->
    }
])

virtual_desktop_utils = {
    get_viewer_command_line: (vdus, ip) ->
        return "echo \"#{vdus.password}\" | vncviewer -autopass #{ip}:#{vdus.effective_port }\n"
}