{% load coffeescript staticfiles %}

<script type="text/javascript">

{% inlinecoffeescript %}

root = exports ? this

show_device_info = (event, dev_key, callback) ->
    new device_info(event, dev_key, callback).show()

class device_info
    constructor: (@event, @dev_key, @callback=undefined) ->
        @addon_devices = []
    show: () =>
        @replace_div = {% if index_view %}true{% else %}false{% endif %}
        $.ajax
            url     : "{% url 'device:device_info' %}"
            data    :
                "key"    : @dev_key
            success : (xml) =>
                if parse_xml_response(xml)
                    @resp_xml = $(xml).find("response")
                    @network_list = @resp_xml.find("network_list network")
                    @permissions = @resp_xml.find("permissions")
                    @build_div()
                    if @replace_div
                        $("div#center_deviceinfo").children().remove().end().append(@dev_div)
                    else
                        @dev_div.simplemodal
                            opacity      : 50
                            position     : [@event.pageY, @event.pageX]
                            autoResize   : true
                            autoPosition : true
                            minWidth     : "800px"
                            onShow: (dialog) -> 
                                dialog.container.draggable()
                                $("#simplemodal-container").css("height", "auto")
                                $("#simplemodal-container").css("width", "auto")
                            onClose: =>
                                $.simplemodal.close()
                                if @callback
                                    @callback(@dev_key)
    get_pk_list: (with_md=true) =>
        # get all pks
        pk_list = [@resp_xml.find("device").attr("pk")]
        for addon_key in @addon_devices
            pk_list.push(addon_key.split("__")[1]) 
        return pk_list
    fqdn_compound: (in_dict) =>
        dev_key = in_dict["id"].split("__")[0..1].join("__")
        el_name = in_dict["id"].split("__")[2]
        dev_xml = @resp_xml.find("device[key='#{dev_key}']")
        other_list = []
        if el_name == "name"
            other_name = "domain_tree_node"
        else
            other_name = "name"
        other_id = "#{dev_key}__#{other_name}"
        in_dict[other_id] = dev_xml.attr(other_name)
        other_list.push(other_id)
        in_dict.other_list = other_list.join("::")
    has_perm: (perm_name) =>
        return if @permissions.find("permissions[permission='#{perm_name}']").length then true else false 
    build_div: () =>
        dev_xml = @resp_xml.find("device")
        @my_submitter = new submitter({
            master_xml       : dev_xml
            modify_data_dict : @fqdn_compound
        })
        dev_div = $("<div>")
        dev_div.append(
            $("<h3>").text("Device #{dev_xml.attr('full_name')}")
        )
        tabs_div = $("<div>").attr("id", "tabs")
        dev_div.append(tabs_div)
        if @addon_devices.length
            num_devs = @addon_devices.length + 1
            addon_text = " (#{num_devs})"
        else
            addon_text = ""
        tabs_div.append(
            $("<ul>").append(
                $("<li>").append($("<a>").attr("href", "#general").text("General")),
                $("<li>").append($("<a>").attr("href", "#category").text("Category")),
                $("<li>").append($("<a>").attr("href", "#location").text("Location")),
                if @has_perm("change_network") then $("<li>").append($("<a>").attr("href", "#network").text("Network#{addon_text}")) else null,
                $("<li>").append($("<a>").attr("href", "#config").text("Config#{addon_text}")),
                $("<li>").append($("<a>").attr("href", "#disk").text("Disk#{addon_text}")),
                $("<li>").append($("<a>").attr("href", "#mdcds").text("MD data store")),
                $("<li>").append($("<a>").attr("href", "#livestatus").text("Livestatus#{addon_text}")),
                $("<li>").append($("<a>").attr("href", "#monconfig").text("MonConfig#{addon_text}")),
                if @has_perm("show_graphs") then $("<li>").append($("<a>").attr("href", "#rrd").text("Graphs#{addon_text}")) else null,
            )
        )
        @dev_div = dev_div
        tabs_div.append(@general_div(dev_xml))
        tabs_div.append(@category_div(dev_xml))
        tabs_div.append(@location_div(dev_xml))
        if @has_perm("change_network")
            tabs_div.append(@network_div(dev_xml))
        tabs_div.append(@config_div(dev_xml))
        tabs_div.append(@disk_div(dev_xml))
        tabs_div.append(@mdcds_div(dev_xml))
        tabs_div.append(@livestatus_div(dev_xml))
        tabs_div.append(@monconfig_div(dev_xml))
        if @has_perm("show_graphs")
            tabs_div.append(@rrd_div(dev_xml))
        tabs_div.tabs(
            activate : @activate_tab
        )
        @config_init = false
        @livestatus_init = false
        @monconfig_init = false
        @diskinfo_init = false
        @rrd_init = false
        @network_init = false
    activate_tab: (event, ui) =>
        t_href = ui.newTab.find("a").attr("href")
        if t_href == "#config"
            if not @config_init
                @config_init = true
                # lazy load config
                angular.bootstrap(ui.newPanel.find("div[id='icsw.device.config.local']"), ["icsw.device.config"])
        else if t_href == "#livestatus"
            if not @livestatus_init
                @livestatus_init = true
                angular.bootstrap(ui.newPanel.find("div[id='icsw.device.livestatus']"), ["icsw.device.livestatus"])
        else if t_href == "#monconfig"
            if not @monconfig_init
                @monconfig_init = true
                angular.bootstrap(ui.newPanel.find("div[id='icsw.device.monconfig']"), ["icsw.device.livestatus"])
        else if t_href == "#disk"
            if not @diskinfo_init
                @diskinfo_init = true
                angular.bootstrap(ui.newPanel.find("div[id='icsw.device.partinfo']"), ["icsw.device.config"])
        else if t_href == "#rrd"
            if not @rrd_init
                @rrd_init = true
                angular.bootstrap(ui.newPanel.find("div[id='icsw.device.rrd']"), ["icsw.device.rrd"])
        else if t_href == "#network"
            if not @network_init
                @network_init = true
                angular.bootstrap(ui.newPanel.find("div[id='icsw.device.network']"), ["icsw.network.device"])
    general_div: (dev_xml) =>
        # general div
        general_div = $("<div>").attr("id", "general")
        # working :-)
        general_div.html(@resp_xml.find("forms general_form").text())
        #console.log(@resp_xml.find("forms general_form")[0])
        general_div.find("input, select").bind("change", @my_submitter.submit)
        @uuid_div = null
        general_div.find("input[name='uuid']").on("click", @show_uuid_info)
        return general_div
    show_uuid_info: (event) => 
        cur_el = $(event.target)
        if @uuid_div
            cur_el.val("show UUID info")
            @uuid_div.remove()
            @uuid_div = null
        else
            cur_el.val("hide UUID info")
            @uuid_div = $("<div>").
                append(
                    $("<h4>").text("Copy the following snippet to /etc/sysconfig/cluster/.cluster_device_uuid :"),
                    $("<pre>").
                        css("font-family", "courier").
                        css("font-size", "12pt").
                        css("display", "block").
                        text("urn:uuid:" + @resp_xml.find("device").attr("uuid")),
                    $("<h4>").text("and restart host-monitoring .")
                )
            cur_el.after(@uuid_div)
    category_div: (dev_xml) =>
        cat_div = $("<div>").attr("id", "category")
        tree_div = $('<div id="cat_tree"><div id="icsw.device.category.local"><div ng-controller="category_ctrl"><tree treeconfig="cat_tree"></tree></div></div></div>')
        angular.bootstrap(tree_div.find("div[id='icsw.device.category.local']"), ["icsw.device.config"])
        angular.element(tree_div.find("div[ng-controller='category_ctrl']")).scope().set_xml_entries(
            # device pk
            @resp_xml.find("device").attr("pk")
            # selected categories
            (parseInt(_entry) for _entry in @resp_xml.find("device").attr("categories").split("::"))
            # XML tree
            @resp_xml.find("categories category[full_name^='/device']")
            # call digest() after init to force redraw
            true
        )
        cat_div.append(tree_div)
        return cat_div
    location_div: (dev_xml) =>
        loc_div = $("<div>").attr("id", "location")
        tree_div = $('<div id="cat_tree"><div id="icsw.device.location.local"><div ng-controller="location_ctrl"><tree treeconfig="loc_tree"></tree></div></div></div>')
        angular.bootstrap(tree_div.find("div[id='icsw.device.location.local']"), ["icsw.device.config"])
        angular.element(tree_div.find("div[ng-controller='location_ctrl']")).scope().set_xml_entries(
            # device pk
            @resp_xml.find("device").attr("pk")
            # selected categories
            (parseInt(_entry) for _entry in @resp_xml.find("device").attr("categories").split("::"))
            # XML tree
            @resp_xml.find("categories category[full_name^='/location']")
            # call digest() after init to force redraw
            true
        )
        loc_div.append(tree_div)
        return loc_div
    network_div: (dev_xml) =>
        # network div
        pk_list = @get_pk_list() 
        net_div = $("<div>").attr("id", "network")
        dis_modal = if @replace_div then 0 else 1
        net_div.append($("<div id='icsw.device.network'><div ng-controller='network_ctrl'><devicenetworks devicepk='" + pk_list.join(",") + "' disablemodal='#{dis_modal}'></devicenetworks></div></div>"))
        return net_div
    config_div: (dev_xml) =>
        # configuration div
        pk_list = @get_pk_list() 
        conf_div = $("<div>").attr("id", "config")
        conf_div.append($("""
            <div id='icsw.device.config.local'>
                <div ng-controller='config_ctrl'>
                    <deviceconfig devicepk='#{pk_list}'>
                    </deviceconfig>
                </div>
                <div ng-controller='config_vars_ctrl'>
                    <deviceconfigvars devicepk='#{pk_list}'>
                    </deviceconfigvars>
                </div>
            </div>
        """))
        return conf_div
    livestatus_div: (dev_xml) =>
        # configuration div
        pk_list = @get_pk_list() 
        ls_div = $("<div>").attr("id", "livestatus")
        ls_div.append($("<div id='icsw.device.livestatus'><div ng-controller='livestatus_ctrl'><livestatus devicepk='" + pk_list.join(",") + "'></livestatus></div></div>"))
        return ls_div
    monconfig_div: (dev_xml) =>
        # monitoring config div
        pk_list = @get_pk_list() 
        mc_div = $("<div>").attr("id", "monconfig")
        mc_div.append($("<div id='icsw.device.monconfig'><div ng-controller='monconfig_ctrl'><monconfig devicepk='" + pk_list.join(",") + "'></monconfig></div></div>"))
        return mc_div
    rrd_div: (dev_xml) =>
        pk_list = @get_pk_list() 
        rrd_div = $("<div>").attr("id", "rrd")
        rrd_div.append($("<div id='icsw.device.rrd'><div ng-controller='rrd_ctrl'><rrdgraph devicepk='" + pk_list.join(",") + "'></rrdgraph></div></div>"))
        return rrd_div
        # rrd div
        return $("<div>").attr("id", "rrd")
    disk_div: (dev_xml) =>
        pk_list = @get_pk_list() 
        dsk_div = $("<div>").attr("id", "disk")
        dsk_div.append($("<div id='icsw.device.partinfo'><div ng-controller='partinfo_ctrl'><partinfo devicepk='" + pk_list.join(",") + "'></partinfo></div></div>"))
        return dsk_div
    mdcds_div: (dev_xml) =>
        # md check data store div
        mdcds_div = $("<div>").attr("id", "mdcds")
        num_mdcds = dev_xml.find("md_check_data_store").length
        if num_mdcds
            mdcds_div.append($("<h3>").text("#{num_mdcds} entries found"))
            dev_xml.find("md_check_data_stores md_check_data_store").each (idx, cur_ds) =>
                cur_ds = $(cur_ds)
                mdcds_div.append(
                    $("<div>").text(cur_ds.attr("name")).append(
                        $("<textarea>").attr("id", "cm01").text(cur_ds.attr("data"))
                    )
                )
                cur_ed = CodeMirror.fromTextArea(mdcds_div.find("textarea")[0], {
                    "mode"         : {
                        "name"    : "xml",
                        "version" : "2"
                    },
                    "styleActiveLine" : true,
                    "lineNumbers"     : true,
                    "lineWrapping"    : true,
                    "indentUnit"      : 4,
                })
        else
            mdcds_div.append($("<h3>").text("No entries found"))
        return mdcds_div
    
root.show_device_info = show_device_info
root.device_info = device_info

{% endinlinecoffeescript %}

</script>

