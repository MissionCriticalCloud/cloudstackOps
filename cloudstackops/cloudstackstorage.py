#      Copyright 2015, Schuberg Philis BV
#
#      Licensed to the Apache Software Foundation (ASF) under one
#      or more contributor license agreements.  See the NOTICE file
#      distributed with this work for additional information
#      regarding copyright ownership.  The ASF licenses this file
#      to you under the Apache License, Version 2.0 (the
#      "License"); you may not use this file except in compliance
#      with the License.  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#      Unless required by applicable law or agreed to in writing,
#      software distributed under the License is distributed on an
#      "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
#      KIND, either express or implied.  See the License for the
#      specific language governing permissions and limitations
#      under the License.

# Class with Hypervisor storage methods

import sys
import time
import os

# Import the class we depend on
from cloudstackops import *
from cloudstackopsssh import *
from cloudstackopsbase import *

# Fabric
from fabric import *
from fabric import api as fab
from fabric.api import run, env, prefix, output, settings


class StorageHelper():

    def __init__(self, remote_ssh_key='~/.ssh/id_rsa.pub', remote_ssh_user='root', remote_ssh_password='password', remote_timeout=10, debug=0):

        self.debug = debug

        # fabric settings
        env.user = remote_ssh_user
        env.password = remote_ssh_password
        env.forward_agent = True
        env.disable_known_hosts = True
        env.parallel = False
        env.pool_size = 1
        env.timeout = remote_timeout
        env.abort_on_prompts = True

        # prevent warnings on remote host
        os.environ['LC_CTYPE'] = 'C'

        # Supress Fabric output by default, unless debug level has been set
        if self.debug > 0:
            output['debug'] = True
            output['running'] = True
            output['stdout'] = True
            output['stdin'] = True
            output['output'] = True
            output['warnings'] = True
        else:
            output['debug'] = False
            output['running'] = False
            output['stdout'] = False
            output['stdin'] = False
            output['output'] = False
            output['warnings'] = False

    # generic method to run remote commands via fabric
    def _remote_cmd(self, hostname, cmd):

        returncode = '0'
        result = ''
        output = ''
        errormsg = ''

        try:
            if self.debug > 0:
                print "[DEBUG]: Running remote command: ", cmd, " on", env.user + "@" + hostname

            with settings(host_string=env.user + "@" + hostname, warn_only=True, capture=False):
                result = fab.run(command=cmd)

        except Exception as error:
            errormsg = error
            returncode = '-1'

        finally:

            if result:
                if self.debug > 0:
                    print "[DEBUG]: command success:", result.succeeded, "command failed:", result.failed, "command returncode:", result.return_code, "command error:", result.stderr

                returncode = result.return_code
                output = result.stdout

                if result.failed:
                    errormsg = result.stdout

            return (returncode, output, errormsg)

    # returns a dict of mounts on remote host
    # dict is structured <mountpoint> : <device/export>
    def list_mounts(self, hostname):
        mount_file = '/proc/mounts'
        remote_cmd = "cat " + mount_file
        mount_list = {}

        returncode, output, errmsg = self._remote_cmd(hostname, remote_cmd)

        if returncode == 0:

            for mount in output.split('\r\n'):
                mount = mount.split(' ')

                mount_device = mount[0]
                mount_path = mount[1]
                mount_list[mount_path] = mount_device

        else:
            print "[ERROR]: Failed to retrieve list of mounts on " + hostname + " due to: ", errmsg

        return mount_list

    # returns a remote mountpoint for a given devicepath
    def get_mountpoint(self, hostname, device_path):

        mount_list = self.list_mounts(hostname)
        mountpoint = None

        if device_path.endswith('/'):
            # strip the slash
            device_path = device_path[:-1]

        if len(mount_list) > 0:
            for path, device in mount_list.iteritems():

                if device.endswith('/'):
                    # strip the slash
                    device = device[:-1]

                if device == device_path:

                    mountpoint = path

        return mountpoint

    # returns a dict of remote files and size (mb) for a given hostname and
    # path
    def list_files(self, hostname, path):

        file_list = {}

        if path is not '':
            remote_cmd = "find -H " + path + " -type f -exec du -sm {} \;"
            returncode, output, errmsg = self._remote_cmd(hostname, remote_cmd)

            if returncode == 0:

                for line in output.split('\r\n'):
                    line = line.split('\t')

                    file_size = line[0]
                    file_path = line[1]

                    file_list[file_path] = file_size

            else:
                print "[ERROR]: Failed to retrieve list from " + hostname + "of file due to: ", output, errmsg

        return file_list
