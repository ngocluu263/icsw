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

# login component

angular.module(
    "icsw.login",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "icsw.system.license", "icsw.layout.theme"
    ]
).controller("icswLoginCtrl",
[
    "$scope", "$window", "ICSW_URLS", "icswSimpleAjaxCall", "icswParseXMLResponseService", "blockUI",
    "initProduct", "icswSystemLicenseDataService", "$q", "$state", "icswCSRFService", "icswUserService",
    "icswToolsSimpleModalService", "setDefaultTheme",
(
    $scope, $window, ICSW_URLS, icswSimpleAjaxCall, icswParseXMLResponseService, blockUI,
    initProduct, icswSystemLicenseDataService, $q, $state, icswCSRFService, icswUserService,
    icswToolsSimpleModalService, setDefaultTheme
) ->
    $scope.initProduct = initProduct
    $scope.license_tree = undefined
    $scope.django_version = "---"
    $scope.login_hints = []
    first_call = true
    $scope.struct = {
        # fx mode
        fx_mode: false
        # data valid
        data_valid: false
        # cluster data
        cluster_data: undefined
        # login form disabled
        disabled: true
    }
    $scope.init_login = () ->
        $q.all(
            [
                icswSimpleAjaxCall(
                    {
                        url: ICSW_URLS.SESSION_LOGIN_ADDONS
                    }
                )
                icswSimpleAjaxCall(
                    {
                        url: ICSW_URLS.MAIN_GET_CLUSTER_INFO
                        dataType: "json"
                    }
                )
                icswSystemLicenseDataService.load($scope.$id)
            ]
        ).then(
            (data) ->
                xml = data[0]
                setDefaultTheme($(xml).find("value[name='theme_default']").text())
                $scope.login_hints = angular.fromJson($(xml).find("value[name='login_hints']").text())
                $scope.django_version = $(xml).find("value[name='django_version']").text()
                $scope.struct.disabled = false
                $scope.struct.cluster_data = data[1]
                $scope.license_tree = data[2]
                $scope.struct.fx_mode = icswSystemLicenseDataService.fx_mode()
                $scope.struct.data_valid = true
                if first_call
                    first_call = false
                    $scope.login_data.next_url = $(xml).find("value[name='next_url']").text()
        )
        $scope.login_data = {
            username: ""
            password: ""
            next_url: ""
        }

    $scope.do_login = () ->
        blockUI.start("Logging in...")
        icswSimpleAjaxCall(
            {
                url: ICSW_URLS.SESSION_LOGIN
                data:
                    blob: angular.toJson($scope.login_data)
            }
        ).then(
            (xml) ->
                # blockUI.stop()
                if $(xml).find("value[name='redirect']").length
                    _val = $(xml).find("value[name='redirect']").text()
                    # clear token
                    icswCSRFService.clear_token()
                    dup_sessions = parseInt($(xml).find("value[name='duplicate_sessions']").text())
                    _do_login = $q.defer()
                    if dup_sessions
                        blockUI.stop()
                        icswToolsSimpleModalService("Another user is already using this account, continue ?").then(
                            (doit) ->
                                blockUI.start("expelling other users")
                                icswSimpleAjaxCall(
                                    url: ICSW_URLS.SESSION_EXPEL
                                    dataType: "json"
                                ).then(
                                    (expelled) ->
                                        console.log "expelled=", expelled
                                        _do_login.resolve("login")
                                )
                            (nono) ->
                                blockUI.start("logging out")
                                _do_login.reject("nologin")
                        )
                    else
                        _do_login.resolve("nodups")
                    _do_login.promise.then(
                        (login) ->
                            $q.all(
                                [
                                    icswCSRFService.get_token()
                                    icswUserService.load()
                                ]
                            ).then(
                                (data) ->
                                    csrf_token = data[0]
                                    _user = data[1].user
                                    blockUI.stop()
                                    $state.go(_val)
                            )
                        (nologin) ->
                            icswSimpleAjaxCall(
                                url: ICSW_URLS.SESSION_LOGOUT
                                dataType: "json"
                            ).then(
                                (logout) ->
                                    _do_login.reject("login")
                                    $scope.init_login()
                                    blockUI.stop()
                            )
                    )
            (error) ->
                blockUI.stop()
                $scope.init_login()
        )
    $scope.init_login()
]).directive("icswLoginForm",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.authentication.form")
    }
]).directive("icswLoginPage",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.user.login.page")
        controller: "icswLoginCtrl"
    }
])