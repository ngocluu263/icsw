{% load coffeescript %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

network_module = angular.module("icsw.network", ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "localytics.directives", "restangular"])

angular_module_setup([network_module])

nw_types_dict = {
    "b" : "boot"
    "p" : "prod"
    "s" : "slave"
    "o" : "other"
    "l" : "local"
}

angular_add_simple_list_controller(
    network_module,
    "network_type_base",
    {
        rest_url            : "{% url 'rest:network_type_list' %}"
        edit_template       : "network_type.html"
        delete_confirm_str  : (obj) -> return "Really delete Network type '#{obj.description}' ?"
        template_cache_list : ["network_type_row.html", "network_type_head.html"]
        new_object          : {"identifier" : "p", description : ""}
        object_created  : (new_obj) -> new_obj.description = ""
        network_types       : nw_types_dict 
    }
)


angular_add_simple_list_controller(
    network_module,
    "network_device_type_base",
    {
        rest_url            : "{% url 'rest:network_device_type_list' %}"
        edit_template       : "network_device_type.html"
        delete_confirm_str  : (obj) -> return "Really delete Network '#{obj.identifier}' ?"
        template_cache_list : ["network_device_type_row.html", "network_device_type_head.html"]
        new_object          : {
            "identifier"  : "eth"
            "description" : "new network device type"
            "name_re"     : "^eth.*$"
            "mac_bytes"   : 6
            "allow_virtual_interfaces" : true
        }
        object_created  : (new_obj) -> new_obj.identifier = ""
    }
)

angular_add_mixin_list_controller(
    network_module,
    "network_base",
    {
        edit_template       : "network.html"
        rest_map            : [
            {"short" : "network"             , "url" : "{% url 'rest:network_list' %}", "options" : {"_with_ip_info" : true}}
            {"short" : "network_types"       , "url" : "{% url 'rest:network_type_list' %}"}
            {"short" : "network_device_types", "url" : "{% url 'rest:network_device_type_list' %}"}
        ]
        delete_confirm_str  : (obj) -> return "Really delete Network '#{obj.identifier}' ?"
        template_cache_list : ["network_row.html", "network_head.html"]
        new_object          : ($scope) ->
            return {
                "identifier"   : "new network",
                "network_type" : (entry["idx"] for key, entry of $scope.rest_data.network_types when typeof(entry) == "object" and entry and entry["identifier"] == "o")[0]
                "enforce_unique_ips" : true
                "num_ip"       : 0
            }
        # function dict, scope gets extended with it
        fn: 
            after_entries_set : () ->
                this.edit_scope.active_network = null
            get_defer : (q_type) ->
                d = this.fn_lut.q.defer()
                result = q_type.then(
                   (response) ->
                       d.resolve(response)
                )
                return d.promise
            show_network : (obj) ->
                es = this.edit_scope
                es.active_network = obj
                q_list = [
                    es.get_defer(es.fn_lut.Restangular.all("{% url 'rest:net_ip_list' %}".slice(1)).getList({"network" : obj.idx}))
                    es.get_defer(es.fn_lut.Restangular.all("{% url 'rest:netdevice_list' %}".slice(1)).getList({"net_ip__network" : obj.idx}))
                    es.get_defer(es.fn_lut.Restangular.all("{% url 'rest:device_list' %}".slice(1)).getList({"netdevice__net_ip__network" : obj.idx}))
                ]
                es.fn_lut.q.all(q_list).then((data) ->
                    es.ip_list = data[0]
                    es.netdevices = build_lut(data[1])
                    es.devices = build_lut(data[2])
                )
            get_production_networks : ($scope) -> 
                prod_idx = (entry for key, entry of $scope.rest_data.network_types when typeof(entry) == "object" and entry and entry["identifier"] == "p")[0].idx
                return (entry for key, entry of $scope.entries when typeof(entry) == "object" and entry and entry.network_type == prod_idx)
            is_slave_network : ($scope, nw_type) ->
                if nw_type
                    return (entry for key, entry of $scope.rest_data.network_types when typeof(entry) == "object" and entry and entry["idx"] == nw_type)[0].identifier == "s"
                else
                    return false
            has_master_network : (edit_obj) ->
                return if edit_obj.master_network then true else false
    }
)

{% endinlinecoffeescript %}

</script>
