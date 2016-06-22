#!/usr/bin/python

#      Copyright 2016, Schuberg Philis BV
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

# We depend on these
import uuid

# Fabric
from fabric.api import *
from fabric import api as fab
from fabric import *
import hypervisor

# Set user/passwd for fabric ssh
env.user = 'root'
env.password = 'password'
env.forward_agent = True
env.disable_known_hosts = True
env.parallel = False
env.pool_size = 1

# Supress Fabric output by default, we will enable when needed
output['debug'] = False
output['running'] = False
output['stdout'] = False
output['stdin'] = False
output['output'] = False
output['warnings'] = False


class Kvm(hypervisor.hypervisor):

    def __init__(self, ssh_user='root', threads=5, pre_empty_script='', post_empty_script='', helper_scripts_path=None):
        hypervisor.__init__(ssh_user, threads)
        self.ssh_user = ssh_user
        self.threads = threads
        self.pre_empty_script = pre_empty_script
        self.post_empty_script = post_empty_script
        self.mountpoint = None
        self.migration_path = None
        self.helper_scripts_path = helper_scripts_path
        self.os_family = None

    def prepare_kvm(self, kvmhost):
        if self.DRYRUN:
            print "Note: Would have created migration folder on %s" % kvmhost.name
            return True
        result = self.create_migration_nfs_dir(kvmhost)
        if self.DEBUG == 1:
            print "DEBUG: received this result:" + str(result)
        if result is False:
            print "Error: Could not prepare the migration folder on host " + kvmhost.name
            return False
        return True

    def find_nfs_mountpoint(self, host):
        print "Note: Looking for NFS mount on KVM host %s" % host.name
        if self.mountpoint is not None:
            print "Note: Found " + str(self.mountpoint)
            return self.mountpoint
        try:
            with settings(host_string=self.ssh_user + "@" + host.ipaddress):
                command = "sudo mount | grep storage | awk {'print $3'}"
                self.mountpoint = fab.run(command)
                print "Note: Found " + str(self.mountpoint)
                return self.mountpoint
        except:
            return False

    def get_migration_path(self):
        if self.migration_path is None:
            self.migration_path = self.mountpoint + "/migration/" + str(uuid.uuid4()) + "/"
        return self.migration_path

    def create_migration_nfs_dir(self, host):
        mountpoint = self.find_nfs_mountpoint(host)
        if mountpoint is False:
            return False
        if len(mountpoint) == 0:
            print "Error: mountpoint cannot be empty"
            return False
        print "Note: Creating migration folder %s" % self.get_migration_path()
        try:
            with settings(host_string=self.ssh_user + "@" + host.ipaddress):
                command = "sudo mkdir -p " + self.get_migration_path()
                return fab.run(command)
        except:
            return False

    def download_volume(self, kvmhost, url, path):
        print "Note: Downloading disk from %s to host %s" % (url, kvmhost.name)
        try:
            with settings(host_string=self.ssh_user + "@" + kvmhost.ipaddress):
                command = "nice -n 19 sudo aria2c --file-allocation=none -c -m 5 -d %s -o %s.vhd %s" % \
                          (self.get_migration_path(), path, url)
                return fab.run(command)
        except:
            return False

    def make_kvm_compatible(self, kvmhost, path, virtvtov=True, partitionfix=True):
        result = self.convert_volume_to_qcow(kvmhost, path)
        if result is False:
            print "Error: Could not convert volume %s on host %s" % (path, kvmhost.name)
            return False
        if partitionfix is True:
            result = self.fix_partition_size(kvmhost, path)
            if result is False:
                print "Error: Could not fix partition of volume %s on host %s" % (path, kvmhost.name)
                return False
        if virtvtov is True:
            result = self.inject_drivers(kvmhost, path)
            if result is False:
                print "Error: Could not inject drivers on volume %s on host %s" % (path, kvmhost.name)
                return False
            if self.get_os_family(kvmhost, path) == "windows":
                registryresult = self.fix_windows_registry(kvmhost, path)
                if registryresult is False:
                    print "Error: Altering the registry failed."
                    return False
            result = self.modify_os_files(kvmhost, path)
            if result is False:
                print "Error: Could not modify disk %s on host %s" % (path, kvmhost.name)
                return False
            result = self.move_rootdisk_to_pool(kvmhost, path)
            if result is False:
                print "Error: Could not move rootvolume %s to the storage pool on host %s" % (path, kvmhost.name)
                return False
        else:
            result = self.move_datadisk_to_pool(kvmhost, path)
            if result is False:
                print "Error: Could not move datavolume %s to the storage pool on host %s" % (path, kvmhost.name)
                return False
            print "Note: Skipping virt-v2v step due to --skipVirtvtov flag"
        return True

    def convert_volume_to_qcow(self, kvmhost, volume_uuid):
        print "Note: Converting disk %s to QCOW2 on host %s" % (volume_uuid, kvmhost.name)
        try:
            with settings(host_string=self.ssh_user + "@" + kvmhost.ipaddress):
                command = "cd %s; nice -n 19 sudo qemu-img convert %s.vhd -O qcow2 %s" % (self.get_migration_path(),
                                                                             volume_uuid, volume_uuid)
                return fab.run(command)
        except:
            return False

    def fix_partition_size(self, kvmhost, volume_uuid):
        print "Note: Fixing virtual versus physical disksize %s on host %s" % (volume_uuid, kvmhost.name)
        try:
            with settings(host_string=self.ssh_user + "@" + kvmhost.ipaddress):
                command = "cd %s; sudo qemu-img resize %s +2MB" % (self.get_migration_path(), volume_uuid)
                return fab.run(command)
        except:
            return False

    def inject_drivers(self, kvmhost, volume_uuid):
        print "Note: Inject drivers into disk %s on host %s" % (volume_uuid, kvmhost.name)
        try:
            with settings(host_string=self.ssh_user + "@" + kvmhost.ipaddress):
                command = "cd %s; sudo virt-v2v -i disk %s -o local -os ./" % (self.get_migration_path(), volume_uuid)
                return fab.run(command)
        except:
            return False

    def fix_windows_registry(self, kvmhost, volume_uuid):
        print "Note: Setting UTC registry setting on disk %s on host %s" % (volume_uuid, kvmhost.name)
        try:
            with settings(host_string=self.ssh_user + "@" + kvmhost.ipaddress):
                command = "cd %s; sudo virt-win-reg %s-sda --merge utc.reg" % (self.get_migration_path(), volume_uuid)
                return fab.run(command)
        except:
            return False

    def get_os_family(self, kvmhost, volume_uuid):
        if self.os_family is not None:
            return self.os_family

        print "Note: Figuring out what OS Familiy the disk %s has" % volume_uuid

        try:
            with settings(host_string=self.ssh_user + "@" + kvmhost.ipaddress):
                command = "cd %s; sudo virt-inspector -a %s 2>/dev/null | virt-inspector --xpath  " \
                          "\"string(//operatingsystems/operatingsystem/name)\"" % \
                          (self.get_migration_path(), volume_uuid)
                self.os_family = fab.run(command)
                print "Note: This is a VM of the %s Family" % self.os_family.title()
                return self.os_family
        except:
            return False

    def modify_os_files(self, kvmhost, volume_uuid):
        print "Note: Getting rid of XenServer legacy for disk %s on host %s" % (volume_uuid, kvmhost.name)

        os_family = self.get_os_family(kvmhost, volume_uuid).lower()
        print "Note: OS_Family var is '%s'" % os_family
        if os_family != "linux" and os_family != "windows":
            print "Note: Not Linux nor Windows! Trying to continue."
            return True
        try:
            with settings(host_string=self.ssh_user + "@" + kvmhost.ipaddress):
                command = "cd %s; sudo ./virt-customize-%s.sh %s" % \
                          (self.get_migration_path(), os_family, self.get_migration_path() + volume_uuid + "-sda")
                return fab.run(command)
        except:
            return False

    def move_rootdisk_to_pool(self, kvmhost, volume_uuid):
        print "Note: Moving disk %s into place on host %s" % (volume_uuid, kvmhost.name)
        try:
            with settings(host_string=self.ssh_user + "@" + kvmhost.ipaddress):
                command = "cd %s; sudo mv %s-sda %s/%s" % (self.get_migration_path(), volume_uuid, self.mountpoint,
                                                           volume_uuid)
                return fab.run(command)
        except:
            return False

    def move_datadisk_to_pool(self, kvmhost, volume_uuid):
        print "Note: Moving disk %s into place on host %s" % (volume_uuid, kvmhost.name)
        try:
            with settings(host_string=self.ssh_user + "@" + kvmhost.ipaddress):
                command = "cd %s; sudo mv %s %s/%s" % (self.get_migration_path(), volume_uuid, self.mountpoint,
                                                       volume_uuid)
                return fab.run(command)
        except:
            return False

    def put_scripts(self, host):
        if self.DRYRUN:
            print "Note: Would have scripts to %s" % host.name
            return True
        try:
            with settings(host_string=self.ssh_user + "@" + host.ipaddress):
                if self.helper_scripts_path is not None:
                    put(self.helper_scripts_path + '/*',
                        self.get_migration_path(), mode=0755, use_sudo=True)
                if len(self.pre_empty_script) > 0:
                    put(self.pre_empty_script,
                        '/tmp/' + self.pre_empty_script.split('/')[-1], mode=0755, use_sudo=True)
                if len(self.post_empty_script) > 0:
                    put(self.post_empty_script,
                        '/tmp/' + self.post_empty_script.split('/')[-1], mode=0755, use_sudo=True)
            return True
        except:
            print "Error: Could not upload check scripts to host " + host.name + "."
            return False
