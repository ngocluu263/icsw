<script type="text/javascript">

String.prototype.toTitle = function () {
    return this.replace(/\w\S*/g, function(txt){return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();});
};

AJAX_UUID = 0;
AJAX_DICT = new Object();

$.ajaxSetup({
    type       : "POST",
    timeout    : 50000,
    dataType   : "xml",
    beforeSend : function(xhr, settings) {
        xhr.inituuid = AJAX_UUID;
        AJAX_UUID++;
        AJAX_DICT[xhr.inituuid] = {
            "state" : "pending",
            "start" : new Date()
        };
        var ai_div = $("div#ajax_info");
        if (! ai_div.find("ul").length) {
            ai_div.append($("<ul>"));
        };
        ai_ul = ai_div.find("ul");
        ai_ul.append($("<li>").attr({
            "id" : xhr.inituuid
        }).text("pending..."));
    },
    complete   : function(xhr, textstatus) {
        AJAX_DICT[xhr.inituuid]["state"] = "done";
        AJAX_DICT[xhr.inituuid]["runtime"] = new Date() - AJAX_DICT[xhr.inituuid]["start"];
        var ai_div = $("div#ajax_info");
        ai_div.find("li#" + xhr.inituuid).remove();
    }
});

function draw_ds_tables(t_div, master_array) {
    t_div.children().remove();
    for (var key in master_array) {
        t_div.append(master_array[key].draw_table());
    };
    t_div.accordion({
        heightStyle : "content",
        collapsible : true
    });
};

function draw_setup(name, postfix, xml_name, create_url, delete_url, draw_array, kwargs) {
    this.name = name;
    this.postfix = postfix;
    this.xml_name = xml_name;
    // plural, plural(s) = ses and not ss (!)
    this.xml_name_plural = this.xml_name.match(/s$/) ? this.xml_name + "es" : this.xml_name + "s";
    this.create_url = create_url;
    this.delete_url = delete_url;
    this.required_xml = kwargs && (kwargs.required_xml || []) || [];
    this.lock_div = kwargs && (kwargs.lock_div || "") || "";
    this.drawn = false;
    this.draw_array = draw_array;
    for (var idx=0; idx < draw_array.length ; idx++) {
        draw_array[idx].draw_setup = this;
    };
    this.table_div = undefined;
    this.element_info = {};
    this.clean = function() {
        this.drawn = false;
        this.table_div = undefined;
        this.info_h3 = undefined;
    };
    function draw_table(master_xml) {
        this.master_xml = master_xml || MASTER_XML;
        if (this.table_div) {
            var table_div = this.table_div;
            var info_h3 = this.info_h3;
        } else {
            var table_div = $("<div>").attr({
                "id" : this.postfix
            });
            var info_h3 = $("<h3>").attr({"id" : this.postfix});
            table_div.append($("<table>").attr({"id" : this.postfix}).addClass("style2"));
        };
        var draw = true;
        var cur_ds = this;
        var missing_objects = []
        if (cur_ds.required_xml) {
            for (var idx=0; idx < cur_ds.required_xml.length; idx++) {
                var cur_req = cur_ds.required_xml[idx];
                var ref_obj = master_array[cur_req];
                if (ref_obj) {
                    var search_str = ref_obj.xml_name_plural + " " + ref_obj.xml_name;
                } else {
                    var search_str = cur_req + "s " + cur_req;
                };
                if (! cur_ds.master_xml.find(search_str).length) {
                    missing_objects.push(ref_obj ? ref_obj.name : cur_req);
                    draw = false;
                };
            };
        };
        var p_table = table_div.find("table");
        if (draw) {
            if (cur_ds.drawn) {
                p_table.find("tr[id]").each(function() {
                    var cur_tr = $(this);
                    cur_tr.find("select").each(function() {
                        var cur_sel = $(this);
                        for (idx=0 ; idx < cur_ds.draw_array.length; idx++) {
                            var cur_di = cur_ds.draw_array[idx];
                            var cur_re = new RegExp(cur_di.name + "$");
                            if (cur_sel.attr("id").match(cur_re)) {
                                if (cur_di.select_source) {
                                    sync_select_from_xml(cur_sel, cur_di);
                                };
                            };
                        };
                    });
                });
            } else {
                p_table.append(draw_head_line(cur_ds));
                if (cur_ds.create_url) p_table.append(draw_line(cur_ds));
                cur_ds.master_xml.find(this.xml_name_plural + " " + this.xml_name).each(function() {
                    p_table.append(draw_line(cur_ds, $(this)));
                });
                info_h3.text(cur_ds.name + " (").append(
                    $("<span>").attr({"id" : "info__" + this.postfix}).text("---")
                ).append($("<span>").text(")"));
                update_table_info(this, info_h3);
            };
        } else {
            if (this.drawn) {
                p_table.children().remove();
            };
            info_h3.text("parent objects missing for " + cur_ds.name + ": " + missing_objects.join(", "));
        };
        this.drawn = draw;
        if (!this.table_div) {
            this.table_div = table_div;
            this.info_h3 = info_h3;
            var dummy_div = $("<div>").append(info_h3).append(table_div);
            return dummy_div.children();
        };
    };
    this.draw_table = draw_table;
};

// info how to render a given XML-attribute
function draw_info(name, kwargs) {
    this.name = name;
    this.label = kwargs && (kwargs.label || name.toTitle()) || name.toTitle();
    this.span = kwargs && (kwargs.span || 1) || 1;
    var attr_list = ["size", "default", "select_source", "boolean", "min", "max", "ro",
        "button", "change_cb", "trigger", "draw_result_cb", "draw_conditional",
        "number", "manytomany", "add_null_entry", "newline", "cspan", "show_label", "group",
        "css", "select_source_attribute", "password", "keep_td"];
    for (idx=0 ; idx < attr_list.length; idx ++) {
        var attr_name = attr_list[idx];
        if (kwargs && kwargs.hasOwnProperty(attr_name)) {
            this[attr_name] = kwargs[attr_name];
        } else {
            this[attr_name] = undefined;
        };
    };
    this.size = kwargs && kwargs.size || undefined;
    function get_kwargs() {
        var attr_list = ["size", "select_source", "boolean", "min", "max", "ro", "button", "change_cb",
            "draw_result_cb", "trigger",
            "number", "manytomany", "add_null_entry", "css", "select_source_attribute", "password"];
        var kwargs = {new_default : this.default};
        for (idx=0 ; idx < attr_list.length; idx ++) {
            var attr_name = attr_list[idx];
            kwargs[attr_name] = this[attr_name];
        };
        if (this.show_label) {
            kwargs["label"] = this["label"];
        };
        if (this.group) {
            kwargs.modify_data_dict = this["modify_data_dict"];
            kwargs.modify_data_dict_opts = this;
        };
        kwargs.draw_info = this;
        return kwargs;
    };
    function modify_data_dict(in_dict, cur_di) {
        var other_list = [];
        var lock_list = ["#" + in_dict["id"]];
        var xml_pk = in_dict["id"].split("__");
        var xml_pk = xml_pk[xml_pk.length - 2];
        var element_info = cur_di.draw_setup.element_info[xml_pk];
        for (idx = 0; idx < cur_di.draw_setup.draw_array.length; idx++) {
            var other_dr = element_info[idx];
            if (other_dr.group == cur_di.group && other_dr.name != cur_di.name) {
                other_list.push(other_dr.element.attr("id"));
                lock_list.push("#" + other_dr.element.attr("id"));
                in_dict[other_dr.element.attr("id")] = get_value(other_dr.element);
            };
        };
        in_dict["other_list"] = other_list.join("::");
        in_dict["lock_list"] = lock_list;
    };
    this.modify_data_dict = modify_data_dict;
    this.get_kwargs = get_kwargs;
};

// storage node for rendered element
function draw_result(name, group, element) {
    this.name = name;
    this.group = group;
    this.element = element;
};

function draw_head_line(cur_ds) {
    var dummy_div = $("<div>");
    var head_line = $("<tr>").attr({
        "class" : "ui-widget-header ui-widget"
    });
    var cur_array = cur_ds.draw_array;
    var cur_span = 1;
    for (var idx=0; idx < cur_array.length ; idx++) {
        var cur_di = cur_array[idx];
        if (cur_di.newline) break;
        cur_span--;
        if (! cur_span) {
            var new_td = $("<th>").attr({"colspan" : cur_di.span}).text(cur_di.label);
            cur_span += cur_di.span;
        };
        head_line.append(new_td);
    };
    if (cur_ds.create_url) head_line.append($("<th>").text("action"));
    dummy_div.append(head_line);
    return dummy_div.children();
};

function draw_line(cur_ds, xml_el) {
    // cur_ds .... draw_setup
    // xml_el .... xml or undefined
    var dummy_div = $("<div>");
    if (xml_el === undefined) {
        var xml_pk = "new";
    } else {
        var xml_pk = xml_el.attr("pk");
    };
    var line_prefix = cur_ds.postfix + "__" + xml_pk;
    var n_line = $("<tr>").attr({
        "id"    : line_prefix,
        "class" : "ui-widget"
    });
    var el_list = [];
    dummy_div.append(n_line);
    var cur_array = cur_ds.draw_array;
    var cur_line = n_line;
    for (var idx=0; idx < cur_array.length ; idx++) {
        var cur_di = cur_array[idx];
        if (cur_di.newline) {
            var cur_line = $("<tr>").attr({
                "id"    : line_prefix,
                "class" : "ui-widget"
            });
            dummy_div.append(cur_line);
        };
        if (! cur_di.keep_td) {
            var new_td = $("<td>");
            if (cur_di.cspan) {
                new_td.attr({"colspan" : cur_di.cspan});
            };
            cur_line.append(new_td);
        };
        var kwargs = cur_di.get_kwargs();
        if (! cur_ds.create_url) {
            kwargs.ro = true;
        };
        // triggers only work for defined instances
        if ((cur_di.trigger && xml_el !== undefined) || ! cur_di.trigger) {
            // removed, not needed ?
            // kwargs.cur_ds = cur_ds;
            if (cur_di.draw_conditional) {
                var draw_el = cur_di.draw_conditional(xml_el);
            } else {
                var draw_el = true;
            }
        } else {
            var draw_el = false;
        }
        if (draw_el) {
            var new_els = create_input_el(xml_el, cur_di.name, line_prefix, kwargs);
            el_list.push(new draw_result(cur_di.name, cur_di.group, new_els.last()));
        } else {
            var new_els = [];
        };
        new_td.append(new_els);
    };
    cur_ds.element_info[xml_pk] = el_list;
    if (cur_ds.create_url) {
        n_line.append(
            $("<td>").append($("<input>").attr({
                "type"  : "button",
                "value" : xml_pk == "new" ? "create" : "delete",
                "id"    : line_prefix
            }).bind("click", function(event) { create_delete_element(event, cur_ds); })
        ));
    };
    return dummy_div.children();
};

function redraw_tables() {
    for (var key in master_array) {
        master_array[key].draw_table();
    };
};

function update_table_info(cur_ds, info_h3) {
    if (info_h3) {
        var info_span = info_h3.find("span#info__" + cur_ds.postfix);
    } else {
        var info_span = $("span#info__" + cur_ds.postfix);
    };
    info_span.text(cur_ds.master_xml.find(cur_ds.xml_name_plural + " " + cur_ds.xml_name).length);
};

function append_new_line(cur_el, new_xml, cur_ds) {
    var t_table = cur_el.parents("table:first");
    t_table.append(draw_line(cur_ds, new_xml));
};

function delete_line(cur_el) {
    var del_tr = cur_el.parents("tr:first");
    if (del_tr.attr("id")) {
        var del_table = del_tr.parents("table:first");
        del_table.find("tr#" + del_tr.attr("id")).remove();
    } else {
        del_tr.remove();
    };
};

function create_delete_element(event, cur_ds) {
    var cur_el = $(event.target);
    var el_id = cur_el.attr("id");
    if (cur_ds.lock_div) {
        var lock_list = lock_elements($("div#" + cur_ds.lock_div));
    } else {
        var lock_list = [];
    };
    if (el_id.match(/new$/)) {
        $.ajax({
            url  : cur_ds.create_url,
            data : create_dict($("table#" + cur_ds.postfix), el_id),
            success : function(xml) {
                if (parse_xml_response(xml)) {
                    var new_period = $(xml).find(cur_ds.xml_name);
                    cur_ds.master_xml.find(cur_ds.xml_name_plural).append(new_period);
                    append_new_line(cur_el, new_period, cur_ds);
                    cur_el.parents("tr:first").find("td input[id$='__name']").attr("value", "");
                    update_table_info(cur_ds);
                    redraw_tables();
                };
                unlock_elements(lock_list);
            }
        });
    } else {
        if (confirm("really delete " + cur_ds.name + " ?")) {
            $.ajax({
                url  : cur_ds.delete_url,
                data : create_dict($("table#" + cur_ds.postfix), el_id),
                success : function(xml) {
                    if (parse_xml_response(xml)) {
                        cur_ds.master_xml.find(cur_ds.xml_name + "[pk='" + el_id.split("__")[1] + "']").remove();
                        delete_line(cur_el);
                        update_table_info(cur_ds);
                        redraw_tables();
                    };
                    unlock_elements(lock_list);
                }
            });
        } else {
            unlock_elements(lock_list);
        };
    };
};

parse_xml_response = function(xml, min_level) {
    var success = false;
    // parse xml response from server
    if ($(xml).find("response header").length) {
        var ret_state = $(xml).find("response header").attr("code");
        if (parseInt(ret_state) < (min_level ? min_level : 40)) {
            // return true if we can parse the header and ret_code <= 40 (less than error)
            success = true;
        };
        $(xml).find("response header messages message").each(function() {
            var cur_mes = $(this);
            var cur_level = parseInt($(cur_mes).attr("log_level"));
            if (cur_level < 30) {
                $.jnotify($(cur_mes).text());
            } else if (cur_level == 30) {
                $.jnotify($(cur_mes).text(), "warning");
            } else {
                $.jnotify($(cur_mes).text(), "error", true);
            };
        });
    } else {
        $.jnotify("error parsing response", "error", true);
    };
    return success;
};

handle_ajax_ok = function(xml, ok_func) {
    if ($(xml).find("err_str").length) {
        var ret_value = false;
        alert($(xml).find("err_str").attr("value"));
    } else {
        var ret_value = true;
        if (ok_func == undefined) {
            if ($(xml).find("ok_str").length) {
                alert($(xml).find("ok_str").attr("value"));
            } else {
                alert("OK");
            }
        } else {
            ok_func(xml);
        }
    }
    return ret_value;
};

handle_ajax_error = function(xhr, status, except) {
    //alert(xhr.status + "," + status + ", " + except);
    if (status == "timeout") {
        alert("timeout");
    } else {
        if (xhr.status ) {
            // if status is != 0 an error has occured
            alert("*** " + status + " ***\nxhr.status : " + xhr.status + "\nxhr.statusText : " + xhr.statusText);
        }
    }
    return false;
}

function get_xml_value(xml, key) {
    var ret_value = undefined;
    $(xml).find("response values value[name='" + key + "']").each(function() {
        var value_xml =$(this);
        if ($(value_xml).attr("type") == "integer") {
            ret_value = parseInt($(value_xml).text());
        } else {
            ret_value = $(value_xml).text();
        };
    });
    return ret_value;
};

// lock all active input elements
function lock_elements(top_el) {
    var el_list = top_el.find("input:enabled", "select:enabled");
    el_list.attr("disabled", "disabled");
    return el_list;
};

// unlock list of elements
function unlock_elements(el_list) {
    el_list.removeAttr("disabled");
};

// get all attributes of a given select
function get_attribute_list(jq_sel, attr_name) {
    var new_list = [];
    jq_sel.each(function() { new_list.push($(this).attr(attr_name)); });
    return new_list;
};

// create a dictionary from a list of elements
function create_dict(top_el, id_prefix) {
    var in_list = top_el.find("input[id^='" + id_prefix + "'], select[id^='" + id_prefix + "'], textarea[id^='" + id_prefix + "']");
    var out_dict = {};
    in_list.each(function(idx, value) {
        var cur_el = $(this);
        if (cur_el.prop("tagName") == "TEXTAREA") {
            out_dict[cur_el.attr("id")] = cur_el.text();
        } else if (cur_el.is(":checkbox")) {
            out_dict[cur_el.attr("id")] = cur_el.is(":checked") ? "1" : "0";
        } else if (cur_el.prop("tagName") == "SELECT" && cur_el.attr("multiple")) {
            var sel_field = [];
            cur_el.find("option:selected").each(function(idx) {
                sel_field.push($(this).attr("value"));
            });
            out_dict[cur_el.attr("id")] = sel_field.join("::");
        } else {
            out_dict[cur_el.attr("id")] = cur_el.attr("value");
        };
    });
    return out_dict;
};

MASTER_XML = undefined;

function init_xml_change(master_el) {
    // set reference XML element
    MASTER_XML = master_el;
};

function replace_xml_element(xml) {
    // replace element in MASTER_XML
    xml.find("value[name='object'] > *").each(function() {
        var new_el = $(this);
        // FIXME; still referencing MASTER_XML
        MASTER_XML.find("[key='" + new_el.attr("key") + "']").replaceWith(new_el);
    });
};

function get_value(cur_el) {
    if (cur_el.is(":checkbox")) {
        var el_value = cur_el.is(":checked") ? "1" : "0";
    } else if (cur_el.prop("tagName") == "TEXTAREA") {
        var is_textarea = true;
        var el_value = cur_el.text();
    } else if (cur_el.prop("tagName") == "SELECT" && cur_el.attr("multiple")) {
        var sel_field = [];
        cur_el.find("option:selected").each(function(idx) {
            sel_field.push($(this).attr("value"));
        });
        var el_value = sel_field.join("::");
    } else {
        var el_value = cur_el.attr("value");
    };
    return el_value;
};

function set_value(el_id, el_value) {
    var cur_el = $("#" + el_id);
    cur_el.val(el_value);
};

function submit_change(cur_el, callback, modify_data_dict, modify_data_dict_opts) {
    var is_textarea = false;
    var el_value = get_value(cur_el);
    reset_value = false;
    if (cur_el.attr("type") == "password") {
        var check_pw = prompt("Please reenter password", "");
        if (check_pw != el_value) {
            alert("Password mismatch");
            return;
        } else {
            reset_value = true;
        };
    };
    var data_field = {
        "id"       : cur_el.attr("id"),
        "checkbox" : cur_el.is(":checkbox"),
        "value"    : el_value
    };
    if (modify_data_dict !== undefined) {
        modify_data_dict(data_field, modify_data_dict_opts);
    };
    if (data_field.lock_list) {
        lock_list = $(data_field.lock_list.join(", ")).attr("disabled", "disabled");
    } else {
        lock_list = undefined;
    };
    $.ajax({
        url  : "{% url base:change_xml_entry %}",
        data : data_field,
        success : function(xml) {
            if (parse_xml_response(xml)) {
                replace_xml_element($(xml));
                if (callback != undefined && typeof callback == "function") {
                    callback(cur_el);
                } else {
                    // set values
                    $(xml).find("changes change").each(function() {
                        var cur_os = $(this);
                        set_value(cur_os.attr("id"), cur_os.text());
                    });
                    if (reset_value) cur_el.val("");
                };
            } else {
                <!-- set back to previous value -->
                if (is_textarea) {
                    $(cur_el).text(get_xml_value(xml, "original_value"));
                } else {
                    $(cur_el).attr("value", get_xml_value(xml, "original_value"));
                };
                if (reset_value) cur_el.val("");
            };
            if (lock_list) unlock_elements(lock_list);
        }
    })
};

function in_array(in_array, s_str) {
    var res = false;
    for (var idx=0 ; idx < in_array.length; idx++) {
        if (in_array[idx] == s_str) {
            res = true;
            break;
        };
    };
    return res;
};

// resync select list
function sync_select_from_xml(cur_el, cur_di) {
    var old_pks = get_attribute_list(cur_el.find("option:selected"), "value");
    var kwargs = cur_di.get_kwargs();
    if (typeof(kwargs.select_source) == "string") {
        var sel_source = (kwargs.draw_info && (kwargs.draw_info.draw_setup.master_xml || MASTER_XML) || MASTER_XML).find(kwargs.select_source);
    } else if (typeof(kwargs.select_source) == "function") {
        var sel_source = kwargs.select_source(undefined);
    } else {
        var sel_source = kwargs.select_source;
    };
    cur_el.children().remove();
    if (kwargs.add_null_entry) {
        cur_el.append($("<option>").attr({"value" : "0"}).text(kwargs.add_null_entry));
    };
    sel_source.each(function() {
        var cur_ns = $(this);
        var new_opt = $("<option>").attr({"value" : cur_ns.attr("pk")}).text(cur_ns.text());
        if (in_array(cur_ns.attr("pk"), old_pks)) new_opt.attr("selected", "seleted");
        cur_el.append(new_opt);
    });
};

// get expansion list
function get_expand_td(line_prefix, name, title, cb_func) {
    return exp_td = $("<td>").append(
        $("<div>").attr({
            "class"   : "ui-icon ui-icon-triangle-1-e leftfloat",
            "id"      : line_prefix + "__expand__" + name,
            "title"   : title === undefined ? "show " + name : title
        })
    ).append(
        $("<span>").attr({
            "id"    : line_prefix + "__expand__" + name + "__info",
            "title" : title === undefined ? "show " + name : title
        }).text(name)
    ).bind("click", function(event) { toggle_config_line_ev(event, cb_func) ; }).mouseover(function () { $(this).addClass("highlight"); }).mouseout(function() { $(this).removeClass("highlight"); });
};

function toggle_config_line_ev(event, cb_func) {
    // get div-element
    var cur_el = $(event.target);
    if (cur_el.prop("tagName") != "TD") cur_el = cur_el.parent("td");
    cur_el = cur_el.children("div");
    var cur_class = cur_el.attr("class");
    var name = cur_el.attr("id").split("__").pop();
    var line_prefix = /^(.*)__expand__.*$/.exec(cur_el.attr("id"))[1];
    if (cur_class.match(/-1-e/)) {
        cur_el.removeClass("ui-icon-triangle-1-e ui-icon-triangle-1-s");
        cur_el.addClass("ui-icon-triangle-1-s");
        cb_func(line_prefix, true, name);
    } else {
        cur_el.removeClass("ui-icon-triangle-1-e ui-icon-triangle-1-s");
        cur_el.addClass("ui-icon-triangle-1-e");
        cb_func(line_prefix, false, name);
    }
};

function create_input_el(xml_el, attr_name, id_prefix, kwargs) {
    var dummy_div = $("<div>");
    kwargs = kwargs || {};
    if (kwargs["label"]) {
        dummy_div.append($("<label>").attr({"for" : attr_name}).text(kwargs["label"]));
    };
    if (kwargs["select_source"] === undefined) {
        if (kwargs.button) {
            // manual callback
            var new_el = $("<input>").attr({
                "type"  : "button",
                "id"    : id_prefix + "__" + attr_name
            });
            new_el.val(attr_name);
        } else if (kwargs.boolean) {
            // checkbox input style
            var new_el = $("<input>").attr({
                "type"  : "checkbox",
                "id"    : id_prefix + "__" + attr_name
            });
            if ((xml_el && xml_el.attr(attr_name) == "1") || (! xml_el && kwargs.new_default)) new_el.prop("checked", true);
        } else if (kwargs.textarea) {
            // textarea input style
            var new_el = $("<textarea>").attr({
                "id"    : id_prefix + "__" + attr_name
            }).text(xml_el === undefined ? (kwargs.new_default || "") : xml_el.attr(attr_name));
        } else {
            // text input style
            if (kwargs.ro) {
                // experimental, FIXME, too many if-levels
                var new_el = $("<span>").attr({
                    "id"    : id_prefix + "__" + attr_name
                }).text(xml_el === undefined ? (kwargs.new_default || (kwargs.number ? "0" : "")) : xml_el.attr(attr_name));
            } else {
                var new_el = $("<input>").attr({
                    "type"  : kwargs.password ? "password" : (kwargs.number ? "number" : "text"),
                    "id"    : id_prefix + "__" + attr_name,
                    "value" : xml_el === undefined ? (kwargs.new_default || (kwargs.number ? "0" : "")) : xml_el.attr(attr_name)
                });
            };
        };
        // copy attributes
        var attr_list = ["size", "min", "max"];
        for (idx=0 ; idx < attr_list.length; idx ++) {
            var attr_name = attr_list[idx];
            if (kwargs.hasOwnProperty(attr_name)) {
                new_el.attr(attr_name, kwargs[attr_name]);
            };
        }
    } else {
        // select input
        if (typeof(kwargs.select_source) == "string") {
            var sel_source = (kwargs.draw_info && (kwargs.draw_info.draw_setup.master_xml || MASTER_XML) || MASTER_XML).find(kwargs.select_source);
        } else if (typeof(kwargs.select_source) == "function") {
            var sel_source = kwargs.select_source(xml_el);
        } else {
            var sel_source = kwargs.select_source;
        };
        if (sel_source.length || kwargs.add_null_entry || kwargs.add_extra_entry) {
            var new_el = $("<select>").attr({
                "id"    : id_prefix + "__" + attr_name
            });
            if (kwargs["css"]) {
                $.each(kwargs["css"], function(key, value) {
                    new_el.css(key, value);
                });
            };
            if (kwargs.manytomany) {
                var sel_val = xml_el === undefined ? [] : xml_el.attr(attr_name).split("::");
                new_el.attr({
                    "multiple" : "multiple",
                    "size"     : 5
                });
            } else {
                var sel_val = xml_el === undefined ? "0" : xml_el.attr(attr_name);
                new_el.val(sel_val);//attr("value", sel_val);
            };
            if (kwargs.add_null_entry) {
                new_el.append($("<option>").attr({"value" : "0"}).text(kwargs.add_null_entry));
            };
            if (kwargs.add_extra_entry) {
                new_el.append($("<option>").attr({"value" : kwargs.extra_entry_id || "-1"}).text(kwargs.add_extra_entry));
            };
            sel_source.each(function() {
                var cur_ns = $(this);
                var new_opt = $("<option>").attr({"value" : cur_ns.attr("pk")});
                if (kwargs.select_source_attribute === undefined) {
                    new_opt.text(cur_ns.text());
                } else {
                    new_opt.text(cur_ns.attr(kwargs.select_source_attribute));
                };
                if (kwargs.manytomany) {
                    if (in_array(sel_val, cur_ns.attr("pk"))) new_opt.attr("selected", "selected");
                } else {
                    if (cur_ns.attr("pk") == sel_val) new_opt.attr("selected", "selected");
                };
                if (cur_ns.attr("data-image")) {
                    new_opt.attr("data-image", cur_ns.attr("data-image"));
                };
                new_el.append(new_opt);
            });
            //new_el.msDropdown();
        } else {
            if (kwargs.ignore_missing_source) {
                var new_el = $("<span>");
            } else {
                var new_el = $("<span>").addClass("error").text("no " + attr_name + " defined");
            };
        };
    };
    if (xml_el !== undefined && (kwargs.bind === undefined || kwargs.bind)) {
        if (kwargs.change_cb) {
            if (kwargs.button) {
                new_el.bind("click", kwargs.change_cb);
            } else {
                new_el.bind("change", kwargs.change_cb);
            };
            new_el.bind("change", kwargs.change_cb);
        } else {
            new_el.bind("change", function(event) {
                submit_change($(event.target), kwargs.callback, kwargs.modify_data_dict, kwargs.modify_data_dict_opts);
            })
        };
    } else if (kwargs.change_cb) {
        new_el.bind("change", kwargs.change_cb);
    };
    if (kwargs && kwargs.ro && new_el.get(0).tagName != "SPAN" && ! kwargs.trigger) {
        new_el.attr("disabled", "disabled");
    };
    dummy_div.append(new_el);
    if (kwargs && kwargs.draw_result_cb) dummy_div = kwargs.draw_result_cb(xml_el, dummy_div);
    return dummy_div.children();
};

</script>
