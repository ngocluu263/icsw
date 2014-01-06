#!/usr/bin/python-init -Otu

from lxml.builder import E # @UnresolvedImport
import codecs
import logging_tools
import os
import process_tools
import server_command
import shutil
import stat

def _set_attributes(xml_el, log_com):
    try:
        if "user" in xml_el.attrib or "group" in xml_el.attrib:
            el_user = xml_el.get("user", "root")
            el_group = xml_el.get("group", "root")
            process_tools.change_user_group_path(xml_el.text, el_user, el_group, log_com=log_com)
        if "mode" in xml_el.attrib:
            os.chmod(xml_el.text, int(xml_el.get("mode"), 8))
    except:
        xml_el.attrib["error"] = "1"
        xml_el.attrib["error_str"] = process_tools.get_except_info()

def create_dir(srv_com, log_com):
    created, failed = (0, 0)
    for dir_entry in srv_com.xpath(".//ns:dir"):
        if not os.path.isdir(dir_entry.text):
            try:
                os.makedirs(dir_entry.text)
            except:
                dir_entry.attrib["error"] = "1"
                dir_entry.attrib["error_str"] = process_tools.get_except_info()
                failed += 1
            else:
                dir_entry.attrib["error"] = "0"
                created += 1
        else:
            dir_entry.attrib["error"] = "0"
        if not int(dir_entry.get("error", "0")):
            _set_attributes(dir_entry, log_com)
    srv_com.set_result(
        "created %s%s" % (
            logging_tools.get_plural("directory", created),
            " (%d failed)" % (failed) if failed else "",
            ),
        server_command.SRV_REPLY_STATE_ERROR if failed else server_command.SRV_REPLY_STATE_OK
        )

def set_file_content(srv_com, log_com):
    for file_entry in srv_com.xpath(".//ns:file"):
        try:
            if "encoding" in file_entry.attrib:
                codecs.open(file_entry.attrib["name"], "w", file_entry.attrib["encoding"]).write(file_entry.text)
            else:
                open(file_entry.attrib["name"], "r").write(file_entry.text)
        except:
            file_entry.attrib["error"] = "1"
            file_entry.attrib["error_str"] = process_tools.get_except_info()
        else:
            file_entry.attrib["error"] = "0"
        if not int(file_entry.get("error", "0")):
            _set_attributes(file_entry, log_com)
    srv_com.set_result(
        "stored file contents",
        )

def get_dir_tree(srv_com, log_com):
    for top_el in srv_com.xpath(".//ns:start_dir"):
        top_el.append(E.directory(full_path=top_el.text, start_dir="1"))
        for cur_dir, dir_list, file_list in os.walk(top_el.text):
            add_el = top_el.find(".//directory[@full_path='%s']" % (cur_dir))
            for new_dir in sorted(dir_list):
                add_el.append(
                    E.directory(
                        full_path=os.path.join(add_el.attrib["full_path"], new_dir),
                        path=new_dir
                    )
                )
            for new_file in sorted(file_list):
                add_el.append(
                    E.file(
                        name=new_file,
                        size="%d" % (os.stat(os.path.join(cur_dir, new_file))[stat.ST_SIZE]),
                        ))
        for cur_idx, cur_el in enumerate(top_el.findall(".//*")):
            cur_el.attrib["idx"] = "%d" % (cur_idx)
    srv_com.set_result(
        "read directory tree"
        )
    
def remove_dir(srv_com, log_com):
    created, failed = (0, 0)
    for dir_entry in srv_com.xpath(".//ns:dir"):
        if os.path.isdir(dir_entry.text):
            try:
                if int(dir_entry.get("recursive", "0")):
                    shutil.rmtree(dir_entry.text)
                else:
                    os.rmdir(dir_entry.text)
            except:
                dir_entry.attrib["error"] = "1"
                dir_entry.attrib["error_str"] = process_tools.get_except_info()
                failed += 1
            else:
                dir_entry.attrib["error"] = "0"
                created += 1
        else:
            dir_entry.attrib["error"] = "0"
    srv_com.set_result(
        "removed %s%s" % (
            logging_tools.get_plural("directory", created),
            " (%d failed)" % (failed) if failed else "",
            ),
            server_command.SRV_REPLY_STATE_ERROR if failed else server_command.SRV_REPLY_STATE_OK
        )

def get_file_content(srv_com, log_com):
    for file_entry in srv_com.xpath(".//ns:file"):
        if os.path.isfile(file_entry.attrib["name"]):
            try:
                if "encoding" in file_entry.attrib:
                    content = codecs.open(file_entry.attrib["name"], "r", file_entry.attrib["encoding"]).read()
                else:
                    content = open(file_entry.attrib["name"], "r").read()
            except:
                file_entry.attrib["error"] = "1"
                file_entry.attrib["error_str"] = "error reading: %s" % (process_tools.get_except_info())
            else:
                try:
                    file_entry.text = content
                except:
                    file_entry.attrib["error"] = "1"
                    file_entry.attrib["error_str"] = "error setting content: %s" % (process_tools.get_except_info())
                else:
                    file_entry.attrib["error"] = "0"
                    file_entry.attrib["size"] = "%d" % (len(content))
                    file_entry.attrib["lines"] = "%d" % (content.count("\n") + 1)
        else:
            file_entry.attrib["error"] = "1"
            file_entry.attrib["error_str"] = "file does not exist"
    srv_com.set_result(
        "read file contents",
    )
