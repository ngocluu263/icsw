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

# unified button for angular

angular.module(
    "icsw.tools.button",
    []
).service('icswToolsButtonConfigService',
[
    'gettextCatalog',
(
    gettextCatalog
) ->
    get_config_for_button_type = (type) ->
        ret_obj = {}
        if type == "modify"
            ret_obj.css_class = "btn-primary"
            ret_obj.button_value = gettextCatalog.getString("modify")
            ret_obj.icon_class = "fa fa-wrench"
        else if type == "change"
            ret_obj.css_class = "btn-warning"
            ret_obj.button_value = "change"
            ret_obj.icon_class = "fa fa-wrench"
        else if type == "create"
            ret_obj.css_class = "btn-success"
            ret_obj.button_value = gettextCatalog.getString("create")
            ret_obj.icon_class = "fa fa-plus-circle"
        else if type == "delete"
            ret_obj.css_class = "btn-danger"
            ret_obj.button_value = gettextCatalog.getString("delete")
            ret_obj.icon_class = "fa fa-trash"
        else if type == "reload"
            ret_obj.css_class = "btn-warning"
            ret_obj.button_value = gettextCatalog.getString("reload")
            ret_obj.icon_class = "fa fa-refresh"
        else if type == "copy"
            ret_obj.css_class = "btn-success"
            ret_obj.button_value = "copy"
            ret_obj.icon_class = "fa fa-copy"
        else if type == "stop"
            ret_obj.css_class = "btn-warning"
            ret_obj.button_value = gettextCatalog.getString("stop")
            ret_obj.icon_class = "fa fa-hand-stop-o"
        else if type == "clear_selection"
            ret_obj.css_class = "btn-warning"
            ret_obj.button_value = gettextCatalog.getString("clear selection")
            ret_obj.icon_class = "fa fa-remove"
        else if type == "show"
            ret_obj.css_class = "btn-success"
            ret_obj.icon_class = ""
        else if type == "toggle"
            ret_obj.css_class = "btn-primary"
            ret_obj.icon_class = "fa fa-refresh"
        else if type == "enable"
            ret_obj.icon_class = "fa fa-check"
            ret_obj.button_value = "enable"
            ret_obj.css_class = "btn-ok"
        else if type == "lock"
            ret_obj.icon_class = "fa fa-lock"
            ret_obj.button_value = "lock"
            ret_obj.css_class = "btn-ok"
        else if type == "disable"
            ret_obj.css_class = "btn-danger"
            ret_obj.button_value = "disable"
            ret_obj.icon_class = "fa fa-ban"
        else if type == "close"
            ret_obj.css_class = "btn-warning"
            ret_obj.button_value = "close"
            ret_obj.icon_class = "fa fa-close"
        else if type == "info"
            ret_obj.css_class = "btn-info"
            ret_obj.icon_class = "fa fa-search"
        else if type == "display"
            ret_obj.css_class = "btn-info"
            ret_obj.icon_class = "fa fa-search"
        else if type == "search"
            ret_obj.css_class = "btn-primary"
            ret_obj.icon_class = "fa fa-search"
        else if type == "draw"
            ret_obj.css_class = "btn-primary"
            ret_obj.icon_class = "fa fa-pencil"
        else if type == "download"
            ret_obj.css_class = "btn-success"
            ret_obj.button_value = gettextCatalog.getString("download")
            ret_obj.icon_class = "fa fa-download"
        else if type == "upload"
            ret_obj.css_class = "btn-success"
            ret_obj.button_value = gettextCatalog.getString("upload")
            ret_obj.icon_class = "fa fa-upload"
        else if type == "revert"
            ret_obj.css_class = "btn-warning"
            ret_obj.button_value = "revert"
            ret_obj.icon_class = "fa fa-undo"
        else if type == "submit"
            ret_obj.css_class = "btn-primary"
            ret_obj.button_value = gettextCatalog.getString("submit")
            ret_obj.icon_class = "fa fa-arrow-circle-right"
        else if type == "save"
            ret_obj.css_class = "btn-success"
            ret_obj.button_value = "save"
            ret_obj.icon_class = "fa fa-save"
        else if type == "select_devices"
            ret_obj.css_class = "btn-primary"
            ret_obj.button_value = "select devices"
            ret_obj.icon_class = "fa fa-desktop"
        else if type == "select_parent"
            ret_obj.css_class = "btn-success"
            ret_obj.button_value = "select devices"
            ret_obj.icon_class = "fa fa-power-off"
        else if type == "bump"
            ret_obj.css_class = "btn-warning"
            ret_obj.button_value = "bump"
            ret_obj.icon_class = "glyphicon glyphicon-arrow-up"
        else if type == "image"
            ret_obj.css_class = "btn-success"
            ret_obj.button_value = "build image"
            ret_obj.icon_class = "glyphicon glyphicon-hdd"
        else
            console.error "Invalid button type: #{type}"
        return ret_obj
    return {
        get_config_for_button_type:
            get_config_for_button_type
        get_css_class: (type) ->
            return get_config_for_button_type(type).css_class
        get_icon_class: (type) ->
            return get_config_for_button_type(type).icon_class
        get_css_and_icon_class: (type) ->
            conf = get_config_for_button_type(type)
            return conf.css_class + " " + conf.icon_class
    }
]).directive("icswToolsYesNo", [() ->
    return {
        restict: "EA"
        template: """
<button class="btn btn-xs form-control" ng-class="get_class()" style="width:100px;" ng-click="change_value($event)"> {{ get_value() }} </button>
"""
        scope:
            flag: "="
        link: (scope, element, attrs) ->
            _yes_value = if attrs.icswYes? then attrs.icswYes else "yes"
            _no_value = if attrs.icswNo? then attrs.icswNo else "no"
            if attrs.disabled?
                _disabled = true
            else
                _disabled = false
            scope.change_value = ($event) ->
                if not _disabled
                    scope.flag = !scope.flag
                $event.preventDefault()

            scope.get_value = () ->
                return if scope.flag then _yes_value else _no_value

            scope.get_class = () ->
                return if scope.flag then "btn-success" else "btn-default"
    }
]).directive("icswToolsYesNoSmall", [() ->
    return {
        restict: "EA"
        template: """
<button class="btn btn-xs btn-default" ng-class="get_class()" style="width:50px;" ng-click="change_value($event)">{{ get_value() }}</button>
"""
        scope:
            flag: "="
        link: (scope, element, attrs) ->
            _yes_value = if attrs.icswYes? then attrs.icswYes else "yes"
            _no_value = if attrs.icswNo? then attrs.icswNo else "no"
            scope.change_value = ($event) ->
                if not attrs.ngClick?
                    # ngClick not defined in attributes
                    scope.flag = !scope.flag
                $event.preventDefault()

            scope.get_value = () ->
                return if scope.flag then _yes_value else _no_value

            scope.get_class = () ->
                return if scope.flag then "btn-success" else "btn-default"
    }
]).directive('icswToolsButton',
[
    "icswToolsButtonConfigService", "gettextCatalog",
(
    icswToolsButtonsConfigService, gettextCatalog
) ->
    return {
        restrict: "EA",
        template: """
    <button ng-attr-type="{{ button_type }}" name="button" class="btn {{ css_class }} {{ additional_class }} {{ icon_class }}"
            ng-disabled="is_disabled">
        {{ button_value }}
    </button>
<!--
Disabled for now as it forces a line break (cf. monitoring basic setup)
visible-md visible-lg
    <button ng-attr-type="{{button_type}}" name="button" class="hidden-md hidden-lg btn {{css_class}} {{additional_class}} {{icon_class}}" title="{{ button_value }}">
    </button>
-->
    """
        scope:
            isShow: '&'
            disabled: '&'
            isEnable: '&'
            isLock: '&'
        link: (scope, element, attrs) ->

            # attrs:
            # - type (mandatory): "modify", "create", "delete", "reload", "show", "clear_selection", "download"
            # - button-type: inserted into type, so use "button" or "submit" (default is "button")
            # - size: inserted into "btn-{{size}}", no default
            # - value: Custom text to display in button
            # - showValue: Custom text to show for show buttons if state is show
            # - hideValue: Custom text to show for show buttons if state is hide
            # - disabled: whether button is enabled

            b_type = attrs.type
            angular.extend(scope, icswToolsButtonsConfigService.get_config_for_button_type(b_type))

            if attrs.value?
                scope.button_value = attrs.value

            if attrs.buttonType?
                scope.button_type = attrs.buttonType
            else
                scope.button_type = "button"

            if attrs.size?
                scope.additional_class = "btn-" + attrs.size
            else
                scope.additional_class = ""

            if attrs.disabled?
                scope.$watch(
                    () ->
                        return scope.disabled()
                    (new_val) ->
                        scope.is_disabled = new_val
                )

            if attrs.type == "show"
                scope.$watch(
                    scope.isShow
                    (new_val) ->
                        if new_val
                            scope.button_value = attrs.showValue or gettextCatalog.getString("show")
                        else
                            scope.button_value = attrs.hideValue or gettextCatalog.getString("hide")
                )
            else if attrs.type == "enable"
                scope.$watch(
                    scope.isEnable
                    (new_val) ->
                        if new_val
                            scope.button_value = gettextCatalog.getString("disable")
                            scope.css_class = "btn-warning"
                        else
                            scope.button_value = gettextCatalog.getString("enable")
                            scope.css_class = "btn-success"
                )
            else if attrs.type == "lock"
                scope.$watch(
                    scope.isLock
                    (new_val) ->
                        if new_val
                            scope.button_value = gettextCatalog.getString("unlock")
                            scope.css_class = "btn-warning"
                            scope.icon_class = "fa fa-unlock"
                        else
                            scope.button_value = gettextCatalog.getString("lock")
                            scope.css_class = "btn-success"
                            scope.icon_class = "fa fa-lock"
                )
    }
]).directive('icswToolsButtonStatic',
[
    "icswToolsButtonConfigService", "gettextCatalog",
(
    icswToolsButtonsConfigService, gettextCatalog
) ->
    # static button, doenst change its face during his lifetime
    return {
        restrict: "EA",
        template: '<button type="button" class="btn btn-default" ng-disabled="is_disabled">value</button>'
        link: (scope, element, attrs) ->
            # attrs:
            # - type (mandatory): "modify", "create", "delete", "reload", "show", "clear_selection", "download"
            # - size: inserted into "btn-{{size}}", no default
            # - value: Custom text to display in button

            settings = icswToolsButtonsConfigService.get_config_for_button_type(attrs.type)

            if attrs.value?
                value = attrs.value
            else
                value = settings.button_value
            element.text(value)
            element.addClass("btn " + settings.css_class + " " + settings.icon_class)
            if attrs.size?
                element.addClass("btn-#{attrs.size}")

    }
])
