# Copyright (C) 2016 init.at
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

# asset related backend functions

device_asset_module = angular.module(
    "icsw.backend.asset",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "ngCsv"
    ]
).service("icswAssetPackageTree",
[
    "$q", "Restangular", "ICSW_URLS", "icswAssetHelperFunctions", "icswTools",
(
    $q, Restangular, ICSW_URLS, icswAssetHelperFunctions, icswTools,
) ->
    class icswAssetPackageTree
        constructor: (list) ->
            @list = []
            @version_list = []
            @update(list)

        update: (list) =>
            @list.length = 0
            @version_list.length = 0
            for entry in list
                @list.push(entry)
                for vers in entry.assetpackageversion_set
                    @version_list.push(vers)
            @build_luts()

        build_luts: () =>
            @lut = _.keyBy(@list, "idx")
            @version_lut = _.keyBy(@version_list, "idx")
            @link()

        link: () =>
            # DT_FORM = "dd, D. MMM YYYY HH:mm:ss"
            # _cf = ["year", "month", "week", "day", "hour", "minute", "second"]
            # create fields for schedule_setting form handling
            for entry in @list
                entry.$$num_versions = entry.assetpackageversion_set.length
                entry.$$package_type = icswAssetHelperFunctions.resolve("package_type", entry.package_type)
                entry.$$expanded = false
                entry.$$created = moment(entry.created).format("YYYY-MM-DD HH:mm:ss")
                for vers in entry.assetpackageversion_set
                    vers.$$package = entry
                    vers.$$created = moment(vers.created).format("YYYY-MM-DD HH:mm:ss")
                    vers.$$size = icswTools.get_size_str(vers.size, 1024, "Byte")


]).service("icswAssetPackageTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall", "icswTools",
    "icswAssetPackageTree", "icswTreeBase",
(
    $q, Restangular, ICSW_URLS, $window, icswCachingCall, icswTools,
    icswAssetPackageTree, icswTreeBase,
) ->
    rest_map = [
        # asset packages
        ICSW_URLS.ASSET_GET_ALL_ASSET_PACKAGES
    ]
    return new icswTreeBase(
        "AssetPackageTree"
        icswAssetPackageTree
        rest_map
        ""
    )
]).service("icswAssetHelperFunctions",
[
    "$q",
(
    $q,
) ->
    info_dict = {
        asset_type: [
            [1, "Package", ""]
            [2, "Hardware", ""]
            [3, "License", ""]
            [4, "Update", ""]
            [5, "Software version", ""]
            [6, "Process", ""]
            [7, "Pending update", ""]
            [8, "DMI", ""],
            [9, "PCI", ""],
            [10, "Windows Hardware", ""]
        ]
        package_type: [
            [1, "Windows", ""]
            [2, "Linux", ""]
        ]
        run_status: [
            [1, "Planned", ""]
            [2, "Running", "success"]
            [3, "Ended", ""]
        ]
        run_result: [
            [1, "Unknown", "warning"]
            [2, "Success", "success"]
            [3, "Success", "success"]
            [4, "Failed", "danger"]
            [5, "Canceled", "warning"]
        ]
        schedule_source: [
            [1, "SNMP", ""]
            [2, "ASU", ""]
            [3, "IPMI", ""]
            [4, "Package", ""]
            [5, "Hardware", ""]
            [6, "License", ""]
            [7, "Update", ""]
            [8, "Software Version", ""]
            [9, "Process", ""]
            [10, "Pending update", ""]
        ]
    }

    # create forward and backward resolves

    res_dict = {}
    for name, _list of info_dict
        res_dict[name] = {}
        for [_idx, _str, _class] in _list
            # forward resolve
            res_dict[name][_idx] = [_str, _class]
            # backward resolve
            res_dict[name][_str] = [_idx, _class]
            res_dict[name][_.lowerCase(_str)] = [_idx, _class]

    _resolve = (name, key, idx) ->
        if name of res_dict
            if key of res_dict[name]
                return res_dict[name][key][idx]
            else
                console.error "unknown key #{key} for name #{name} in resolve"
                return "???"
        else
            console.error "unknown name #{name} in resolve"
            return "????"

    return {
        resolve: (name, key) ->
            return _resolve(name, key, 0)

        get_class: (name, key) ->
            return _resolve(name, key, 1)
    }
]).service("icswStaticAssetTemplateTree",
[
    "$q", "Restangular", "ICSW_URLS", "icswTools", "icswSimpleAjaxCall", "icswStaticAssetFunctions",
(
    $q, Restangular, ICSW_URLS, icswTools, icswSimpleAjaxCall, icswStaticAssetFunctions,
) ->
    class icswStaticAssetTemplateTree
        constructor: (list) ->
            @list = []
            @update(list)

        update: (list) =>
            @list.length = 0
            for entry in list
                @list.push(entry)
            @build_luts()

        build_luts: () =>
            @lut = _.keyBy(@list, "idx")
            # field lut
            @field_lut = {}
            @static_asset_type_lut = {}
            for _struct in icswStaticAssetFunctions.get_form_dict("asset_type")
                _found = (entry for entry in @list when entry.type == _struct.idx)
                if _found.length
                    for _entry in _found
                        # set name
                        _entry.$$staticAssetType = _struct.name
                    @static_asset_type_lut[_struct.name] = _found
            for _template in @list
                for _field in _template.staticassettemplatefield_set
                    @field_lut[_field.idx] = _field
            @static_asset_type_keys = _.keys(@static_asset_type_lut)
            @static_asset_type_keys.sort()
            # list of (type, template_list) tuples
            @static_assets = []
            for _key in @static_asset_type_keys
                @static_assets.push([_key, @static_asset_type_lut[_key]])
            @link()

        link: () =>
            # DT_FORM = "dd, D. MMM YYYY HH:mm:ss"
            # _cf = ["year", "month", "week", "day", "hour", "minute", "second"]
            # create fields for schedule_setting form handling
            for entry in @list
                @salt_template(entry)

        salt_template: (entry) =>
            entry.$$num_fields = entry.staticassettemplatefield_set.length
            entry.$$asset_type = icswStaticAssetFunctions.resolve("asset_type", entry.type)
            entry.$$created = moment(entry.date).format("YYYY-MM-DD HH:mm:ss")
            for field in entry.staticassettemplatefield_set
                @salt_field(field)

        salt_field: (field) =>
            # salt static asset template field
            field.$$field_type = icswStaticAssetFunctions.resolve("field_type", field.field_type)
            if field.field_type == 3
                # date
                field.$$
            icswStaticAssetFunctions.get_default_value(field)

        copy_template: (src_obj, new_obj, create_user) =>
            defer = $q.defer()
            icswSimpleAjaxCall(
                {
                    url: ICSW_URLS.ASSET_COPY_STATIC_TEMPLATE
                    data:
                        new_obj: angular.toJson(new_obj)
                        src_idx: src_obj.idx
                        user_idx: create_user.idx
                    dataType: "json"
                }
            ).then(
                (result) =>
                    console.log "Result", result
                    @list.push(result)
                    @build_luts()
                    defer.resolve("created")
                (error) ->
                    defer.reject("not created")
            )
            return defer.promise

        create_template: (new_obj) =>
            d = $q.defer()
            Restangular.all(ICSW_URLS.ASSET_CREATE_STATIC_ASSET_TEMPLATE.slice(1)).post(new_obj).then(
                (created) =>
                    @list.push(created)
                    @build_luts()
                    d.resolve(created)
                (not_cr) =>
                    d.reject("not created")
            )
            return d.promise

        delete_template: (del_obj) =>
            d = $q.defer()
            Restangular.restangularizeElement(null, del_obj, ICSW_URLS.ASSET_STATIC_ASSET_TEMPLATE_DETAIL.slice(1).slice(0, -2))
            del_obj.remove().then(
                (removed) =>
                    _.remove(@list, (entry) -> return entry.idx == del_obj.idx)
                    @build_luts()
                    d.resolve("deleted")
                (not_removed) ->
                    d.resolve("not deleted")
            )
            return d.promise

        delete_field: (template, field) =>
            d = $q.defer()
            Restangular.restangularizeElement(null, field, ICSW_URLS.ASSET_STATIC_ASSET_TEMPLATE_FIELD_DETAIL.slice(1).slice(0, -2))
            field.remove(null, {"Content-Type": "application/json"}).then(
                (ok) =>
                    _.remove(template.staticassettemplatefield_set, (entry) -> return entry.idx == field.idx)
                    @salt_template(template)
                    d.resolve("ok")
                (notok) ->
                    d.reject("not ok")
            )
            return d.promise

        update_field: (template, field) =>
            d = $q.defer()
            Restangular.restangularizeElement(null, field, ICSW_URLS.ASSET_STATIC_ASSET_TEMPLATE_FIELD_DETAIL.slice(1).slice(0, -2))
            field.put(null, {"Content-Type": "application/json"}).then(
                (new_field) =>
                    _.remove(template.staticassettemplatefield_set, (entry) -> return entry.idx == field.idx)
                    template.staticassettemplatefield_set.push(new_field)
                    @salt_template(template)
                    d.resolve("ok")
                (notok) ->
                    d.reject("not ok")
            )
            return d.promise

        create_field: (template, field) =>
            d = $q.defer()
            Restangular.all(ICSW_URLS.ASSET_STATIC_ASSET_TEMPLATE_FIELD_CALL.slice(1)).post(field).then(
                (new_field) =>
                    template.staticassettemplatefield_set.push(new_field)
                    @salt_template(template)
                    d.resolve("ok")
                (notok) ->
                    d.reject("not ok")
            )
            return d.promise

        # device related calls
        build_asset_struct: (device) =>
            # return populated asset struture
            _asset_lut = {}
            for _as in device.staticasset_set
                _asset_lut[_as.static_asset_template] = _as
                @salt_device_asset(_as)

            _asset_struct = {
                used: []
                unused: []
                num_available: 0
            }
            for _asset in @list
                if _asset.idx of _asset_lut
                    _asset_struct.used.push(_asset_lut[_asset.idx])
                else
                    _asset_struct.unused.push(_asset)
            _asset_struct.num_available = (entry for entry in _asset_struct.unused when entry.enabled).length
            return _asset_struct

        salt_device_asset: (as) =>
            # salts StaticAsset of device
            as.$$static_asset_template = @lut[as.static_asset_template]
            info_f = []
            for _f in as.staticassetfieldvalue_set
                _f.$$field = @field_lut[_f.static_asset_template_field]
                _f.$$field_type_str = icswStaticAssetFunctions.resolve("field_type", _f.$$field.field_type)
                if _f.$$field.show_in_overview
                    info_f.push(_f.$$field.name + "=" + @get_field_display_value(_f, _f.$$field))
            if info_f.length
                as.$$field_info = info_f.join(", ")
            else
                as.$$field_info = "---"

        get_field_display_value: (field, temp_field) =>
            # console.log icswStaticAssetFunctions.resolve("field_type", temp_field.field_type)
            if temp_field.field_type == 1
                # integer
                return "#{field.value_int}"
            else if temp_field.field_type == 2
                # string
                return field.value_str
            else
                return moment(field.value_date).format("DD.MM.YYYY")

]).service("icswStaticAssetTemplateTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "$window", "icswCachingCall", "icswTools",
    "icswStaticAssetTemplateTree", "$rootScope", "ICSW_SIGNALS", "icswTreeBase",
(
    $q, Restangular, ICSW_URLS, $window, icswCachingCall, icswTools,
    icswStaticAssetTemplateTree, $rootScope, ICSW_SIGNALS, icswTreeBase,
) ->
    rest_map = [
        ICSW_URLS.ASSET_GET_STATIC_TEMPLATES
    ]
    return new icswTreeBase(
        "StaticAssetTemplateTree"
        icswStaticAssetTemplateTree
        rest_map
        ""
    )
])