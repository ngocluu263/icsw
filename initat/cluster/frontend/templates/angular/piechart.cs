{% load coffeescript staticfiles %}

<script type="text/javascript">

{% inlinecoffeescript %}

{% verbatim %}

{% endverbatim %}

root = exports ? this


angular.module(
    "angular-piechart", []
).directive("icswPiechart", () ->
    return {
        restrict: "E"
        scope:
            data: "=data"
            diameter: "=diameter"
        template: """
{% verbatim %}
<div class="chart">
    <svg ng-show="data_active.length > 0" ng-attr-width="{{diameter}}" ng-attr-height="{{diameter}}" ng-attr-viewBox="0 0 {{diameter}} {{diameter}}" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
        <g opacity="1">
            <g ng-repeat="entry in data_active" data-active class="pieSegmentGroup" data-order={{entry.num}}>
                <path stroke-width="1" stroke-miterlimit="2" stroke="#fff" ng-attr-fill="{{entry.color}}" class="pieSegment" ng-attr-d="{{entry.path}}"
                    ng-mouseenter="mouse_enter(entry)" ng-mouseleave="mouse_leave(entry)" ng-mousemove="mouse_move(entry, $event)"></path>
            </g>
        </g>
    </svg>
    <div class="piechart-tooltip" ng-show="tooltip_text" ng-attr-style="top: {{tooltipY}}px; left: {{tooltipX}}px;">{{tooltip_text}}</div>
</div>
{% endverbatim %}
"""
        link : (scope, el, attrs) ->
            scope.mouse_enter = (entry) ->
                scope.tooltip_text = "#{entry.title}: #{entry.value}%"
            scope.mouse_leave = (entry) ->
                scope.tooltip_text = undefined
            scope.mouse_move = (entry, event) ->
                # not very elegant
                tooltip = el[0].children[0].childNodes[3]
                scope.tooltipX = event.clientX - (tooltip.clientWidth/2)
                scope.tooltipY = event.clientY - 40
            scope.calc_path = (entry) ->

                if entry.part == 1.0  # full circle
                    cmd = [
                           'M', scope.centerX, scope.centerY,
                           'm', -scope.radius, 0,
                           'a', scope.radius, scope.radius, 0, 1, 0, 2*scope.radius, 0,
                           'a', scope.radius, scope.radius, 0, 1, 0, -2*scope.radius, 0]
                else 
                    startX = scope.centerX + Math.cos(entry.start_angle) * scope.radius
                    startY = scope.centerY + Math.sin(entry.start_angle) * scope.radius

                    endX = scope.centerX + Math.cos(entry.end_angle) * scope.radius
                    endY = scope.centerY + Math.sin(entry.end_angle) * scope.radius

                    largeArc = if ((entry.end_angle - entry.start_angle) % (Math.PI * 2)) > Math.PI then 1 else 0

                    cmd = [
                           'M', startX, startY,  # move
                           'A', scope.radius, scope.radius, 0, largeArc, 1, endX, endY,  # arc
                           'L', scope.centerX, scope.centerY,  #line to the center.
                           'Z']  # close
                return cmd.join(" ")
            scope.calc_col = (entry) ->
                return entry.color
                
            scope.$watchGroup(["data", "diameter"], (new_data) ->
                scope.centerX = scope.diameter/2
                scope.centerY = scope.diameter/2
                scope.radius = scope.diameter/2
                
                new_data = []
                i = 0
                scope.value_total = 0
                for entry in scope.data
                    new_entry = Object.create(entry)
                    new_entry.num = i
                    scope.value_total += new_entry.value

                    new_data.push(new_entry)
                    i += 1

                # calculations based on value_total (cant do these in loop above)
                start_angle = -Math.PI/2
                for new_entry in new_data
                    # calc general properties (currently only used in calc_path)
                    part = new_entry.value / scope.value_total
                    part_angle = part * (Math.PI*2)

                    new_entry.part = part
                    new_entry.start_angle = start_angle
                    new_entry.end_angle = start_angle + part_angle

                    new_entry.path = scope.calc_path(new_entry)

                    new_entry.tooltip_visible = false

                    start_angle = new_entry.end_angle

                scope.data_active = new_data
            )
}).run(($templateCache) ->
)


{% endinlinecoffeescript %}

</script>
