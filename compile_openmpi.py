#!/usr/bin/python-init -Otu
#
# Copyright (c) 2007-2009,2012,2014 Andreas Lang-Nevyjel, init.at
#
# this file is part of cbc-tools
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License
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
""" compiles openmpi """

import argparse
import commands
import compile_tools
import cpu_database
import logging_tools
import os
import rpm_build_tools
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

OPENMPI_VERSION_FILE = "/opt/cluster/share/openmpi_versions"

class my_opt_parser(argparse.ArgumentParser):
    def __init__(self):
        argparse.ArgumentParser.__init__(self)
        # check for 64-bit Machine
        self.mach_arch = os.uname()[4]
        if self.mach_arch in ["x86_64", "ia64"]:
            is_64_bit = True
        else:
            is_64_bit = False
        self._read_openmpi_versions()
        target_dir = "/opt/libs/"
        fc_choices = sorted(["GNU",
                             "INTEL",
                             "PATHSCALE"])
        self.cpu_id = cpu_database.get_cpuid()
        self.add_argument("-c", type=str, dest="fcompiler", help="Set Compiler type [%(default)s]", action="store", choices=fc_choices, default="GNU")
        self.add_argument("--fpath", type=str, dest="fcompiler_path", help="Compiler Base Path, for instance /opt/intel/compiler-9.1 [%(default)s]", default="NOT_SET")
        self.add_argument("-o", type=str, dest="openmpi_version", help="Choose OpenMPI Version [%(default)s]", action="store", choices=self.version_dict.keys(), default=self.highest_version)
        self.add_argument("-d", type=str, dest="target_dir", help="Sets target directory [%(default)s]", default=target_dir, action="store")
        self.add_argument("--extra", type=str, dest="extra_settings", help="Sets extra options for configure, i.e. installation directory and package name [%(default)s]", action="store", default="")
        self.add_argument("--extra-filename", type=str, dest="extra_filename", help="Sets extra filename string [%(default)s]", action="store", default="")
        self.add_argument("--arch", type=str, dest="arch", help="Set package architecture [%(default)s]", default="")
        self.add_argument("--log", dest="include_log", help="Include log of make-command in README [%(default)s]", action="store_true", default=False)
        self.add_argument("-v", dest="verbose", help="Set verbose level [%(default)s]", action="store_true", default=False)
        self.add_argument("--release", dest="release", type=str, help="Set release [%(default)s]", default="1")
        self.add_argument("--without-mpi-selecter", dest="mpi_selector", default=True, action="store_false", help="disable support for MPI-Selector [%(default)s]")
        self.add_argument("--without-module", dest="module_file", default=True, action="store_false", help="disable support for modules [%(default)s]")
        self.add_argument("--without-hwloc", dest="hwloc", default=True, action="store_false", help="disable hwloc support [%(default)s]")
        if is_64_bit:
            # add option for 32-bit goto if machine is NOT 32 bit
            self.add_argument("--32", dest="use_64_bit", help="Set 32-Bit build [%(default)s]", action="store_false", default=True)
        else:
            self.add_argument("--64", dest="use_64_bit", help="Set 64-Bit build [%(default)s]", action="store_true", default=False)
    def parse(self):
        options = self.parse_args()
        self.options = options
        self.mpi_selector = options.mpi_selector
        self.module_file = options.module_file
        self.hwloc = options.hwloc
        self._check_compiler_settings()
        self.package_name = "openmpi-%s-%s-%s-%s%s" % (self.options.openmpi_version,
                                                       self.options.fcompiler,
                                                       self.small_version,
                                                       self.options.use_64_bit and "64" or "32",
                                                       self.options.extra_filename and "-%s" % (self.options.extra_filename.strip()) or "")
        self.openmpi_dir = "%s/%s" % (self.options.target_dir,
                                      self.package_name)
    def _check_compiler_settings(self):
        self.add_path_dict = {}
        if self.options.fcompiler == "GNU":
            if os.path.isdir(self.options.fcompiler_path):
                self.add_path_dict = {"LD_LIBRARY_PATH": ["%s/lib" % (self.options.fcompiler_path),
                                                          "%s/lib64" % (self.options.fcompiler_path)],
                                      "PATH"           : ["%s/bin" % (self.options.fcompiler_path)]}
                self.compiler_dict = {"CC"  : "%s/bin/gcc" % (self.options.fcompiler_path),
                                      "CXX" : "%s/bin/g++" % (self.options.fcompiler_path),
                                      "F77" : "%s/bin/gfortran" % (self.options.fcompiler_path),
                                      "FC"  : "%s/bin/gfortran" % (self.options.fcompiler_path)}
            else:
                self.compiler_dict = {"CC"  : "gcc",
                                      "CXX" : "g++",
                                      "F77" : "gfortran",
                                      "FC"  : "gfortran"}
            stat, out = commands.getstatusoutput("%s --version" % self.compiler_dict['CC'])
            if stat:
                raise ValueError, "Cannot get Version from gcc (%d): %s" % (stat, out)
            self.small_version = out.split(")")[1].split()[0]
            self.compiler_version_dict = {"GCC" : out}
        elif self.options.fcompiler == "INTEL":
            if os.path.isdir(self.options.fcompiler_path):
                bin_path = compile_tools.get_intel_path(self.options.fcompiler_path)
                self.add_path_dict = compile_tools.get_add_paths_for_intel(self.options.fcompiler_path)
                self.compiler_dict = {"CC"  : "icc",
                                      "CXX" : "icpc",
                                      "F77" : "ifort",
                                      "FC"  : "ifort"}
                ifort_out_lines, small_version = compile_tools.get_short_version_for_intel(self.options.fcompiler_path, "ifort")
                if not small_version:
                    sys.exit(-1)
                self.small_version = small_version
                ifort_out = "\n".join(ifort_out_lines)
                self.compiler_version_dict = {"ifort" : ifort_out}
                icc_out_lines, short_icc_version = compile_tools.get_short_version_for_intel(self.options.fcompiler_path, "icc")
                icc_out = "\n".join(icc_out_lines)
                self.compiler_version_dict = {"ifort" : ifort_out,
                                              "icc"   : icc_out}
            else:
                raise IOError, "Compiler base path '%s' for compiler setting %s is not a directory" % (self.options.fcompiler_path,
                                                                                                       self.options.fcompiler)
        elif self.options.fcompiler == "PATHSCALE":
            if os.path.isdir(self.options.fcompiler_path):
                self.add_path_dict = {"LD_LIBRARY_PATH": ["%s/lib" % (self.options.fcompiler_path)],
                                      "PATH"           : ["%s/bin" % (self.options.fcompiler_path)]}
                self.compiler_dict = {"CC"  : "pathcc",
                                      "CXX" : "pathCC",
                                      "F77" : "pathf95",
                                      "FC"  : "pathf95"}
                stat, pathf95_out = commands.getstatusoutput("%s/bin/pathf95 -dumpversion" % (self.options.fcompiler_path))
                if stat:
                    raise ValueError, "Cannot get Version from pathf95 (%d): %s" % (stat, pathf95_out)
                self.small_version = pathf95_out.split("\n")[0]
                self.compiler_version_dict = {"pathf95" : pathf95_out}
                stat, pathcc_out = commands.getstatusoutput("%s/bin/pathcc -dumpversion" % (self.options.fcompiler_path))
                if stat:
                    raise ValueError, "Cannot get Version from pathcc (%d): %s" % (stat, pathcc_out)
                self.compiler_version_dict = {"pathf95" : pathf95_out,
                                              "pathcc"   : pathcc_out}
            else:
                raise IOError, "Compiler base path '%s' for compiler setting %s is not a directory" % (self.options.fcompiler_path,
                                                                                                       self.options.fcompiler)
        else:
            raise ValueError, "Compiler settings %s unknown" % (self.options.fcompiler)
    def _read_openmpi_versions(self):
        if os.path.isfile(OPENMPI_VERSION_FILE):
            version_lines = [line.strip().split() for line in file(OPENMPI_VERSION_FILE, "r").read().split("\n") if line.strip()]
            self.version_dict = dict([(key, value) for key, value in version_lines])
            vers_dict = dict([(tuple([part.isdigit() and int(part) or part for part in key.split(".")]), key) for key in self.version_dict.keys()])
            vers_keys = sorted(vers_dict.keys())
            self.highest_version = vers_dict[vers_keys[-1]]
        else:
            raise IOError, "No %s found" % (OPENMPI_VERSION_FILE)
    def get_compile_options(self):
        return "\n".join([" - build_date is %s" % (time.ctime()),
                          " - openmpi Version is %s, cpuid is %s" % (self.options.openmpi_version,
                                                                     self.cpu_id),
                          " - Compiler is %s, Compiler Base path is %s" % (self.options.fcompiler,
                                                                           self.options.fcompiler_path),
                          " - small_version is %s" % (self.small_version),
                          " - source package is %s, target directory is %s" % (self.version_dict[self.options.openmpi_version],
                                                                               self.openmpi_dir),
                          " - extra_settings for configure: %s" % (self.options.extra_settings),
                          "compiler settings: %s" % ", ".join(["%s=%s" % (key, value) for key, value in self.compiler_dict.iteritems()]),
                          "add_path_dict    : %s" % ", ".join(["%s=%s:$%s" % (key, ":".join(value), key) for key, value in self.add_path_dict.iteritems()]),
                          "version info:"] + \
                         ["%s:\n%s" % (key, "\n".join(["    %s" % (line.strip()) for line in value.split("\n")])) for key, value in self.compiler_version_dict.iteritems()])

class openmpi_builder(object):
    def __init__(self, parser):
        self.parser = parser
    def build_it(self):
        self.compile_ok = False
        self._init_tempdir()
        if self._untar_source():
            if self._compile_it():
                if self.package_it():
                    self.compile_ok = True
                    self._remove_tempdir()
        if not self.compile_ok:
            print "Not removing temporary directory %s" % (self.tempdir)
    def _init_tempdir(self):
        self.tempdir = tempfile.mkdtemp("_openmpi")
    def _remove_tempdir(self):
        print "Removing temporary directory"
        shutil.rmtree(self.tempdir)
        try:
            os.rmdir(self.tempdir)
        except:
            pass
    def _untar_source(self):
        tar_source = self.parser.version_dict[self.parser.options.openmpi_version]
        if not os.path.isfile(tar_source):
            print "Cannot find OpenMPI source %s" % (tar_source)
            success = False
        else:
            print "Extracting tarfile %s ..." % (tar_source),
            tar_file = tarfile.open(tar_source, "r")
            tar_file.extractall(self.tempdir)
            tar_file.close()
            print "done"
            success = True
        return success
    def _compile_it(self):
        num_cores = cpu_database.global_cpu_info(parse=True).num_cores() * 2
        act_dir = os.getcwd()
        os.chdir("%s/openmpi-%s" % (self.tempdir, self.parser.options.openmpi_version))
        print "Modifying environment"
        for env_name, env_value in self.parser.compiler_dict.iteritems():
            os.environ[env_name] = env_value
        for path_name, path_add_value in self.parser.add_path_dict.iteritems():
            os.environ[path_name] = "%s:%s" % (":".join(path_add_value), os.environ.get(path_name, ""))
        self.time_dict, self.log_dict = ({}, {})
        # remove link if needed
        if os.path.islink("%s/etc/openmpi-mca-params.conf" % (self.parser.openmpi_dir)):
            os.unlink("%s/etc/openmpi-mca-params.conf" % (self.parser.openmpi_dir))
        success = True
        config_list = [("--prefix", self.parser.openmpi_dir)]
        if self.parser.hwloc:
            config_list.append(("--with-hwloc", "/opt/cluster"))
        for command, time_name in [("./configure %s %s" % (
            " ".join(["%s=%s" % (key, value) for key, value in config_list]),
            self.parser.options.extra_settings), "configure"),
                                   ("make -j %d" % (num_cores), "make"),
                                   ("make install", "install")]:
            self.time_dict[time_name] = {"start" : time.time()}
            print "Doing command %s" % (command)
            sp_obj = subprocess.Popen(command.split(), 0, None, None, subprocess.PIPE, subprocess.STDOUT)
            out_lines = []
            while True:
                stat = sp_obj.poll()
                while True:
                    try:
                        new_lines = sp_obj.stdout.next()
                    except StopIteration:
                        break
                    else:
                        if self.parser.options.verbose:
                            print new_lines,
                        if type(new_lines) == type([]):
                            out_lines.extend(new_lines)
                        else:
                            out_lines.append(new_lines)
                if stat is not None:
                    break
            self.time_dict[time_name]["end"] = time.time()
            self.time_dict[time_name]["diff"] = self.time_dict[time_name]["end"] - self.time_dict[time_name]["start"]
            self.log_dict[time_name] = "".join(out_lines)
            if stat:
                print "Something went wrong (%d):" % (stat)
                if not self.parser.options.verbose:
                    print "".join(out_lines)
                success = False
                break
            else:
                print "done, took %s" % (logging_tools.get_diff_time_str(self.time_dict[time_name]["diff"]))
        os.chdir(act_dir)
        return success
    def _create_module_file(self):
        self.modulefile_name = self.parser.package_name.replace("-", "_").replace("__", "_")
        targ_dir = "%s/module_dir" % (self.parser.openmpi_dir)
        dir_list = os.listdir(self.parser.openmpi_dir)
        if "lib64" in dir_list:
            lib_dir = "%s/lib64" % (self.parser.openmpi_dir)
        else:
            lib_dir = "%s/lib" % (self.parser.openmpi_dir)
        mod_lines = [
            "#%Module1.0",
            "",
            "append-path PATH %s/bin" % (self.parser.openmpi_dir),
            "append-path LD_LIBRARY_PATH %s" % (lib_dir),
            ""
            ]
        if not os.path.isdir(targ_dir):
            os.makedirs(targ_dir)
        file("%s/%s" % (targ_dir, self.modulefile_name), "w").write("\n".join(mod_lines))
    def _create_mpi_selector_file(self):
        self.mpi_selector_sh_name = "%s.sh" % (self.parser.package_name)
        self.mpi_selector_csh_name = "%s.csh" % (self.parser.package_name)
        self.mpi_selector_dir = "/var/mpi-selector/data"
        sh_lines = ['#PATH',
                    'if test -z "`echo $PATH | grep %s/bin`"; then' % (self.parser.openmpi_dir),
                    '    PATH="%s/bin:${PATH}"' % (self.parser.openmpi_dir),
                    '    export PATH',
                    'fi',
                    '# LD_LIBRARY_PATH',
                    'if test -z "`echo $LD_LIBRARY_PATH | grep %s/lib64`"; then' % (self.parser.openmpi_dir),
                    '    if [ -d "%s/lib64" ] ; then' % (self.parser.openmpi_dir),
                    '        LD_LIBRARY_PATH=%s/lib64:${LD_LIBRARY_PATH}' % (self.parser.openmpi_dir),
                    '        export LD_LIBRARY_PATH',
                    '    fi',
                    'fi',
                    'if test -z "`echo $LD_LIBRARY_PATH | grep %s/lib`"; then' % (self.parser.openmpi_dir),
                    '    if [ -d "%s/lib" ] ; then' % (self.parser.openmpi_dir),
                    '        LD_LIBRARY_PATH=%s/lib:${LD_LIBRARY_PATH}' % (self.parser.openmpi_dir),
                    '        export LD_LIBRARY_PATH',
                    '    fi',
                    'fi',
                    '',
                    '# MANPATH',
                    'if test -z "`echo $MANPATH | grep %s/share/man`"; then' % (self.parser.openmpi_dir),
                    '    MANPATH=%s/man:${MANPATH}' % (self.parser.openmpi_dir),
                    '    export MANPATH',
                    'fi']
        csh_lines = ['# path',
                     'if ("" == "`echo $path | grep %s/bin`") then',
                     '    set path=(%s/bin $path)',
                     'endif',
                     '',
                     '# LD_LIBRARY_PATH',
                     'if ("1" == "$?LD_LIBRARY_PATH") then',
                     '    if ("$LD_LIBRARY_PATH" !~ *%s/lib64*) then' % (self.parser.openmpi_dir),
                     '        setenv LD_LIBRARY_PATH %s/lib64:${LD_LIBRARY_PATH}' % (self.parser.openmpi_dir),
                     '    endif',
                     'else',
                     '    setenv LD_LIBRARY_PATH %s/lib64' % (self.parser.openmpi_dir),
                     'endif',
                     '',
                     '# MANPATH',
                     'if ("1" == "$?MANPATH") then',
                     '    if ("$MANPATH" !~ *%s/share/man*) then' % (self.parser.openmpi_dir),
                     '        setenv MANPATH %s/share/man:${MANPATH}' % (self.parser.openmpi_dir),
                     '    endif',
                     'else',
                     '    setenv MANPATH %s/share/man:' % (self.parser.openmpi_dir),
                     'endif']
        targ_dir = "%s/%s" % (self.tempdir, self.mpi_selector_dir)
        if not os.path.isdir(targ_dir):
            os.makedirs(targ_dir)
        file("%s/%s" % (targ_dir, self.mpi_selector_sh_name), "w").write("\n".join(sh_lines))
        file("%s/%s" % (targ_dir, self.mpi_selector_csh_name), "w").write("\n".join(csh_lines))
    def package_it(self):
        print "Packaging ..."
        info_name = "README.%s" % (self.parser.package_name)
        sep_str = "-" * 50
        readme_lines = [sep_str] + \
            self.parser.get_compile_options().split("\n") + \
            ["Compile times: %s" % (", ".join(["%s: %s" % (key, logging_tools.get_diff_time_str(self.time_dict[key]["diff"])) for key in self.time_dict.keys()])), sep_str, ""]
        if self.parser.options.include_log:
            readme_lines.extend(["Compile logs:"] + \
                                sum([self.log_dict[key].split("\n") + [sep_str] for key in self.log_dict.keys()], []))
        file("%s/%s" % (self.tempdir, info_name), "w").write("\n".join(readme_lines))
        package_name, package_version, package_release = (self.parser.package_name,
                                                          self.parser.options.openmpi_version,
                                                          self.parser.options.release)
        if self.parser.module_file:
            self._create_module_file()
        if self.parser.mpi_selector:
            self._create_mpi_selector_file()
        new_p = rpm_build_tools.build_package()
        if self.parser.options.arch:
            new_p["arch"] = self.parser.options.arch
        new_p["name"] = package_name
        new_p["version"] = package_version
        new_p["release"] = package_release
        new_p["package_group"] = "System/Libraries"
        new_p["inst_options"] = " -p "
        # remove config files
        for file_name in os.listdir("%s/etc" % (self.parser.openmpi_dir)):
            try:
                os.unlink("%s/etc/%s" % (self.parser.openmpi_dir, file_name))
            except:
                pass
        # generate empty hosts file
        file("%s/etc/openmpi-default-hostfile" % (self.parser.openmpi_dir), "w").write("")
        # generate link
        mca_local_file = "/etc/openmpi-mca-params.conf"
        os.symlink(mca_local_file, "%s/etc/openmpi-mca-params.conf" % (self.parser.openmpi_dir))
        # generate dummy file if not existent
        remove_mca = False
        if not os.path.exists(mca_local_file):
            remove_mca = True
            open(mca_local_file, "w").write("")
        # remove old info if present
        if os.path.isfile("%s/%s" % (self.parser.openmpi_dir, info_name)):
            os.unlink("%s/%s" % (self.parser.openmpi_dir, info_name))
        fc_list = [self.parser.openmpi_dir,
                   "%s/%s:%s/%s" % (self.tempdir, info_name, self.parser.openmpi_dir, info_name)]
        if self.parser.mpi_selector:
            fc_list.append("%s/%s/%s:/%s/%s" % (self.tempdir, self.mpi_selector_dir, self.mpi_selector_sh_name,
                                                self.mpi_selector_dir, self.mpi_selector_sh_name))
            fc_list.append("%s/%s/%s:/%s/%s" % (self.tempdir, self.mpi_selector_dir, self.mpi_selector_csh_name,
                                                self.mpi_selector_dir, self.mpi_selector_csh_name))
        content = rpm_build_tools.file_content_list(fc_list)
        new_p.create_tgz_file(content)
        new_p.write_specfile(content)
        new_p.build_package()
        if new_p.build_ok:
            print "Build successfull, package locations:"
            print new_p.long_package_name
            print new_p.src_package_name
            success = True
        else:
            print "Something went wrong, please check tempdir %s" % (self.tempdir)
            success = False
        if remove_mca:
            os.unlink(mca_local_file)
        return success

def main():
    my_parser = my_opt_parser()
    my_parser.parse()
    print my_parser.get_compile_options()
    my_builder = openmpi_builder(my_parser)
    my_builder.build_it()

if __name__ == "__main__":
    main()
    # print "update to use ***FLAGS=-O{1,2}!"
