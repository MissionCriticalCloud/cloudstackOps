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

import socket
import sys
import time
# We depend on these
import uuid

from fabric import api as fab
# Fabric
from fabric.api import (
    env,
    output,
    put,
    settings
)

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
    def __init__(self, ssh_user='root', threads=5, pre_empty_script='', post_empty_script='', post_reboot_script='',
                 helper_scripts_path=None):
        hypervisor.__init__(ssh_user, threads)
        self.ssh_user = ssh_user
        self.threads = threads
        self.pre_empty_script = pre_empty_script
        self.post_empty_script = post_empty_script
        self.post_reboot_script = post_reboot_script
        self.mountpoint = None
        self.migration_path = None
        self.helper_scripts_path = helper_scripts_path
        self.os_family = None
        self.DRYRUN = True
        self.PREPARE = False

    def prepare_kvm(self, kvmhost, storage_pool_uuid):
        if self.DRYRUN:
            print "Note: Would have created migration folder on /mnt/%s on random host" % storage_pool_uuid
            return True
        result = self.create_migration_nfs_dir(kvmhost, storage_pool_uuid)
        if self.DEBUG == 1:
            print "DEBUG: received this result:" + str(result)
        if result is False:
            print "Error: Could not prepare the migration folder on host " + kvmhost.name
            return False
        return True

    def get_migration_path(self):
        if self.migration_path is None:
            self.migration_path = self.mountpoint + "/migration/" + str(uuid.uuid4()) + "/"
        return self.migration_path

    def create_migration_nfs_dir(self, host, storage_pool_uuid):
        if len(storage_pool_uuid) == 0:
            print "Error: mountpoint cannot be empty"
            return False
        self.mountpoint = "/mnt/" + storage_pool_uuid
        print "Note: Creating migration folder %s on %s" % (self.get_migration_path(), host.name)
        try:
            with settings(host_string=self.ssh_user + "@" + host.ipaddress):
                command = "sudo mkdir -p " + self.get_migration_path()
                return fab.run(command)
        except:
            return False

    def download_volume(self, kvmhost, file_location, path):
        print "Note: Downloading disk from %s to host %s" % (file_location, kvmhost.name)
        try:
            with settings(host_string=self.ssh_user + "@" + kvmhost.ipaddress):
                command = "sudo rsync -av -P %s %s%s.vhd" % (file_location, self.get_migration_path(), path)

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
            print "Note: Skipping virt-v2v step due to --skip-virt-v2v flag"
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
                command = "cd %s; sudo qemu-img resize %s +2M" % (self.get_migration_path(), volume_uuid)
                return fab.run(command)
        except:
            return False

    def inject_drivers(self, kvmhost, volume_uuid):
        print "Note: Inject drivers into disk %s on host %s" % (volume_uuid, kvmhost.name)
        try:
            with settings(host_string=self.ssh_user + "@" + kvmhost.ipaddress, warn_only=True):
                command = "cd %s; sudo virt-v2v -i disk %s -o local -os ./" % (self.get_migration_path(), volume_uuid)
                output = fab.run(command)

                if output.failed and "The NTFS partition is in an unsafe state." in output:
                    print "Note: NTFS is in an unsafe state, trying to fix for disk %s on host %s" % (
                        volume_uuid, kvmhost.name
                    )
                    if self.ntfsfix(kvmhost, volume_uuid, output):
                        print "Note: Retrying to inject drivers into disk %s on host %s" % (volume_uuid, kvmhost.name)
                        output = fab.run(command).succeeded
                elif output.failed:
                    print output
                    return False

                return output
        except:
            return False

    def ntfsfix(self, kvmhost, volume_uuid, output):
        print "Note: Trying to fix NTFS on disk %s on host %s" % (volume_uuid, kvmhost.name)
        try:
            with settings(host_string=self.ssh_user + "@" + kvmhost.ipaddress, warn_only=True):
                for line in output.split('\n'):
                    if "Original error message: mount:" in line:
                        device = line.split(" ")[4]

                        print "Note: Fixing NTFS partition %s disk %s on host %s" % (device, volume_uuid, kvmhost.name)
                        command = "cd %s; sudo guestfish add %s : run : ntfsfix %s" % \
                                  (self.get_migration_path(), volume_uuid, device)
                        return fab.run(command).succeeded
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

    def vmware_virt_v2v(self, kvmhost, esxi_host, vmx_path):
        print "Note: Virt-v2v from VMware host: %s vmx-path: %s on kvm host: %s" % (
            esxi_host, vmx_path, kvmhost.name
        )
        try:
            with settings(host_string=self.ssh_user + "@" + kvmhost.ipaddress, warn_only=True):

                vmx_uri = "ssh://root@%s/%s" % (esxi_host, vmx_path)

                command = "cd %s; LIBGUESTFS_BACKEND=direct sudo -E virt-v2v -i vmx -it ssh \"%s\" -o local -of qcow2 -os ./" % \
                          (self.get_migration_path(), vmx_uri)

                output = fab.run(command)

                if output.failed:
                    print output
                    return False

                return output
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
        if self.DRYRUN and not self.PREPARE:
            print "Note: Would have uploaded scripts to %s" % host.name
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
                if len(self.post_reboot_script) > 0:
                    put(self.post_reboot_script,
                        '/tmp/' + self.post_reboot_script.split('/')[-1], mode=0755, use_sudo=True)
                put('kvm_check_bonds.sh',
                    '/tmp/kvm_check_bonds.sh', mode=0755, use_sudo=True)
            return True
        except:
            print "Error: Could not upload check scripts to host " + host.name + "."
            return False

    # Get bond status
    def get_bond_status(self, host):
        try:
            with settings(host_string=self.ssh_user + "@" + host.ipaddress, use_sudo=True):
                return fab.run("bash /tmp/kvm_check_bonds.sh bond0 | awk {'print $1'} | tr -d \":\"")
        except:
            return False

    # Get VM count of a hypervisor
    def host_get_vms(self, host):
        with settings(host_string=self.ssh_user + "@" + host.ipaddress, use_sudo=True):
            return fab.run("virsh list | grep running | wc -l")

    # Reboot host and execute scripts
    def host_reboot(self, host, halt_hypervisor=False, force_reset_hypervisor=False, skip_reboot_hypervisor=False):

        # Count VMs to be sure
        if self.host_get_vms(host) != "0":
            print "Error: Host " + host.name + " not empty, cannot reboot!"
            return False
        print "Note: Host " + host.name + " has no VMs running, continuing"

        # Execute post-empty-script
        if self.exec_script_on_hypervisor(host, self.post_empty_script) is False:
            print "Error: Executing script '" + self.post_empty_script + "' on host " + host.name + " failed."
            return False

        # Reboot methods: reboot, force-reset, halt
        try:
            with settings(host_string=self.ssh_user + "@" + host.ipaddress, command_timeout=10, use_sudo=True):
                if halt_hypervisor:
                    print "Note: Halting host %s in 60s. Undo with 'sudo shutdown -c'" % host.name
                    fab.run("sudo shutdown -h 1")
                elif force_reset_hypervisor:
                    print "Note: Immediately force-resetting host %s" % host.name
                    fab.run("sudo sync; sudo echo b > /proc/sysrq-trigger")
                elif skip_reboot_hypervisor:
                    print "Note: Skipping reboot on host %s" % host.name
                else:
                    print "Note: Rebooting host %s in 60s. Undo with 'sudo shutdown -c' " % host.name
                    fab.run("sudo shutdown -r 1")
        except:
            print "Warning: Got an exception on reboot/reset/halt, but that's most likely due to the the host " \
                  "shutting itself down, so ignoring it."

        # Check the host is really offline
        if not skip_reboot_hypervisor:
            self.check_offline(host)

        # Wait until the host is back
        self.check_connect(host)

        # Execute post-reboot-script
        if self.exec_script_on_hypervisor(host, self.post_reboot_script) is False:
            print "Error: Executing script '" + self.post_reboot_script + "' on host " + host.name + " failed."
            return False

        return True

    # Wait for hypervisor to become alive again
    def check_connect(self, host):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print "Note: Waiting for " + host.name + "(" + host.ipaddress + ") to return"
        while s.connect_ex((host.ipaddress, 22)) > 0:
            # Progress indication
            sys.stdout.write(".")
            sys.stdout.flush()
            time.sleep(5)
        # Remove progress indication
        sys.stdout.write("\033[F")
        print "Note: Host " + host.name + " responds to SSH again!                           "
        time.sleep(10)
        print "Note: Waiting until we can successfully run a command against the cluster.."
        while self.check_libvirt(host) is False:
            # Progress indication
            sys.stdout.write(".")
            sys.stdout.flush()
            time.sleep(5)
        # Remove progress indication
        sys.stdout.write("\033[F")
        print "Note: Host " + host.name + " is able to do libvirt stuff again!                                  "
        return True

    # Check if we can use libvirt
    def check_libvirt(self, host):
        try:
            with settings(warn_only=True, host_string=self.ssh_user + "@" + host.ipaddress, use_sudo=True):
                result = fab.run("virsh list")
                if result.return_code == 0:
                    return True
                else:
                    return False
        except:
            return False

    # Get current patchlevel
    def get_patch_level(self, hosts):
        return_string = ""
        for host in sorted(hosts, key=lambda h: h.name):
            try:
                with settings(host_string=self.ssh_user + "@" + host.ipaddress, use_sudo=True):
                    patch_level = fab.run("yum check-update -q | wc -l") + " updates"
                    if len(return_string) == 0:
                        hostname = host.name.split('.')[0]
                    else:
                        hostname = "\n" + host.name.split('.')[0]
                    return_string = return_string + hostname + ": " + patch_level + " "
            except:
                return False
        return return_string
