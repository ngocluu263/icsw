{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

package_module = angular.module("icsw.package", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular"])

angular_module_setup([package_module])

angular_add_simple_list_controller(
    package_module,
    "package_repo_base",
    {
        rest_url            : "{% url 'rest:package_repo_list' %}"
        edit_template       : "network_type.html"
        delete_confirm_str  : (obj) -> return "Really delete Package repository '#{obj.name}' ?"
        template_cache_list : ["package_repo_row.html", "package_repo_head.html"]
        fn :
            toggle : (obj) ->
                obj.publish_to_nodes = if obj.publish_to_nodes then false else true
                obj.put()
            rescan : ($scope) ->
                $.blockUI()
                $.ajax
                    url     : "{% url 'pack:repo_overview' %}"
                    data    : {
                        "mode" : "rescan"
                    }
                    success : (xml) ->
                        $.unblockUI()
                        if parse_xml_response(xml)
                            $scope.reload()
            sync : () ->
                $.blockUI()
                $.ajax
                    url     : "{% url 'pack:repo_overview' %}"
                    data    : {
                        "mode" : "sync"
                    }
                    success : (xml) ->
                        $.unblockUI()
                        parse_xml_response(xml)
    }
)

angular_add_simple_list_controller(
    package_module,
    "package_search_base",
    {
        rest_url            : "{% url 'rest:package_search_list' %}"
        edit_template       : "network_type.html"
        delete_confirm_str  : (obj) -> return "Really delete Package search '#{obj.name}' ?"
        template_cache_list : ["package_search_row.html", "package_search_head.html"]
        entries_filter      : {deleted : false}
        fn:
            retry : ($scope, obj) ->
                $.ajax
                    url     : "{% url 'pack:retry_search' %}"
                    data    : {
                        "pk" : obj.idx
                    }
                    success : (xml) ->
                        parse_xml_response(xml)
                        $scope.reload()
            show_time : (idx) ->
                console.log idx
        init_fn:
            ($scope) ->
                $(document).everyTime(5000, "show_time", (i) ->
                    $scope.reload()
                )
    }
)

{% endinlinecoffeescript %}

</script>
