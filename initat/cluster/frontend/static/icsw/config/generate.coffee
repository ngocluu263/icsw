config_gen_module = angular.module(
    "icsw.config.generate",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.codemirror"
    ]
).service("icswConfigConfigTreeService", () ->
    class config_tree extends tree_config
        constructor: (@scope, args) ->
            super(args)
            @show_selection_buttons = false
            @show_icons = true
            @show_select = false
            @show_descendants = false
            @show_childs = false
        get_name : (t_entry) ->
            switch t_entry._node_type
                when "eh"
                    return "errors"
                when "e"
                    return "config " + t_entry.obj.key
                when "c"
                    obj = t_entry.obj
                    content = obj.data
                    node_str = obj.name
                    attr_list = []
                    for attr_name in ["uid", "gid", "mode"]
                        if content[attr_name]?
                            attr_value = content[attr_name]
                            if attr_name == "mode"
                                attr_value = parseInt(attr_value).toString(8)
                            attr_list.push("#{attr_name}=#{attr_value}")
                    if attr_list
                        node_str = "#{node_str} (" + attr_list.join(", ") + ")"
                    return node_str
                else
                    return "unknown _node_type '#{t_entry._node_type}'"
        handle_click: (t_entry, event) =>
            @clear_selected()
            t_entry.selected = true
            switch t_entry._node_type
                when "eh"
                    @dev_conf.active_error = []
                when "e"
                    @dev_conf.active_error = t_entry.obj.text.split("\n")
                when "c"
                    content = t_entry.obj.data.content
                    if content?
                        @dev_conf.active_content = content.split("\n")
                    else
                        @dev_conf.active_content = []
).controller("icswConfigGenerateCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "sharedDataSource", "$q", "$modal", "blockUI", "ICSW_URLS", "icswConfigConfigTreeService",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, sharedDataSource, $q, $modal, blockUI, ICSW_URLS, icswConfigConfigTreeService) ->
        $scope.devsel_list = []
        $scope.result_trees = []
        $scope.new_devsel = (_dev_sel) ->
            $scope.devsel_list = _dev_sel
        $scope.dev_names = () ->
            # FIXME
            return $scope.devsel_list.join("::")
            return resolve_device_keys($scope.devsel_list)
        $scope._build_list = (ct) ->
            _r_list = [ct]
            for _subnode in ct.sub_nodes
                for _res in $scope._build_list(_subnode)
                    _r_list.push(_res)
            return _r_list
        $scope.generate_config = () ->
            $scope.result_trees = []
            blockUI.start()
            call_ajax
                url     : ICSW_URLS.CONFIG_GENERATE_CONFIG
                data    : {
                    "pk_list" : angular.toJson($scope.devsel_list)
                },
                success : (xml) =>
                    blockUI.stop()
                    cur_list = []
                    if parse_xml_response(xml)
                        _json = angular.fromJson($(xml).find("value[name='result']").text())
                        for cur_dev in _json["devices"]
                            new_tree = new icswConfigConfigTreeService($scope)
                            new_conf = {
                                state : parseInt(cur_dev.state_level)
                                name : cur_dev.name
                                tree : new_tree
                                info_str : cur_dev.info_str
                                active_error : []
                                active_content : []
                            }
                            new_tree.dev_conf = new_conf
                            if new_conf.state >= 40
                                top_node = new_tree.new_node(
                                    {
                                        folder     :  true
                                        _node_type : "eh"
                                        expand     : true
                                    }
                                )
                                new_tree.add_root_node(top_node)
                                # build error tree
                                for entry in cur_dev.info_dict
                                    t_entry = new_tree.new_node({folder:true, obj:entry, _node_type : "e", expand:true})
                                    top_node.add_child(t_entry)
                            else
                                node_lut = {}
                                # build list of entries
                                _tree_list = $scope._build_list(cur_dev.config_tree)
                                for entry in _tree_list
                                    t_entry = new_tree.new_node(
                                        {
                                            folder : parseInt(entry.is_dir)
                                            _node_type : "c"
                                            expand : parseInt(entry.depth) < 2
                                            obj : entry
                                        }
                                    )
                                    node_id = entry.node_id
                                    parent_id = entry.parent_id
                                    node_lut[node_id] = t_entry
                                    if parent_id != "0"
                                        node_lut[parent_id].add_child(t_entry)
                                    else
                                        new_tree.add_root_node(t_entry)
                            cur_list.push(new_conf)
                    $scope.$apply(
                        $scope.result_trees = cur_list
                    )
        $scope.get_info_class = (dev_conf) ->
            if dev_conf.state == 40
                return "text-danger"
            else if dev_conf.state == 20
                return "text-success"
            else
                return "text-warning"
]).directive("icswConfigGenerateConfig", ["$templateCache", "msgbus", ($templateCache, msgbus) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.generate.config")
        link : (scope, el, attrs) ->
            if not attrs["devicepk"]?
                msgbus.emit("devselreceiver")
                msgbus.receive("devicelist", scope, (name, args) ->
                    scope.new_devsel(args[1])
                )
    }
])
