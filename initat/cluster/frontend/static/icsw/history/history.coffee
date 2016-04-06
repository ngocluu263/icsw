# Copyright (C) 2012-2016 init.at
#
# Send feedback to: <mallinger@init.at>
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
    "icsw.history",
    []
).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.history", {
            url: "/history"
            template: "<icsw-history-overview></icsw-history-overview>"
            data:
                pageTitle: "Database history"
                rights: ["user.snapshots"]
                menuEntry:
                    menukey: "sys"
                    name: "History"
                    icon: "fa-history"
                    ordering: 10
        }
    )
]).directive("icswHistoryOverview",
[
    'icswHistoryDataService',
(
    icswHistoryDataService
) ->
    return  {
        restrict: 'EA'
        templateUrl: 'icsw.history.overview'
        link: (scope, el, attrs) ->
            scope.struct = {
                loading: true
                models_with_history_sorted: []
                selected_model: "device"
            }
            icswHistoryDataService.get_models_with_history().then(
                (data) ->
                    _list = []
                    for key, value of data.plain()
                        _list.push([value, key])
                    _list.sort()
                    scope.struct.models_with_history_sorted = _list
                    scope.struct.loading = false
            )
            icswHistoryDataService.add_to_scope(scope)
    }
]).service("icswHistoryDataService",
[
    "Restangular", "ICSW_URLS", "$rootScope", "$q",
(
    Restangular, ICSW_URLS, $rootScope, $q
) ->
    get_historic_data = (model_name, object_id) ->
        params = {
            model: model_name,
            object_id: object_id,
        }
        return Restangular.all(ICSW_URLS.SYSTEM_GET_HISTORICAL_DATA.slice(1)).getList(params)

    user = Restangular.all(ICSW_URLS.REST_USER_LIST.slice(1)).getList().$object

    get_models_with_history = () ->
        defer = $q.defer()
        Restangular.all(ICSW_URLS.SYSTEM_GET_MODELS_WITH_HISTORY.slice(1)).customGET().then(
            (data) ->
                defer.resolve(data)
        )
        return defer.promise

    get_user_by_idx = (idx) -> return _.find(user, (elem) -> return elem.idx == idx)

    return {
        get_historic_data: get_historic_data
        get_models_with_history: () ->
            return get_models_with_history()
        user:  user
        get_user_by_idx: get_user_by_idx
        add_to_scope: (scope) ->
            scope.user = user
            scope.get_user_by_idx = get_user_by_idx
    }
]).directive("icswHistoryModelHistory",
[
    "icswHistoryDataService",
(
    icswHistoryDataService
) ->
    return {
        restrict: 'EA'
        templateUrl: 'icsw.history.model_history'
        scope: {
            icsw_model: '=icswModel'
            objectId: '&'
            onRevert: '&'
            style: '@'  # 'config', 'history'
        }
        link: (scope, el, attrs) ->
            scope.on_revert_defined = attrs.onRevert
            icswHistoryDataService.add_to_scope(scope)
            scope.$watch(
                () ->
                    [scope.icsw_model, scope.objectId]
                () ->
                    console.log scope.icsw_model
                    if scope.icsw_model?
                        model_for_callback = scope.icsw_model
                        icswHistoryDataService.get_historic_data(scope.icsw_model, scope.objectId()).then(
                            (new_data) ->
                                # loading takes a while, check if the user has changed the selection meanwhile
                                if model_for_callback == scope.icsw_model
                                    # don't show empty changes
                                    scope.entries = (entry for entry in new_data when entry.meta.type != 'modified' || Object.keys(entry.changes).length > 0)
                                    # NOTE: entries must be in chronological, earliest first
                    )
                true
            )

            scope.format_value = (val) ->
                if angular.isArray(val)
                    if val.length > 0
                        return val.join(", ")
                    else
                        return "no entries"
                else
                    return val

            scope.get_get_change_list = (limit_entry) ->
                # pass as function such that we don't need to generate everything
                return () ->
                    # return in order of original application
                    changes = []
                    for entry in scope.entries
                        changes.push(entry.changes)
                        if entry == limit_entry
                            break
                    return changes
    }
])
