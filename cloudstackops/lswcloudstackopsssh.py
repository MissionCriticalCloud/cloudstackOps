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

# Class to support SSH operations specific to Leaseweb
# Nuno Tavares - n.tavares@tech.leaseweb.com

# Import the class we depend on
from cloudstackopsssh import CloudStackOpsSSH
from lswcloudstackopsbase import LswCloudStackOpsBase

class LswCloudStackOpsSSH(CloudStackOpsSSH, LswCloudStackOpsBase):

    # MGMT servers are already checking the instances, we can use that cache
    def retrieveAlarmedInstancesCache(self, mgt_server):
        alarmedInstancesCache = {}
        self.debug(2, "Fetching alarmed instances cache...")
        mgtSsh = "grep -v -f /var/local/ack_readonly /tmp/vps_readonly 2>/dev/null || /bin/true"
        retcode, output = self.runSSHCommand(mgt_server, mgtSsh)
        self.debug(2, " + retcode=%d" % (retcode))
        
        import re
        lines = output.split('\n')
        for line in lines:
            m = re.match("(\S+) \[(.*)\]", line)
            if m:
                self.debug(2, "i: %s, h: %s" % (m.group(1), m.group(2)))
                alarmedInstancesCache[m.group(1)] = { 'alarm': 'read-only', 'name': m.group(1), 'host': m.group(2) }
        return alarmedInstancesCache

    # MGMT servers are already checking the routerVMs, we can use that cache
    def retrieveAlarmedRoutersCache(self, mgt_server):
        alarmedRoutersCache = {}
        self.debug(2, "Fetching alarmed routers cache...")
        mgtSsh = "cat /tmp/routervms_problem"
        retcode, output = self.runSSHCommand(mgt_server, mgtSsh)
        self.debug(2, " + retcode=%d" % (retcode))
        
        import re
        lines = output.split('\n')
        for line in lines:
            m = re.match("(\S+) \[(.*)\] (\d+)", line)
            if m:
                self.debug(2, "r: %s, n: %s, code: %s" % (m.group(1), m.group(2), m.group(3)))
                alarmedRoutersCache[m.group(1)] = { 'network': m.group(2), 'code': int(m.group(3)), 'checked': False }
        return alarmedRoutersCache

# ..........

    def examineHost(self,nodeSrv):
        if 'load-avg' in ENABLED_CHECKS_HOST:
            LOAD_AVG_MARGIN = 0.3
            nodeSsh = "echo \"$(grep ^processor /proc/cpuinfo  | wc -l) $(awk '{print $2}' /proc/loadavg)\""
            retcode, output = self.runSSHCommand(nodeSrv, nodeSsh)
            self.debug(2, "   + Load average check output: %s" % (output))
            
            (n_cpus, loadavg) = output.split(' ')
            n_cpus = int(n_cpus)
            loadavg = float(loadavg)
            self.debug(2, "   + Load average check: %d  + %.0f%% < %.1f" % (n_cpus, LOAD_AVG_MARGIN*100, loadavg))
            if loadavg > n_cpus*(1+LOAD_AVG_MARGIN):
                return { 'action': LswCloudStackOpsBase.ACTION_UNKNOWN, 'safetylevel': LswCloudStackOpsBase.SAFETY_NA, 'comment': 'Hypervisor under pressure (load): %.1f' % loadavg }

        if 'io-abuse' in ENABLED_CHECKS_HOST:
            self.debug(2, ' + Checking I/O abuse...')
            nodeSsh = "/usr/local/nagios/libexec/nrpe_local/check_libvirt_storage.sh"
            retcode, output = self.runSSHCommand(nodeSrv, nodeSsh)

            if retcode!=0:
                return { 'action': LswCloudStackOpsBase.ACTION_MANUAL, 'safetylevel': LswCloudStackOpsBase.SAFETY_NA, 'comment': 'check_libvirt_storage.sh seems to be failing' }

            lines = output.split('\n')
            instances = {}
            for line in lines:
                m = re.match("(\S+) (\S+) (\S+)", line)
                if m:
                    self.debug(2, " + check_libvirt_storage: i=%s, m=%s, level=%s" % (m.group(2), m.group(3), m.group(1)))
                    # For some reason, someone decided to change the instance name... 
                    i_name = m.group(2).replace('_', '-')
                    if i_name not in instances.keys():
                        instances[ i_name ] = []
                    instances[i_name] += [ m.group(3) ]
                    self.alarmedInstancesCache[i_name] = { 'alarm': 'io-abuse', 'host': host.name, 'level': m.group(1), 'metrics': instances[i_name] }
            if len(instances.keys())>=1:
                return { 'action': LswCloudStackOpsBase.ACTION_ESCALATE, 'safetylevel': LswCloudStackOpsBase.SAFETY_NA, 'comment': 'IOP abusing instances: '+ ','.join(instances.keys()) }

        if 'conntrack' in ENABLED_INSPECTIONS:
            CONNTRACK_RATIO_THRESHOLD_PC = 70
            self.debug(2, ' + Checking conntrack...')
            #mgtSsh = "ssh -At %s ssh -At -p 3922 -i /root/.ssh/id_rsa.cloud -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no root@%s ls -la" % (router.hostname, router.linklocalip)
            #nodeSsh = 'CT_MAX=$(cat /proc/sys/net/netfilter/nf_conntrack_max); CT_COUNT=$(cat /proc/sys/net/netfilter/nf_conntrack_count); awk \'BEGIN {printf "%.2f",\${CT_COUNT}/\${CT_MAX}}\''
            nodeSsh = "echo \"$(cat /proc/sys/net/netfilter/nf_conntrack_count) $(cat /proc/sys/net/netfilter/nf_conntrack_max)\""
            retcode, output = self.runSSHCommand(nodeSrv, nodeSsh)
            self.debug(2, "   + retcode=%d, output=%s" % (retcode, output))

            m = re.match("(\d+) (\d+)", output)
            if m:
                ct_cur = int(m.group(1))
                ct_max = int(m.group(2))
                self.debug(2, "   + conntrack: c=%d, max=%d" % (ct_cur, ct_max))
                ct_ratio = 100.0 * ct_cur / ct_max
                if ct_ratio > CONNTRACK_RATIO_THRESHOLD_PC:
                    return { 'action': LswCloudStackOpsBase.ACTION_MANUAL, 'safetylevel': LswCloudStackOpsBase.SAFETY_NA, 'comment': 'Conntrack abuse (' + "{:.2f}%".format(ct_ratio) + ')' }
        return None

    def testMgmtServerConnection(self, host):
        # Test connection to MGMT_SERVER, we are going to need it
        self.debug(2, "+ Testing SSH to '%s'" % (host))
        retcode, output = self.testSSHConnection(host)
        self.debug(2, "   + retcode=%d, output=%s" % (retcode, output))
        if retcode != 0:
            print "Failed to ssh to management server %s, please investigate." % (host)
            sys.exit(1)

        MGMT_SERVER_DATA = {}
        MGMT_SERVER_DATA['version'] = '__UNKNOWN__'
        MGMT_SERVER_DATA['version.normalized'] = '__UNKNOWN__'
        mgtSsh = "if [ -n \"$(which dpkg 2>/dev/null)\" ] ; then dpkg -l cloudstack-management | tail -n 1 | awk '{print $3}'; elif [ -n \"$(which rpm 2>/dev/null)\" ] ; then rpm -qa | grep cloudstack-management | tail -n 1 | sed 's,cloudstack-management-,,g; s,\.el6.*$,,g; s,\.el7.*,,g'; fi"
        retcode, output = self.runSSHCommand(host, mgtSsh)
        if retcode == 0:
            MGMT_SERVER_DATA['version'] = output
            MGMT_SERVER_DATA['version.normalized'] = self.normalizePackageVersion(output)
        self.debug(2, '    + Got MGMTVERSION: ' + MGMT_SERVER_DATA['version'] + ', normalized: ' + MGMT_SERVER_DATA['version.normalized'])
        return MGMT_SERVER_DATA

    def getAdvisoriesResources(self, mgt_server):
        self.debug(2, "getAdvisoriesResources : begin")
        results = []
        
        self.debug(2, " + checking check_free_vcpus")
        mgtSsh = "/usr/local/nagios/libexec/nrpe_local/check_free_vcpus"
        retcode, output = self.runSSHCommand(mgt_server, mgtSsh)
        if retcode != 0:
            if output == '':
                output = 'return code: ' + str(retcode)
            results += [{ 'id': '', 'name': 'free-vcpu', 'domain': 'ROOT', 'asset_type': 'resource', 'adv_action': LswCloudStackOpsBase.ACTION_MANUAL, 'adv_safetylevel': LswCloudStackOpsBase.SAFETY_NA, 'adv_comment': output}]

        self.debug(2, " + checking check_free_ips")
        mgtSsh = "/usr/local/nagios/libexec/nrpe_local/check_free_ips"
        retcode, output = self.runSSHCommand(mgt_server, mgtSsh)
        if retcode != 0:
            if output == '':
                output = 'return code: ' + str(retcode)
            results += [{ 'id': '', 'name': 'free-ip', 'domain': 'ROOT', 'asset_type': 'resource', 'adv_action': LswCloudStackOpsBase.ACTION_MANUAL, 'adv_safetylevel': LswCloudStackOpsBase.SAFETY_NA, 'adv_comment': output}]

        self.debug(2, " + checking check_cloud_agents")
        mgtSsh = "/usr/local/nagios/libexec/nrpe_local/check_cloud_agents"
        retcode, output = self.runSSHCommand(mgt_server, mgtSsh)
        if retcode != 0:
            if output == '':
                output = 'return code: ' + str(retcode)
            results += [{ 'id': '', 'name': 'cloud-agents', 'domain': 'ROOT', 'asset_type': 'resource', 'adv_action': LswCloudStackOpsBase.ACTION_MANUAL, 'adv_safetylevel': LswCloudStackOpsBase.SAFETY_NA, 'adv_comment': output}]

        # Taken from /usr/local/nagios/libexec/check_zone_resources
        self.debug(2, " + checking check_zone_resources")
        mgtSsh = "(cloudmonkey listCapacity type=0 | grep percentused | cut -d '\"' -f 4; cloudmonkey listCapacity type=1 | grep percentused | cut -d '\"' -f 4) | xargs"
        retcode, output = self.runSSHCommand(mgt_server, mgtSsh)
        (memory, cpu) = output.split(' ')
        if retcode != 0:
            if output == '':
                output = 'return code: ' + str(retcode)
            results += [{ 'id': '', 'name': 'capacity', 'domain': 'ROOT', 'asset_type': 'resource', 'adv_action': LswCloudStackOpsBase.ACTION_MANUAL, 'adv_safetylevel': LswCloudStackOpsBase.SAFETY_NA, 'adv_comment': 'check_zone_resources breached thresholds, mem=' + memory + ', cpu=' + cpu }]

        self.debug(2, "getAdvisoriesResources : end")
        return results
