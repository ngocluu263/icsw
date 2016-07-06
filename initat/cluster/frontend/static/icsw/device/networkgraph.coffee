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

# network graphing tool

angular.module(
    "icsw.svg_tools",
    []
).factory("svg_tools", () ->
    _has_class_svg = (s_target, name) ->
        classes = s_target.attr("class")
        if !classes
            return false
        return if classes.search(name) == -1 then false else true
            
    _find_element = (s_target) ->
        # iterative search
        if _has_class_svg(s_target, "draggable")
            return s_target
        s_target = s_target.parent()
        if s_target.length
            return _find_element(s_target)
        else
            return null
            
    return {
        has_class_svg: _has_class_svg

        get_abs_coordinate: (svg_el, x, y) ->
            screen_ctm = svg_el.getScreenCTM()
            svg_point = svg_el.createSVGPoint()
            svg_point.x = x
            svg_point.y = y
            first = svg_point.matrixTransform(screen_ctm.inverse())
            return first
            
        find_draggable_element: (s_target) ->
            return _find_element(s_target)
    }
)

angular.module(
    "icsw.mouseCapture",
    []
).factory('mouseCaptureFactory', [() ->
    # mouseCaptureFactory for ReactJS, no $rootScope.$digest Cycles are triggered
    $element = document
    mouse_capture_config = null
    mouse_move = (event) ->
        if mouse_capture_config and mouse_capture_config.mouse_move
            mouse_capture_config.mouse_move(event)
    mouse_up = (event) ->
        if mouse_capture_config and mouse_capture_config.mouse_up
            mouse_capture_config.mouse_up(event)
    return {
        register_element: (element) ->
            $element = $(element)
        acquire: (event, config) ->
            this.release()
            mouse_capture_config = config
            $element.bind("mousemove", mouse_move)
            $element.bind("mouseup", mouse_up)
        release: () ->
            if mouse_capture_config
                if mouse_capture_config.released
                    mouse_capture_config.released()
                mouse_capture_config = null;
                $element.unbind("mousemove", mouse_move)
                $element.unbind("mouseup", mouse_up)
    }
])

angular.module(
    "icsw.dragging",
    [
        "icsw.mouseCapture"
    ]
).factory("dragging",
[
    "mouseCaptureFactory",
(
    mouseCaptureFactory
) ->
    return {
        start_drag: (event, threshold, config) ->
            dragging = false
            x = event.clientX
            y = event.clientY
            mouse_move = (event) ->
                if !dragging
                    if Math.abs(event.clientX - x) > threshold or Math.abs(event.clientY - y) > threshold
                        dragging = true;
                        if config.dragStarted
                            config.dragStarted(x, y, event)
                        if config.dragging
                            config.dragging(event.clientX, event.clientY, event)
                else 
                    if config.dragging
                        config.dragging(event.clientX, event.clientY, event);
                    x = event.clientX
                    y = event.clientY
            released = () ->
                if dragging
                    if config.dragEnded
                        config.dragEnded()
                else 
                    if config.clicked
                        config.clicked()
            mouse_up = (event) ->
                mouseCaptureFactory.release()
                event.stopPropagation()
                event.preventDefault()
            mouseCaptureFactory.acquire(event, {
                mouse_move: mouse_move
                mouse_up: mouse_up
                released: released
            })
            event.stopPropagation()
            event.preventDefault()
    }
])

angular.module(
    "icsw.device.network.graph",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "icsw.d3", "ui.select",
        "angular-ladda", "icsw.dragging", "monospaced.mousewheel", "icsw.svg_tools", "icsw.tools", "icsw.tools.table",
    ]
).service("icswBurstDrawParameters", [
    "$q"
(
    $q,
) ->
    class icswBurstDrawParameters
        constructor: (args) ->
            # inner radius
            @inner_radius = 20
            # outer radius
            @outer_radius = 60
            # collapse rings with only one segment
            @collapse_one_element_rings = true
            # start ring, 0 ... system, 1 ... group, 2 ... device, 3 .... service
            @start_ring = 2
            # special parameter to filter mon_results
            @device_idx_filter = undefined
            # is interactive (show descriptions on mouseover)
            @is_interactive = false
            # show details on mouseover
            @show_details = false
            # check for too small segments
            @omit_small_segments = false
            # segment treshold, arc * outer_radius must be greater than this valu
            @small_segment_threshold = 3
            for _key, _value of args
                # console.info "BurstDrawParam", _key, _value
                if not @[_key]?
                    console.error "Unknown icswBurstDrawParameter", _key, _value
                else
                    @[_key] = _value

        create_ring_draw_list: (ring_keys) =>
            _idx = 0
            _results = []
            _num_rings = ring_keys.length
            _arc_offset = 0.0
            if _num_rings
                _width = @outer_radius - @inner_radius
                for _key in ring_keys
                    _inner_rad = @inner_radius + _idx * _width / _num_rings
                    _outer_rad = @inner_radius + (_idx + 1 ) * _width / _num_rings
                    _idx++
                    _results.push([_key, _inner_rad, _outer_rad, _arc_offset])
                    # always keep arc_offset at zero
                    _arc_offset += 0.0
            return _results

        start_feed: () =>
            @segments_omitted = 0
            @segments_drawn = 0

        draw_segment: (val) =>
            _draw = if @omit_small_segments and val < @small_segment_threshold then false else true
            if _draw
                @segments_drawn++
            else
                @segments_omitted++
            return _draw

        get_segment_info: () =>
            _r_str = "#{@segments_drawn} segments"
            if @segments_omitted
                _r_str = "#{_r_str}, #{@segments_omitted} omitted"
                
            return _r_str
            
        do_layout: () =>
            # calc some settings for layout
            _outer = @outer_radius
            if @is_interactive
                @text_radius = 1.1 * _outer
                @text_width = 1.15 * _outer
                @total_width = 2 * _outer * 1.2 + 200
                @total_height = 2 * _outer * 1.2
            else
                @total_width = 2 * _outer
                @total_height = 2 * _outer
            

]).service("icswStructuredBurstNode", [
    "$q",
(
    $q,
) ->
    class icswStructuredBurstNode
        constructor: (@parent, @name, @idx, @check, @filter=false, @placeholder=false) ->
            # attributes:
            # o root (top level element)
            # o parent (parent element)
            # name
            # check (may also be a dummy dict)
            @value = 1
            # childre lookup table
            @lut = {}
            @children = []
            @depth = 0
            # show legend
            @show_legend = false
            # selection flags
            @sel_by_parent = false
            @sel_by_child = false
            # no longer used
            # @show = true
            @clicked = false
            if @depth == 0
                # only for root-nodes
                # flag, not in use right now
                @balanced = false
            # parent linking
            if @parent?
                @parent.add_child(@)
            else
                @root = @

        clear_focus: () ->
            # clear all show_legend flags downwards
            @show_legend = false
            @sel_by_parent = false
            @sel_by_child = false
            (_el.clear_focus() for _el in @children)

        # iterator functions
        iterate_upward: (cb_func) ->
            cb_func(@)
            if @parent?
                @parent.iterate_upward(cb_func)

        iterate_downward: (cb_func) ->
            cb_func(@)
            (_child.iterate_downward(cb_func) for _child in @children)

        set_clicked: () ->
            @root.iter_childs((node) -> node.clicked = false)
            @clicked = true
            
        set_focus: () ->
            @iterate_upward((node) -> node.sel_by_child = true)
            @iterate_downward((node) -> node.sel_by_parent = true)

            @show_legend = true
            for _el in @children
                _el.show_legend = true


        clear_clicked: () ->
            # clear all clicked flags
            @root.iter_childs((node) -> node.clicked = false)

        any_clicked: () ->
            res = @clicked
            if not res
                for _entry in @children
                    res = res || _entry.any_clicked()
            return res

        handle_clicked: () ->
            # find clicked entry
            _clicked = @get_childs((obj) -> return obj.clicked)[0]
            @iter_childs(
                (obj) ->
                    obj.show = false
            )
            parent = _clicked
            while parent?
                parent.show = true
                parent = parent.parent
            _clicked.iter_childs((obj) -> obj.show = true)

        balance: () ->
            if @children.length
                _width = _.sum(_child.balance() for _child in @children)
            else
                # constant one or better use value ?
                _width = 1
            # the sum of all widths on any given level is (of course) the same
            @width = _width
            if @depth == 0
                # create ring lookup table
                @ring_lut = {}
                @iter_childs(
                    (node) ->
                        if node.depth not of node.root.ring_lut
                            node.root.ring_lut[node.depth] = []
                        node.root.ring_lut[node.depth].push(node)
                )
                @element_list = []
            return _width

        valid_device: () ->
            _r = false
            if @children.length == 1
                if @children[0].children.length == 1
                    _r = true
            return _r

        reduce: () ->
            if @children.length
                return @children[0]
            else
                return @

        add_child: (entry) ->
            entry.root = @root
            entry.depth = @depth + 1
            @children.push(entry)
            @lut[entry.idx] = entry

        get_self_and_childs: () ->
            _r = [@]
            for node in @children
                _r = _.concat(_r, node.get_self_and_childs())
            return _r

        iter_childs: (cb_f) ->
            cb_f(@)
            (_entry.iter_childs(cb_f) for _entry in @children)

        get_childs: (filter_f) ->
            _field = []
            if filter_f(@)
                _field.push(@)
            for _entry in @children
                _field = _field.concat(_entry.get_childs(filter_f))
            return _field

]).service("icswDeviceLivestatusFunctions",
[
    "$q", "icswStructuredBurstNode", "icswSaltMonitoringResultService",
(
    $q, icswStructuredBurstNode, icswSaltMonitoringResultService,
) ->

    ring_path = (inner, outer) ->
        # return the SVG path for a ring with radi inner and outer
        _path = "M#{outer},0 " + \
        "A#{outer},#{outer} 0 1,1 #{-outer},0 " + \
        "A#{outer},#{outer} 0 1,1 #{outer},0 " + \
        "L#{outer},0 " + \
        "M#{inner},0 " + \
        "A#{inner},#{inner} 0 1,0 #{-inner},0 " + \
        "A#{inner},#{inner} 0 1,0 #{inner},0 " + \
        "L#{inner},0 " + \
        "Z"
        return _path

    ring_segment_path = (inner, outer, start_arc, end_arc) ->
        # returns the SVG path for a ring segment
        start_sin = Math.sin(start_arc)
        start_cos = Math.cos(start_arc)
        end_sin = Math.sin(end_arc)
        end_cos = Math.cos(end_arc)
        if end_arc > start_arc + Math.PI
            _large_arc_flag = 1
        else
            _large_arc_flag = 0
        _path = "M#{start_cos * inner},#{start_sin * inner} L#{start_cos * outer},#{start_sin * outer} " + \
            "A#{outer},#{outer} 0 #{_large_arc_flag} 1 #{end_cos * outer},#{end_sin * outer} " + \
            "L#{end_cos * inner},#{end_sin * inner} " + \
            "A#{inner},#{inner} 0 #{_large_arc_flag} 0 #{start_cos * inner},#{start_sin * inner} " + \
            "Z"
        return _path

    build_burst_ring = (inner, outer, arc_offset, key_prefix, r_data, draw_params) ->
        # offset
        # arc_offset = 0.2
        end_arc = arc_offset
        end_num = 0
        _ia = draw_params.is_interactive
        _len = _.sum((entry.width for entry in r_data))
        _result = []
        # flag if all segments are omitted
        all_omitted = true
        if _len
            _idx = 0
            for node in r_data
                srvc = node.check
                _idx++
                start_arc = end_arc
                end_num += node.width
                end_arc = 2 * Math.PI * end_num / _len + arc_offset
                if draw_params.draw_segment((end_arc - start_arc) * outer)
                    all_omitted = false
                    if _len == 1 and draw_params.collapse_one_element_rings
                        _path = ring_path(inner, outer)
                    else if _len == node.width
                        # full ring (no segment), to fix drawing issues
                        _path = ring_path(inner, outer)
                    else
                        _path = ring_segment_path(inner, outer, start_arc, end_arc)
                    # _el is a path element, (nearly) ready to be rendered via SVG
                    # $$segment is the pointer to the StructuredBurstNode and holds important flags and
                    #    structural information
                    # $$service is the pointer to the linked service check (may be a dummy check)
                    _el = {
                        key: "path.#{key_prefix}.#{_idx}"
                        d: _path
                        # fill: #srvc.$$burst_fill_color
                        #classes : srvc.className #not needed any more?
                        className: "sb_lines #{srvc.className}"
                        #stroke: "black"
                        # hm, stroke-width seems to be ignored
                        #strokeWidth: "0.5"
                        # link to segment
                        $$segment: node
                        # link to check (node or device or devicegroup or system)
                        $$service: srvc
                    }
                    if _ia
                        # add values for interactive display
                        _el.$$mean_arc = (start_arc + end_arc) / 2.0
                        _el.$$mean_radius = (outer + inner) / 2.0
                    _result.push(_el)
                if all_omitted
                    # all segments omitted, draw dummy graph
                    _dummy = icswSaltMonitoringResultService.get_dummy_service_entry()
                    _result.push(
                        {
                            key: "path.#{key_prefix}.omit"
                            d: ring_path(inner, outer)
                            $$service: _dummy
                            fill: _dummy.$$burst_fill_color
                            stroke: "black"
                            strokeWidth: "0.3"
                        }
                    )
        else
            _dummy = icswSaltMonitoringResultService.get_dummy_service_entry()
            # draw an empty (== grey) ring
            _result.push(
                {
                    key: "path.#{key_prefix}.empty"
                    d: ring_path(inner, outer)
                    $$service: _dummy
                    fill: _dummy.$$burst_fill_color
                    stroke: "black"
                    strokeWidth: "0.3"
                }
            )
        return _result

    build_structured_burst = (mon_data, draw_params) ->
        _root_node = new icswStructuredBurstNode(
            null
            "System"
            0
            icswSaltMonitoringResultService.get_system_entry("System")
        )
        #if node.id of @props.monitoring_data.host_lut
        #    host_data = @props.monitoring_data.host_lut[node.id]
        #    if not host_data.$$show
        #        host_data = undefined
        #else
        #    host_data = undefined
        # service ids to show
        _sts = (entry.$$idx for entry in mon_data.services)
        for host in mon_data.hosts
            dev = host.$$icswDevice
            if not draw_params.device_idx_filter? or dev.idx == draw_params.device_idx_filter
                devg = host.$$icswDeviceGroup
                if devg.idx not of _root_node.lut
                    # add device group ring
                    _devg = new icswStructuredBurstNode(
                        _root_node
                        devg.name
                        devg.idx
                        icswSaltMonitoringResultService.get_device_group_entry(devg.name)
                    )
                else
                    _devg = _root_node.lut[devg.idx]
                # _devg holds now the structured node for the device group
                _dev = new icswStructuredBurstNode(
                    _devg
                    dev.name
                    dev.idx
                    host
                )
                for service in host.$$service_list
                    # check for filter
                    if service.$$idx in _sts
                        new icswStructuredBurstNode(_dev, service.description, service.$$idx, service, true)
                if not _dev.children.length
                    # add dummy service for devices without services
                    new icswStructuredBurstNode(
                        _dev
                        ""
                        0
                        icswSaltMonitoringResultService.get_dummy_service_entry("---")
                        false
                        true
                    )

        # balance nodes, set width of each segment, create ring lut

        _root_node.balance()

        # set states in ring 1 and 0
        for _ring_idx in [1, 0]
            if _ring_idx of _root_node.ring_lut
                for _entry in _root_node.ring_lut[_ring_idx]
                    if _entry.children.length
                        _entry.check.state = _.max((_child.check.state for _child in _entry.children))
                    else
                        _entry.check.state = 3
                    icswSaltMonitoringResultService.salt_device_state(_entry.check)

        # draw
        _ring_keys= (
            _entry for _entry in _.map(
                _.keys(_root_node.ring_lut)
                (_key) ->
                    return parseInt(_key)
            ).sort() when _entry >= draw_params.start_ring
        )

        # reset some draw parameters (omitted segments)
        draw_params.start_feed()

        for [_ring, _inner_rad, _outer_rad, _arc_offset] in draw_params.create_ring_draw_list(_ring_keys)
            _root_node.element_list = _.concat(_root_node.element_list, build_burst_ring(_inner_rad, _outer_rad, _arc_offset, "ring#{_ring}", _root_node.ring_lut[_ring], draw_params))
        return _root_node
        
    return {
        build_structured_burst: (mon_data, draw_params) ->
            # mon_data is a filtered instance of icswMonitoringResult
            return build_structured_burst(mon_data, draw_params)
    }

]).factory("icswDeviceLivestatusReactBurst",
[
    "$q", "icswDeviceLivestatusFunctions", "icswBurstDrawParameters",
(
    $q, icswDeviceLivestatusFunctions, icswBurstDrawParameters,
) ->

    react_dom = ReactDOM
    {div, g, text, circle, path} = React.DOM

    return React.createClass(
        propTypes: {
            # required types
            node: React.PropTypes.object
            monitoring_data: React.PropTypes.object
            draw_parameters: React.PropTypes.object
        }
        
        componentDidMount: () ->
            el = react_dom.findDOMNode(@)
            # d3js hack
            el.__data__ = @props.node

        render: () ->
            node = @props.node
            # hack, set special attribute
            @props.draw_parameters.device_idx_filter = node.id
            # should be optmized
            root_node = icswDeviceLivestatusFunctions.build_structured_burst(
                @props.monitoring_data
                @props.draw_parameters
            )
            #if root_node.element_list.length
            #    console.log "EL=", node.id, root_node.element_list.length
            #else
            #    console.log "empty", node.id
            # console.log "rn=", root_node, @props.monitoring_data
            # reset
            @props.draw_parameters.device_idx_filter = undefined
            # srvc_data = (entry for entry in @props.monitoring_data.services when entry.host.host_name  == node.$$device.full_name)

            # console.log host_data, srvc_data
            # if host_data and srvc_data.length
            # _pathes = icswDeviceLivestatusFunctions.build_single_device_burst(host_data, srvc_data)
            # else
            #    _pathes = []

            return g(
                {
                    key: "node.#{node.id}"
                    className: "d3-livestatus"
                    id: "#{node.id}"
                    transform: "translate(#{node.x}, #{node.y})"
                }
                (
                    path(_.pickBy(_path, (value, key) -> return not key.match(/\$/))) for _path in root_node.element_list
                )
            )
    )
]).service("icswD3DeviceLivestatiReactBurst",
[
    "svg_tools", "icswDeviceLivestatusReactBurst", "icswBurstDrawParameters",
(
    svg_tools, icswDeviceLivestatusReactBurst, icswBurstDrawParameters,
) ->
    # container for all device bursts
    react_dom = ReactDOM
    {div, g, text} = React.DOM

    return React.createClass(
        propTypes: {
            # required types
            nodes: React.PropTypes.array
            show_livestatus: React.PropTypes.bool
            monitoring_data: React.PropTypes.object
        }
        #shouldComponentUpdate: (next_props, next_state) ->
        #    console.log "*", next_props, @props
        #    return _redraw

        render: () ->
            _draw_params = new icswBurstDrawParameters({inner_radius: 20, outer_radius: 30})
            _bursts = []
            if @props.show_livestatus
                for node in @props.nodes
                    _bursts.push(
                        React.createElement(
                            icswDeviceLivestatusReactBurst
                            {
                                node: node
                                monitoring_data: @props.monitoring_data
                                draw_parameters: _draw_params
                            }
                        )
                    )
            return g(
                {
                    key: "top.stati"
                    className: "d3-livestati"
                }
                _bursts
            )
    )
]).service("icswD3Device",
[
    "svg_tools",
(
    svg_tools
) ->
    class icswD3Device
        constructor: (@container) ->

        create: (selector, graph) ->
            # console.log "data=", graph.nodes
            # not working, TODO
            # selector.data([]).exit().remove()
            ds = selector.data(graph.nodes, (d) -> return d.id)
            _g = ds.enter().append("g")
            _g.attr("class", "d3-point draggable")
            .attr("id", (d) -> return graph.node_to_dom_id(d))
            .attr("transform", (d) -> return "translate(#{d.x}, #{d.y})")
            _g.append("circle")
            # <circle r="18" fill="{{ fill_color }}" stroke-width="{{ stroke_width }}" stroke="{{ stroke_color }}" cursor="crosshair"></circle>
            .attr('r', (d) -> return d.radius)
            .attr("class", "svg_d3circle")
            .attr("cursor", "crosshair")
            _g.append("text")
            .attr("class", "svg_d3text")
            .text(
                (d) ->
                    return d.$$device.full_name
            )
            # <text text-anchor="middle" alignment-baseline="middle" cursor="crosshair">{{ node.name }}</text>
            .attr("cursor", "crosshair")
            # mouse handling
            that = @
            _g.on("click", (node) ->
                # important to use thin arrows here
                that.container.click(this, node)
            )
            ds.exit().remove()

]).service("icswD3Link",
[
    "svg_tools",
(
    svg_tools
) ->
    class icswD3Link
        constructor: (@container) ->
        create: (selector, graph) ->
            # console.log "link=", graph.links
            ds = selector.data(graph.links, (l) -> return graph.link_to_dom_id(l))
            ds.enter().append("line")
            .attr("class", "d3-link svg_d3link")
            ds.exit().remove()

]).service("icswNetworkTopologyDrawService",
[
    "$templateCache", "d3_service", "svg_tools", "dragging", "mouseCaptureFactory",
    "icswTools", "icswD3Device", "icswD3Link", "$q", "icswDeviceLivestatusDataService",
    "$timeout", "icswD3DeviceLivestatiReactBurst",
(
    $templateCache, d3_service, svg_tools, dragging, mouseCaptureFactory,
    icswTools, icswD3Device, icswD3Link, $q, icswDeviceLivestatusDataService,
    $timeout, icswD3DeviceLivestatiReactBurst,
) ->

    # acts as a helper class for drawing Networks as SVG-graphs
    class icswNetworkTopologyDrawService

        constructor: () ->
            @id = icswTools.get_unique_id()
            @status_timeout = undefined
            @livestatus_state = false
            @filter_state_str = ""
            @device_gen = new icswD3Device(@)
            @link_gen = new icswD3Link(@)
            # pipe for graph commands
            @graph_command_pipe = undefined
            # current monitoring data
            @monitoring_data = undefined
            # autoscale during initial force run
            @do_autoscale = false

        create: (element, props, state) =>
            @element = element
            @props = props
            @state = state
            @graph_command_pipe = $q.defer()
            if @props.graph_command_cb?
                @props.graph_command_cb(@graph_command_pipe)
                @graph_command_pipe.promise.then(
                    () ->
                    (exit) ->
                        console.log "exit"
                    (cmd) =>
                        if cmd == "scale"
                            @graph_cmd_scale()
                        else
                            console.error "unknown graph command '#{cmd}'"
                )
            draw_settings = state.settings
            $q.all(
                [
                    d3_service.d3()
                ]
            ).then(
                (result) =>
                    d3 = result[0]
                    # base settings
                    @d3 = d3
                    @d3_element = d3.select(@element)
                    _find_element = (s_target) ->
                        # iterative search
                        if svg_tools.has_class_svg(s_target, "draggable")
                            return s_target
                        s_target = s_target.parent()
                        if s_target.length
                            return _find_element(s_target)
                        else
                            return null
                    svg = @d3_element.append("svg")
                    .attr('class', 'draggable')
                    # viewBox not viewbox
                    .attr("viewBox", "0 0 1200 760")
                    .attr("preserveAspectRatio", "xMidYMin meet")
                    .attr("version", "1.1")
                    .attr("onStart", @_drag_start)
                    .attr("pointer-events", "all")
                    .attr("width", "100%")
                    .attr("height", 760) #$(window).height()-140)
                    $(element).on("mouseclick", (event) =>
                        drag_el = _find_element($(event.target))
                        # console.log "DRAG_EL=", drag_el
                        if drag_el? and drag_el.length
                            drag_el = $(drag_el[0])
                            # console.log "d=", drag_el
                    )
                    $(element).mousedown(
                        (event) =>
                            mouseCaptureFactory.register_element(element)
                            drag_el = _find_element($(event.target))
                            if drag_el? and drag_el.length
                                drag_el = $(drag_el[0])
                                drag_el_tag = drag_el.prop("tagName")
                                # disable autoscale
                                svg = $(element).find("svg")[0]
                                @do_autoscale = false
                                if drag_el_tag == "svg"
                                    _sx = 0
                                    _sy = 0
                                    start_drag_point = undefined
                                    dragging.start_drag(event, 1, {
                                        dragStarted: (x, y, event) =>
                                            start_drag_point = svg_tools.get_abs_coordinate(svg, x, y)
                                            _sx = draw_settings.offset.x
                                            _sy = draw_settings.offset.y
                                        dragging: (x, y) =>
                                            cur_point = svg_tools.get_abs_coordinate(svg, x, y)
                                            draw_settings.offset = {
                                                x: _sx + cur_point.x - start_drag_point.x
                                                y: _sy + cur_point.y - start_drag_point.y
                                            }
                                            @_update_transform(element, draw_settings, props.update_scale_cb)
                                        dragEnded: () =>
                                    })
                                else
                                    drag_node = drag_el[0]
                                    drag_dev = state.graph.dom_id_to_node($(drag_node).attr("id"))
                                    dragging.start_drag(event, 1, {
                                        dragStarted: (x, y, event) =>
                                            @set_fixed(drag_node, drag_dev, true)
                                        dragging: (x, y) =>
                                            cur_point = @_rescale(
                                                svg_tools.get_abs_coordinate(svg, x, y)
                                                draw_settings
                                            )
                                            node = drag_dev
                                            node.x = cur_point.x
                                            node.y = cur_point.y
                                            # the p-coordiantes are important for moving (dragging) nodes
                                            node.px = cur_point.x
                                            node.py = cur_point.y
                                            @tick()
                                            if @force?
                                                # restart moving
                                                @force.start()
                                        dragEnded: () =>
                                            @set_fixed(drag_node, drag_dev, false)
                                    })
                    )
                    Hamster(element).wheel(
                        (event, delta, dx, dy) =>
                            # console.log "msd", delta, dx, dy
                            svg = $(element).find("svg")[0]
                            scale_point = @_rescale(
                                svg_tools.get_abs_coordinate(svg, event.originalEvent.clientX, event.originalEvent.clientY)
                                draw_settings
                            )
                            prev_factor = draw_settings.zoom.factor
                            if delta > 0
                                draw_settings.zoom.factor *= 1.05
                            else
                                draw_settings.zoom.factor /= 1.05
                            draw_settings.offset.x += scale_point.x * (prev_factor - draw_settings.zoom.factor)
                            draw_settings.offset.y += scale_point.y * (prev_factor - draw_settings.zoom.factor)
                            @_update_transform(element, draw_settings, props.update_scale_cb)
                            event.stopPropagation()
                            event.preventDefault()
                    )
                    # enclosing rectangular and top-level g
                    svg.append("rect")
                    .attr("x", "0")
                    .attr("y", "0")
                    .attr("width", "100%")
                    .attr("height", "100%")
                    .attr("style", "stroke:black; stroke-width:2px; fill-opacity:0;")
                    _top_g = svg.append("g").attr("id", "top")
                    _top_g.append('g').attr('class', 'd3-links')
                    _top_g.append('g').attr('class', 'd3-livestati')
                    _top_g.append('g').attr('class', 'd3-points')

                    # force settings

                    force = undefined
                    if draw_settings.force? and draw_settings.force.enabled?
                        force = d3.layout.force().charge(-220).gravity(0.01).linkDistance(100).size(
                            [
                                400
                                400
                            ]
                        ).linkDistance(
                            (d) ->
                                return 100
                        ).on("tick", () =>
                            @tick()
                        )
                    @update(element, state)
                    if draw_settings.force? and draw_settings.force.enabled?
                        force.stop()
                        force.nodes(state.graph.nodes).links(state.graph.links)
                        force.start()
                    @do_autoscale = true
                    @_draw_points()
                    @_draw_links()
                    @force = force
                    # for correct initial handling of livestatus display
                    @set_livestatus_state(props.with_livestatus)

            )

        set_fixed: (dom_node, device, flag) ->
            device.fixed = flag
            cssclass = if flag then "svg_d3circle_selected" else "svg_d3circle"
            $(dom_node).find("circle").attr("class", cssclass)

        tick: () =>
            # updates all coordinates, attention: not very effective for dragging
            # update
            @d3_element.selectAll(".d3-point")
            .attr("transform", (d) -> return "translate(#{d.x}, #{d.y})")
            @d3_element.selectAll(".d3-livestatus")
            .attr("transform", (d) -> return "translate(#{d.x}, #{d.y})")
            @d3_element.selectAll(".d3-link")
            .attr("x1", (d) -> return d.source.x)
            .attr("y1", (d) -> return d.source.y)
            .attr("x2", (d) -> return d.target.x)
            .attr("y2", (d) -> return d.target.y)
            @d3_element.selectAll(".d3-point")
            if @do_autoscale
                @graph_cmd_scale()

        click: (dom_node, drag_dev) =>
            @set_fixed(dom_node, drag_dev, !drag_dev.fixed)

        _drag_start: (event, ui) ->
            # console.log "ds", event, ui
            true

        _rescale: (point, settings) =>
            point.x -= settings.offset.x
            point.y -= settings.offset.y
            point.x /= settings.zoom.factor
            point.y /= settings.zoom.factor
            return point

        update: () =>
            # scales are not needed
            # scales = @_scales(@element, @state.settings.domain)
            @_update_transform(@element, @state.settings, @props.update_scale_cb)
            @tick()

        _scales: (element, domain) =>
            # hm, to be improved ...
            jq_el = $(element).find("svg")
            width = jq_el.width()
            height = jq_el.height()
            # console.log "domain=", domain
            x = @d3.scale.linear().range([0, width]).domain(domain.x)
            y = @d3.scale.linear().range([height, 0]).domain(domain.y)
            z = @d3.scale.linear().range([5, 20]).domain([1, 10])
            console.log x, y, z
            return {x: x, y: y, z: z}

        _update_transform: (element, settings, update_scale_cb) =>
            g = $(element).find("g#top")
            _t_str = "translate(#{settings.offset.x}, #{settings.offset.y}) scale(#{settings.zoom.factor})"
            g.attr("transform", _t_str)
            update_scale_cb()

        _draw_points: () =>
            # select g
            g = @d3_element.selectAll(".d3-points")

            @device_gen.create(g.selectAll(".d3-point"), @state.graph)

        _draw_links: () =>
            # select g
            g = @d3_element.selectAll(".d3-links")

            @link_gen.create(g.selectAll(".d3-link"), @state.graph)

        _draw_livestatus: () =>
            # select g
            g = @d3_element.select(".d3-livestati")
            ReactDOM.render(
                React.createElement(
                    icswD3DeviceLivestatiReactBurst
                    {
                        nodes: @state.graph.nodes
                        show_livestatus: @livestatus_state
                        monitoring_data: @monitoring_data
                    }
                )
                g[0][0]
            )

        destroy: (element) =>
            console.log "destroy"
            if @force?
                @force.stop()
            icswDeviceLivestatusDataService.destroy(@id)

        graph_cmd_scale: () =>
            _n = @state.graph.nodes
            _xs = (d.x for d in _n)
            _ys = (d.y for d in _n)
            [_min_x, _max_x] = [_.min(_xs), _.max(_xs)]
            [_min_y, _max_y] = [_.min(_ys), _.max(_ys)]

            # add boundaries

            _size_x = _max_x - _min_x
            _size_y = _max_y - _min_y
            _min_x -= _size_x / 20
            _max_x += _size_x / 20
            _min_y -= _size_y / 20
            _max_y += _size_y / 20

            # parse current viewBox settings

            _vbox = _.map($(@element).find("svg")[0].getAttribute("viewBox").split(" "), (elem) -> return parseInt(elem))
            _width = parseInt(_vbox[2])
            _height = parseInt(_vbox[3])

            _fact_x = _width / (_max_x - _min_x)
            _fact_y = _height / (_max_y - _min_y)
            if _fact_x < _fact_y
                # x domain is wider than y domain
                @state.settings.zoom.factor = _fact_x
                @state.settings.offset = {
                    x: -_min_x * _fact_x
                    y: (_height - (_max_y + _min_y) * _fact_x) / 2
                }
            else
                @state.settings.zoom.factor = _fact_y
                @state.settings.offset = {
                    x: (_width - (_max_x + _min_x) * _fact_y) / 2
                    y: -_min_y * _fact_y
                }
            @_update_transform(@element, @state.settings, @props.update_scale_cb)

        set_livestatus_filter: (filter) =>
            state_str = filter.get_filter_state_str()
            if state_str != @filter_state_str
                @filter_state_str = state_str
                if @monitoring_data
                    @props.livestatus_filter.set_monitoring_data(@monitoring_data)
                    @_draw_livestatus()

        set_livestatus_state: (new_state) =>
            # set state of livestatus display
            if new_state != @livestatus_state
                # console.log "set state of livestatus to #{new_state}"
                @livestatus_state = new_state
                if @livestatus_state
                    @start_livestatus()
                else
                    @stop_livestatus()
                    @_draw_livestatus()

        stop_livestatus: () =>
            icswDeviceLivestatusDataService.stop(@id)
            @monitoring_data = undefined

        start_livestatus: () =>
            icswDeviceLivestatusDataService.retain(@id, @state.graph.device_list).then(
                (result) =>
                    result.result_notifier.promise.then(
                        () ->
                        () ->
                        (generation) =>
                            @monitoring_data = result
                            # console.log "gen", @props.livestatus_filter, @monitoring_data
                            # @props.livestatus_filter.set_monitoring_data(@monitoring_data)
                            @_draw_livestatus()
                    )
            )

]).factory("icswNetworkTopologyReactSVGContainer",
[
    "icswNetworkTopologyDrawService",
(
    icswNetworkTopologyDrawService
) ->

    react_dom = ReactDOM
    {div} = React.DOM

    return React.createClass(
        propTypes: {
            # required types
            graph: React.PropTypes.object
            settings: React.PropTypes.object
            scale_changed_cb: React.PropTypes.func
            with_livestatus: React.PropTypes.bool
            livestatus_filter: React.PropTypes.object
            graph_command_cb: React.PropTypes.func
        }
        getInitialState: () ->
            return {
                iteration: 0
            }

        componentDidMount: () ->
            @draw_service = new icswNetworkTopologyDrawService()
            console.log "mount"
            el = ReactDOM.findDOMNode(@)
            @draw_service.create(
                el
                {
                    width: @props.settings.size.width
                    height: @props.settings.size.height
                    update_scale_cb: @update_scale
                    with_livestatus: @props.with_livestatus
                    livestatus_filter: @props.livestatus_filter
                    graph_command_cb: @props.graph_command_cb
                }
                {
                    graph: @props.graph
                    settings: @props.settings
                }
            )

        update_scale: () ->
            @setState({iteration: @state.iteration + 1})
            @props.scale_changed_cb()

        componentWillUnmount: () ->
            console.log "main_umount"
            el = react_dom.findDOMNode(@)
            @draw_service.destroy(el)

        componentDidUpdate: () ->
            # called when the props have changed
            @draw_service.set_livestatus_state(@props.with_livestatus)
            @draw_service.set_livestatus_filter(@props.livestatus_filter)

        render: () ->
            return div({key: "div"})
    )
]).factory("icswNetworkTopologyReactContainer",
[
    "$q", "ICSW_URLS", "icswSimpleAjaxCall", "icswNetworkTopologyReactSVGContainer",
    "icswLivestatusFilterService", "icswLivestatusFilterReactDisplay",
    "icswActiveSelectionService",
(
    $q, ICSW_URLS, icswSimpleAjaxCall, icswNetworkTopologyReactSVGContainer,
    icswLivestatusFilterService, icswLivestatusFilterReactDisplay,
    icswActiveSelectionService,
) ->
    # Network topology container, including selection and redraw button
    react_dom = ReactDOM
    {div, h4, select, option, p, input, span, button} = React.DOM

    return React.createClass(
        propTypes: {
            # required types
            device_tree: React.PropTypes.object
        }

        getInitialState: () ->
            return {
                draw_type: "all_with_peers"
                loading: false
                with_livestatus: false
                data_present: false
                graph: undefined
                settings: undefined
                graph_id: 0
                redraw_trigger: 0
                livestatus_filter: new icswLivestatusFilterService()
            }

        componentWillUnmount: () ->
            console.log "TopCont umount"
            if @graph_command?
                @graph_command.reject("exit")
            el = react_dom.findDOMNode(@)

        render: () ->
            _load_data = () =>
                @setState({loading: true})
                @load_data()

            _draw_options = [
                ["none", "None"]
                ["all_with_peers", "All peered"]
                ["all", "All devices"]
                ["sel", "selected devices"]
                ["selp1", "selected devices + 1 (next ring)"]
                ["selp2", "selected devices + 2"]
                ["selp3", "selected devices + 3"]
                ["core", "Core network"]
            ]
            _opts = (
                option(
                    {
                        key: "sel_#{key}"
                        value: key
                    }
                    info
                ) for [key, info] in _draw_options
            )
            _list = [
                "Show network topology for "
                select(
                    {
                        key: "inpsel"
                        className: "form-control"
                        defaultValue: "#{@state.draw_type}"
                        style: {width: "200px"}
                        onChange: (event) =>
                            _cur_dt = @state.draw_type
                            _new_dt = event.target.value
                            @setState({draw_type: event.target.value}, () =>
                                if _cur_dt != _new_dt
                                    _load_data()
                            )

                    }
                    _opts
                )
                ", "
                button(
                    {
                        key: "b.redraw"
                        type: "button"
                        className: "btn btn-warning btn-sm fa fa-pencil"
                        onClick: (event) =>
                            _load_data()
                    }
                    " Redraw"
                )
            ]
            _top_list = [
                div(
                    {key: "div0", className: "form-group form-inline"}
                    _list
                )
            ]
            if @state.data_present
                _list.push(
                    button(
                        {
                            key: "b.scale"
                            type: "button"
                            className: "btn btn-success btn-sm fa fa-arrows-alt"
                            onClick: (event) =>
                                @graph_command.notify("scale")
                        }
                        " Scale"
                    )
                )
                _list.push(
                    button(
                        {
                            key: "b.livestatus"
                            type: "button"
                            className: if @state.with_livestatus then "btn btn-success btn-sm fa fa-bar-chart" else "btn btn-default btn-sm fa fa-bar-chart"
                            onClick: (event) =>
                                @setState({with_livestatus: not @state.with_livestatus})
                        }
                        " Livestatus"
                    )
                )
                if false
                    # no longer needed, too much details
                    _top_list.push(
                        h4(
                            {key: "header"}
                            "Settings: #{_.round(@state.settings.offset.x, 3)} / #{_.round(@state.settings.offset.y, 3)} @ #{_.round(@state.settings.zoom.factor, 3)}"
                        )
                    )
                graph_id = @state.graph_id
                _top_list.push(
                    React.createElement(
                        icswNetworkTopologyReactSVGContainer
                        {
                            key: "graph#{graph_id}"
                            graph: @state.graph
                            settings: @state.settings
                            scale_changed_cb: @scale_changed
                            with_livestatus: @state.with_livestatus
                            livestatus_filter: @state.livestatus_filter
                            graph_command_cb: @graph_command_cb
                        }
                    )
                )
            if @state.with_livestatus
                _list.push(
                    React.createElement(
                        icswLivestatusFilterReactDisplay
                        {
                            livestatus_filter: @state.livestatus_filter
                            filter_changed_cb: @filter_changed
                        }
                    )
                )
            if @state.loading
                _list.push(
                    span(
                        {className: "text-danger", key: "infospan"}
                        " Fetching data from server..."
                    )
                )
            return div(
                {key: "top"}
                _top_list
            )

        graph_command_cb: (defer) ->
            @graph_command = defer

        filter_changed: () ->
            @setState({redraw_trigger: @state.redraw_trigger + 1})

        scale_changed: () ->
            @setState({redraw_trigger: @state.redraw_trigger + 1})

        load_data: () ->
            _dt = @state.draw_type
            if _dt.match(/^sel/)
                _pks = icswActiveSelectionService.current().get_devsel_list()[1]
            else
                _pks = []
            icswSimpleAjaxCall(
                url: ICSW_URLS.NETWORK_JSON_NETWORK
                data:
                    graph_sel: _dt
                    devices: angular.toJson(_pks)
                dataType: "json"
            ).then(
                (json) =>
                    # console.log json
                    @setState(
                        {
                            loading: false
                            data_present: true
                            graph_id: @state.graph_id + 1
                            graph: @props.device_tree.seed_network_graph(json.nodes, json.links)
                            settings: {
                                offset: {
                                    x: 0
                                    y: 0
                                }
                                zoom: {
                                    factor: 1.0
                                }
                                force: {
                                    enabled: true
                                }
                                # domain: {
                                #     x: [0, 10]
                                #     y: [0, 20]
                                # }
                                size: {
                                    width: "95%"
                                    height: "600px"
                                }
                            }
                        }
                    )
            )
    )
]).directive("icswDeviceNetworkTopologyOld",
[
    "ICSW_URLS", "icswDeviceTreeService", "icswNetworkTopologyReactContainer",
    "icswMonLivestatusPipeConnector",
(
    ICSW_URLS, icswDeviceTreeService, icswNetworkTopologyReactContainer,
    icswMonLivestatusPipeConnector,
) ->
    return {
        restrict: "EA"
        replace: true
        link: (scope, element, attrs) ->

            scope.size = undefined
            scope.$watch("size", (new_val) ->
                # hm, not working
                console.log "new size", new_val
            )
            icswDeviceTreeService.load(scope.$id).then(
                (tree) ->
                    _load_graph(tree)
            )
            _load_graph = (tree) ->
                ReactDOM.render(
                    React.createElement(
                        icswNetworkTopologyReactContainer
                        {
                            device_tree: tree
                        }
                    )
                    element[0]
                )
                scope.$on("$destroy", () ->
                    ReactDOM.unmountComponentAtNode(element[0])
                )

    }
])
