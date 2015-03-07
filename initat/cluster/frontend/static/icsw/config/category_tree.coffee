
angular.module(
    "icsw.config.category_tree",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "ui.select", "restangular", "uiGmapgoogle-maps", "angularFileUpload"
    ]
).controller("icswConfigCategoryTreeCtrl", [
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "$window", "$timeout",
    "$q", "$modal", "access_level_service", "FileUploader", "blockUI", "icswTools", "ICSW_URLS", "icswConfigCategoryTreeService",
    "icswCallAjaxService", "icswParseXMLResponseService", "toaster",
   ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, $window, $timeout, $q, $modal, access_level_service,
    FileUploader, blockUI, icswTools, ICSW_URLS, icswConfigCategoryTreeService, icswCallAjaxService, icswParseXMLResponseService, toaster) ->
        $scope.cat = new icswConfigCategoryTreeService($scope, {})
        $scope.pagSettings = paginatorSettings.get_paginator("cat_base", $scope)
        $scope.entries = []
        # mixins
        # edit mixin for cateogries
        $scope.edit_mixin = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular, $q, "cat")
        $scope.edit_mixin.use_modal = false
        $scope.edit_mixin.use_promise = true
        $scope.edit_mixin.new_object = (scope) -> return scope.new_object()
        $scope.edit_mixin.delete_confirm_str = (obj) -> return "Really delete category node '#{obj.name}' ?"
        $scope.edit_mixin.modify_rest_url = ICSW_URLS.REST_CATEGORY_DETAIL.slice(1).slice(0, -2)
        $scope.edit_mixin.create_rest_url = Restangular.all(ICSW_URLS.REST_CATEGORY_LIST.slice(1))
        $scope.edit_mixin.edit_template = "category.form"
        # edit mixin for location gfxs
        $scope.gfx_mixin = new angular_edit_mixin($scope, $templateCache, $compile, $modal, Restangular, $q, "gfx")
        $scope.gfx_mixin.use_modal = true
        $scope.gfx_mixin.use_promise = true
        $scope.gfx_mixin.new_object = (scope) -> return scope.new_location_gfx()
        $scope.gfx_mixin.delete_confirm_str = (obj) -> return "Really delete location graphic '#{obj.name}' ?"
        $scope.gfx_mixin.modify_rest_url = ICSW_URLS.REST_LOCATION_GFX_DETAIL.slice(1).slice(0, -2)
        $scope.gfx_mixin.create_rest_url = Restangular.all(ICSW_URLS.REST_LOCATION_GFX_LIST.slice(1))
        $scope.gfx_mixin.create_template = "location.gfx.form"
        $scope.gfx_mixin.edit_template = "location.gfx.form"
        $scope.form = {}
        $scope.locations = []
        $scope.uploader = new FileUploader(
            scope : $scope
            url : ICSW_URLS.BASE_UPLOAD_LOCATION_GFX
            queueLimit : 1
            alias : "gfx"
            formData : [
                 "location_id" : 0
                 "csrfmiddlewaretoken" : $window.CSRF_TOKEN
            ]
            removeAfterUpload : true
        )
        $scope.upload_list = []
        $scope.uploader.onBeforeUploadItem = (item) ->
            item.formData[0].location_id = $scope.cur_location_gfx.idx
            blockUI.start()
        $scope.uploader.onCompleteAll = () ->
            blockUI.stop()
            $scope.uploader.clearQueue()
            return null
        $scope.uploader.onErrorItem = (item, response, status, headers) ->
            blockUI.stop()
            $scope.uploader.clearQueue()
            toaster.pop("error", "", "error uploading file, please check logs", 0)
            return null
        $scope.uploader.onCompleteItem = (item, response, status, headers) ->
            xml = $.parseXML(response)
            if icswParseXMLResponseService(xml)
                Restangular.one(ICSW_URLS.REST_LOCATION_GFX_DETAIL.slice(1).slice(0, -2), $scope.cur_location_gfx.idx).get().then((data) ->
                    for _copy in ["width", "height", "uuid", "content_type", "locked", "image_stored", "icon_url", "image_name", "image_url"]
                        $scope.cur_location_gfx[_copy] = data[_copy]
                )
        $scope.map = {
            center: {
                latitude: 4
                longitude: 7
            }
            zoom: 2
            control: {}
            options: {
                "streetViewControl": false
                "minZoom" : 1
                "maxZoom" : 20
            }
            marker: {
                events:{
                    dragend: (marker, event_name, args) ->
                        _pos = marker.getPosition()
                        _cat = $scope.marker_lut[marker.key]
                        _cat.latitude = _pos.lat()
                        _cat.longitude = _pos.lng()
                        _cat.put()
                }
            }
            bounds: {
                "northeast" : {
                    "latitude": 4
                    "longitude": 4
                }
                "southwest": {
                    "latitude": 20
                    "longitude": 30
                }
                "ne" : {
                    "latitude": 4
                    "longitude": 4
                }
                "sw": {
                    "latitude": 20
                    "longitude": 30
                }
            }
        }
        $scope.reload = () ->
            wait_list = [
                restDataSource.reload([ICSW_URLS.REST_CATEGORY_LIST, {}])
                restDataSource.reload([ICSW_URLS.REST_LOCATION_GFX_LIST, {}])
                restDataSource.reload([ICSW_URLS.REST_DEVICE_MON_LOCATION_LIST])
            ]
            $q.all(wait_list).then((data) ->
                $scope.entries = data[0]
                for entry in $scope.entries
                    entry.open = false
                $scope.location_gfxs = data[1]
                $scope.dml_list = data[2]
                $scope.edit_mixin.create_list = $scope.entries
                $scope.edit_mixin.delete_list = $scope.entries
                $scope.rebuild_cat()
        )
        if false
            $scope.redrawn = {"test" : 0}
            _el = $compile("<icsw-device-livestatus-brief devicepk='3' redraw-sunburst='redrawn.test'></icsw-device-livestatus-brief>")($scope)
            $scope.$watch('redrawn.test', (new_val) ->
                if new_val
                    $timeout(
                        () ->
                            icswCallAjaxService
                                url : ICSW_URLS.MON_SVG_TO_PNG
                                data :
                                    svg : _el[0].innerHTML
                                success : (xml) ->
                                    if icswParseXMLResponseService(xml)
                                        _url = ICSW_URLS.MON_FETCH_PNG_FROM_CACHE.slice(0, -1) + $(xml).find("value[name='cache_key']").text()
                                        $scope.$apply(
                                            for loc in $scope.locations
                                                # do not set _icon
                                                loc._icon = _url
                                        )
                    )
            )
        $scope.edit_obj = (cat, event) ->
            $scope.create_mode = false
            $scope.cat.clear_active()
            $scope.cat_lut[cat.idx].active = true
            $scope.cat.show_active()
            pre_parent = cat.parent
            $scope.edit_mixin.edit(cat, event).then((data) ->
                if data.parent == pre_parent
                    $scope.cat.iter(
                        (entry) ->
                            if entry.parent and entry.parent.obj.name
                                entry.obj.full_name = "#{entry.parent.obj.full_name}/#{entry.obj.name}"
                            else
                                entry.obj.full_name = "/#{entry.obj.name}"
                    )
                    $scope.build_markers()
                else
                    $scope.reload()
            )
        $scope.delete_obj = (obj) ->
            $scope.edit_mixin.delete_obj(obj).then((data) ->
                if data
                    $scope.rebuild_cat()
                    $scope.cat.clear_active()
            )
        $scope.rebuild_cat = () ->
            # check location gfx refs
            $scope.gfx_lut = icswTools.build_lut($scope.location_gfxs)
            for entry in $scope.location_gfxs
                entry.num_dml = 0
            for entry in $scope.dml_list
                $scope.gfx_lut[entry.location_gfx].num_dml++
            cat_lut = {}
            $scope.cat.clear_root_nodes()
            for entry in $scope.entries
                t_entry = $scope.cat.new_node({folder:false, obj:entry, expand:entry.depth < 2, selected: entry.immutable})
                cat_lut[entry.idx] = t_entry
                if $scope.is_location(entry)
                    entry.location_gfxs = (_gfx for _gfx in $scope.location_gfxs when _gfx.location == entry.idx)
                if entry.parent
                    cat_lut[entry.parent].add_child(t_entry)
                else
                    $scope.cat.add_root_node(t_entry)
            $scope.cat_lut = cat_lut
            $scope.build_markers()
        $scope.get_valid_locations = () ->
            return (entry for entry in $scope.entries when entry.depth > 1 and entry.full_name.split("/")[1] == "location" and entry.latitude and entry.longitude)
        $scope.build_markers = () ->
            new_list = []
            marker_lut = {}
            for _entry in $scope.get_valid_locations()
                new_list.push(
                    {
                        "latitude": _entry.latitude
                        "longitude": _entry.longitude
                        "key": _entry.idx
                        "comment": if _entry.comment then "#{_entry.name} (#{_entry.comment})" else _entry.name
                        "options": {
                            "draggable": not _entry.locked
                            "title": _entry.full_name
                        }
                        "icon": null
                    }
                )
                marker_lut[_entry.idx] = _entry
            $scope.locations = new_list
            $scope.marker_lut = marker_lut
        $scope.locate = (loc, $event) ->
            $scope.map.control.refresh({"latitude":loc.latitude, "longitude":loc.longitude})
            $scope.map.control.getGMap().setZoom(11)
            $event.stopPropagation()
            $event.preventDefault()
        $scope.toggle_lock = ($event, loc) ->
            loc.locked = !loc.locked
            loc.put()
            _entry = (entry for entry in $scope.locations when entry.key == loc.idx)[0]
            _entry.options.draggable = not loc.locked
            $event.stopPropagation()
            $event.preventDefault()
        $scope.new_object = () ->
            if $scope.new_top_level
                _parent = (value for value in $scope.entries when value.depth == 1 and value.name == $scope.new_top_level)[0]
                _name = "new_#{_parent.name}"
                r_struct = {"name" : _name, "parent" : _parent.idx, "depth" : 2, "full_name" : "/#{$scope.new_top_level}/#{_name}"}
                if $scope.new_top_level == "location"
                    r_struct["latitude"] = 48.1
                    r_struct["longitude"] = 16.3
                return r_struct
            else
                return {"name" : "new_cat", "depth" : 2, "full_name" : ""}
        $scope.create_new = ($event, top_level) ->
            $scope.create_mode = true
            $scope.new_top_level = top_level
            $scope.cat.clear_active()
            $scope.edit_mixin.create($event).then((data) ->
                $scope.reload()
            )
        $scope.get_valid_parents = (obj) ->
            if obj.idx
                # object already saved, do not move beteen top categories
                top_cat = new RegExp("^/" + obj.full_name.split("/")[1])
                p_list = (value for value in $scope.entries when value.depth and top_cat.test(value.full_name))
                # remove all nodes below myself
                r_list = []
                add_list = [$scope._edit_obj.idx] 
                while add_list.length
                    r_list = r_list.concat(add_list)
                    add_list = (value.idx for value in p_list when (value.parent in r_list and value.idx not in r_list))
                p_list = (value for value in p_list when value.idx not in r_list)
            else
                # new object, allow all values
                p_list = (value for value in $scope.entries when value.depth)
            return p_list
        $scope.is_location = (obj) ->
            # full_name.match leads to infinite digest cycles
            return (obj.depth > 1) and obj.full_name.split("/")[1] == "location"
        $scope.close_modal = () ->
            $scope.cat.clear_active()
            if $scope.cur_edit
                $scope.cur_edit.close_modal()
        $scope.prune_tree = () ->
            $scope.cat.clear_active()
            $scope.close_modal()
            $modal.open(
                template : $templateCache.get("icsw.tools.simple.modal")
                controller : ($scope, $modalInstance, question) ->
                    $scope.question = question
                    $scope.ok = () ->
                        $modalInstance.close(true)
                    $scope.cancel = () ->
                        $modalInstance.dismiss("cancel")
                backdrop : "static"
                resolve :
                    question : () =>
                            return "Really prune tree (delete empty elements) ?"
            ).result.then(
                () =>
                    blockUI.start()
                    icswCallAjaxService
                        url     : ICSW_URLS.BASE_PRUNE_CATEGORIES
                        success : (xml) ->
                            icswParseXMLResponseService(xml)
                            $scope.reload()
                            blockUI.stop()
            )
        $scope.new_location_gfx = () ->
            # return empty location_gfx for current location
            return {
                "location" : $scope.loc_gfx_mother.idx
            }
            
        $scope.add_location_gfx = ($event, loc) ->
            $scope.preview_gfx = undefined
            $scope.loc_gfx_mother = loc
            $scope.gfx_mixin.create($event).then((data) ->
                data.num_dml = 0
                loc.location_gfxs.push(data)
            )
            $event.stopPropagation()
            $event.preventDefault()
        $scope.modify_location_gfx = ($event, loc) ->
            $scope.preview_gfx = undefined
            $scope.cur_location_gfx = loc
            $scope.gfx_mixin.edit(loc, $event).then((data) ->
            )
        $scope.delete_location_gfx = ($event, obj) ->
            # find location object via cat_lut
            loc = $scope.cat_lut[obj.location].obj
            $scope.preview_gfx = undefined
            $scope.gfx_mixin.delete_obj(obj).then((data) ->
                if data
                    loc.location_gfxs = (entry for entry in loc.location_gfxs when entry.idx != obj.idx)
            )
        $scope.show_preview = (obj) ->
            $scope.preview_gfx = obj
        $scope.rotate = (obj, degrees) ->
            $scope.modify_image(
                 obj
                 {
                    "id": obj.idx
                    "mode": "rotate"
                    "degrees" : degrees
                 }
            )
        $scope.brightness = (obj, factor) ->
            $scope.modify_image(
                 obj
                 {
                    "id": obj.idx
                    "mode": "brightness"
                    "factor" : factor
                 }
            )
        $scope.sharpen = (obj, factor) ->
            $scope.modify_image(
                 obj
                 {
                    "id": obj.idx
                    "mode": "sharpen"
                    "factor" : factor
                 }
            )
        $scope.restore = (obj) ->
            $scope.modify_image(obj, "restore")
        $scope.undo = (obj) ->
            $scope.modify_image(obj, "undo")
        $scope.emboss = (obj) ->
            $scope.modify_image(obj, "emboss")
        $scope.contour = (obj) ->
            $scope.modify_image(obj, "contour")
        $scope.edge_enhance = (obj) ->
            $scope.modify_image(obj, "edge_enhance")
        $scope.find_edges = (obj) ->
            $scope.modify_image(obj, "find_edges")
        $scope.modify_image = (obj, data) ->
            $scope.show_preview(obj)
            if angular.isString(data)
                data = {"id" : obj.idx, "mode": data}
            blockUI.start()
            icswCallAjaxService
                url : ICSW_URLS.BASE_MODIFY_LOCATION_GFX
                data: data
                success: (xml) ->
                    blockUI.stop()
                    if icswParseXMLResponseService(xml)
                        $scope.$apply(() ->
                            obj.image_url = $(xml).find("value[name='image_url']").text()
                            obj.icon_url = $(xml).find("value[name='icon_url']").text()
                        )
        $scope.reload()
]).service("icswConfigCategoryTreeService", () ->
    class category_tree_edit extends tree_config
        constructor: (@scope, args) ->
            super(args)
            @show_selection_buttons = false
            @show_icons = false
            @show_select = false
            @show_descendants = true
            @show_childs = false
            @location_re = new RegExp("^/location/.*$")
        get_name : (t_entry) ->
            cat = t_entry.obj
            is_loc = @location_re.test(cat.full_name)
            if cat.depth > 1
                r_info = "#{cat.full_name} (#{cat.name})"
                if cat.num_refs
                    r_info = "#{r_info} (refs=#{cat.num_refs})"
                if is_loc
                    if cat.physical
                        r_info = "#{r_info}, physical"
                    else
                        r_info = "#{r_info}, structural"
                    if cat.locked
                        r_info = "#{r_info}, locked"
            else if cat.depth
                r_info = cat.full_name
            else
                r_info = "TOP"
            return r_info
        handle_click: (entry, event) =>
            @clear_active()
            cat = entry.obj
            if cat.depth > 1
                @scope.edit_obj(cat, event)
            else if cat.depth == 1
                @scope.create_new(event, cat.full_name.split("/")[1])

).directive("icswConfigCategoryTreeHead", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.category.tree.head")
    }
]).directive("icswConfigCategoryTreeRow", ["$templateCache", ($templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.category.tree.row")
        link : (scope, el, attrs) ->
            scope.get_tr_class = (obj) ->
                return if obj.depth > 1 then "" else "success"
            scope.get_space = (depth) ->
                return ("&nbsp;&nbsp;" for idx in [0..depth]).join("")
    }
]).directive("icswConfigCategoryTreeEditTemplate", ["$compile", "$templateCache", ($compile, $templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("category.form")
        link : (scope, element, attrs) ->
            scope.form_error = (field_name) ->
                if scope.form[field_name].$valid
                    return ""
                else
                    return "has-error"
    }
]).directive("icswConfigCategoryTree", ["$compile", "$templateCache", ($compile, $templateCache) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.config.category.tree")
    }
])
