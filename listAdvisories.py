#!/usr/bin/python

#      Copyright 2016, Leaseweb Technologies BV
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

# Script to list potential fixes.
# Nuno Tavares - n.tavares@tech.leaseweb.com

import time
import sys
import getopt
from cloudstackops import cloudstackops
from cloudstackops import cloudstackopsssh
import os.path
from random import choice
from prettytable import PrettyTable
import re

# Function to handle our arguments

def debug(level, args):
    if DEBUG>=level:
        print args

SAFETY_BEST = 0
SAFETY_DOWNTIME = 1
SAFETY_GOOD = 2
SAFETY_UNKNOWN = -1
SAFETY_NA = -99

ACTION_R_LOG_CLEANUP = 'log-cleanup'
ACTION_R_RST_PASSWD_SRV = 'rst-passwd-srv'
ACTION_N_RESTART = 'restart'
ACTION_I_THROTTLE = 'throttle'
ACTION_UNKNOWN = 'unknown'
ACTION_MANUAL = 'manual'
ACTION_ESCALATE = 'escalate'

STATE_ALLOCATED = 'Allocated'

def translateSafetyLevel(level):
    if level==SAFETY_BEST:
        return 'Best'
    if level==SAFETY_DOWNTIME:
        return 'Downtime'
    if level==SAFETY_GOOD:
        return 'Good'
    if level==SAFETY_NA:
        return 'N/A'
    return 'Unknown'

def translateSafetyLevelString(level):
    if level=='Best':
        return SAFETY_BEST
    if level=='Downtime':
        return SAFETY_DOWNTIME
    if level=='Good':
        return SAFETY_GOOD
    if level=='N/A':
        return SAFETY_NA
    if level=='Unknown':
        return SAFETY_UNKNOWN
    return None

def handleArguments(argv):
    global DEBUG
    DEBUG = 0
    global DRYRUN
    DRYRUN = 1
    global QUICKSCAN
    QUICKSCAN = 1
    global DEEPSCAN
    DEEPSCAN = 0
    global SAFETYLEVEL
    SAFETYLEVEL = SAFETY_BEST
    global domainname
    domainname = ''
    global configProfileName
    configProfileName = ''
    global command
    command = 'list'
    global plainDisplay
    plainDisplay = 0
    global opFilterNetworks
    opFilterNetworks = False
    global opFilterRouters
    opFilterRouters = False
    global opFilterInstances
    opFilterInstances = False
    global opFilterHosts
    opFilterHosts = False
    global opFilterResources
    opFilterResources = False
    global opFilterAll
    opFilterAll = False
    global opFilterSafetyLevel
    opFilterSafetyLevel = None
    global PLATFORM
    PLATFORM = None
    global MGMT_SERVER
    global MGMT_SERVER_DATA
    MGMT_SERVER_DATA = {}

    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options] ' + \
        '\n  --config-profile -c <profile>\t\tSpecify the CloudMonkey profile name to get the credentials from (or specify in ./config file)' + \
        '\n  --plain-display\t\t\tEnable plain display, no pretty tables' + \
        '\n  --repair\t\t\t\tApply suggested actions - at Safe/Best level' + \
        '\n' + \
        '\n  Modifiers:' + \
        '\n  --exec\tDisable dry-run mode. You\'l need this to perform changes to the platform.' + \
        '\n  --debug\tEnable debug mode. Use it multiple times to increase verbosity' + \
        '\n  --live\tPerform live scan. By default, quick mode is used (using deferred/cached collection methods)' + \
        '\n  --deep\tEnable further tests that usually produces a lot of results. For a list of tests, use -h with this option' + \
        '\n' + \
        '\n  Filters:' + \
        '\n  -n \t\tScan networks (incl. VPCs)' + \
        '\n  -r \t\tScan routerVMs' + \
        '\n  -i \t\tScan instances' + \
        '\n  -H \t\tScan hypervisors' + \
        '\n  -t \t\tScan resource usage' + \
        '\n  --all \tReport all assets of the selected types, independently of the presence of advisory' + \
        '\n  --safety <safety> \tFilter out advisories that are not at the specified safety level (default: ' + translateSafetyLevel(SAFETYLEVEL) + ')'

    try:
        opts, args = getopt.getopt(
            argv, "hc:nriHt", [
                "config-profile=", "debug", "exec", "deep", "live", "plain-display", "all", "repair", "safety=" ])
    except getopt.GetoptError as e:
        print "Error: " + str(e)
        print help
        sys.exit(2)

    if len(opts) == 0:
        print help
        sys.exit(2)

    helpRequested = False
    for opt, arg in opts:
        if opt == '-h':
            helpRequested = True
        elif opt in ("-c", "--config-profile"):
            configProfileName = arg
            PLATFORM = configProfileName
        elif opt in ("--debug"):
            if DEBUG==2:
                DEBUG = 1
            else:
                DEBUG = 2
        elif opt in ("--exec"):
            DRYRUN = 0
        elif opt in ("--live"):
            QUICKSCAN = 0
        elif opt in ("--deep"):
            DEEPSCAN = 1
        elif opt in ("--plain-display"):
            plainDisplay = 1
        elif opt in ("-n"):
            opFilterNetworks = True
        elif opt in ("-r"):
            opFilterRouters = True
        elif opt in ("-i"):
            opFilterInstances = True
        elif opt in ("-H"):
            opFilterHosts = True
        elif opt in ("--t"):
            opFilterResources = True
        elif opt in ("--all"):
            opFilterAll = True
        elif opt in ("--repair"):
            command = 'repair'
        elif opt in ("--safety"):
            opFilterSafetyLevel = translateSafetyLevelString(arg)
            if opFilterSafetyLevel != None:
                SAFETYLEVEL = opFilterSafetyLevel

    def printHelpTests():
        print
        print "List of tests available"
        t = PrettyTable(["Scope", "Level", "Symptom / Probe / Detection", "Detection", "Recovery"])
        t.align["Symptom / Probe / Detection"] = "l"
        
        if plainDisplay == 1:
            t.border = False
            t.header = False
            t.padding_width = 1

        t.add_row([ "network", "Normal", "Flag restart_required", True, True ])
        t.add_row([ "router", "Normal", "Redundancy state", True, True ])
        t.add_row([ "router", "Normal", "Output of check_router.sh is non-zero (dmesg,swap,resolv,ping,fs,disk,password)", True, True ])
        t.add_row([ "router", "Deep", "Checks if router is running on the current systemvm template version", True, True ])
        t.add_row([ "instance", "Normal", "Try to assess instance read-only state", True, False ])
        t.add_row([ "instance", "Normal", "Queries libvirt usage records for abusers (CPU, I/O, etc)", True, False ])
        t.add_row([ "hypervisor", "Normal", "Agent state (version, conn state)", True, False ])
        t.add_row([ "hypervisor", "Normal", "Load average", True, False ])
        t.add_row([ "hypervisor", "Normal", "Conntrack abusers", True, False ])
        t.add_row([ "hypervisor", "Normal", "check_libvirt_storage.sh correct functioning", True, False ])

        print t
        
    if helpRequested:
        if DEEPSCAN:
            printHelpTests()
        else:
            print help
        sys.exit()

    if PLATFORM==None:
        print "No platform is specified. Please use the -c option."
        sys.exit(1)

    MGMT_SERVER = "mgt01." + PLATFORM

    # Default to cloudmonkey default config file
    if len(configProfileName) == 0:
        configProfileName = "config"

# Parse arguments
if __name__ == "__main__":
    handleArguments(sys.argv[1:])

# Init our class
c = cloudstackops.CloudStackOps(DEBUG, DRYRUN)
ssh = cloudstackopsssh.CloudStackOpsSSH(DEBUG, DRYRUN)
c.ssh = ssh

if DEBUG > 0:
    print "# Warning: Debug mode is enabled!"

if DRYRUN == 1:
    print "# Warning: dry-run mode is enabled, not running any commands!"

# make credentials file known to our class
c.configProfileName = configProfileName

# Init the CloudStack API
c.initCloudStackAPI()

if DEBUG == 1:
    print "API address: " + c.apiurl
    print "ApiKey: " + c.apikey
    print "SecretKey: " + c.secretkey

#
# TODO : examine conntrack

def examineHost(alarmedInstancesCache, host):
    def getHostIp(host):
        return host.name + "." + PLATFORM
    ENABLED_INSPECTIONS = []
    ENABLED_INSPECTIONS += [ 'io-abuse' ]
    ENABLED_INSPECTIONS += [ 'conntrack' ]
    ENABLED_INSPECTIONS += [ 'load-avg' ]
    
    debug(2, ' + Checking agent connection state: ' + host.state)
    if host.state != 'Up':
        return { 'action': ACTION_MANUAL, 'safetylevel': SAFETY_NA, 'comment': 'Agent is not Up (' + host.state + ')' }

    debug(2, ' + Comparing h.version(%s) with MGMT version(%s)' % (host.version, MGMT_SERVER_DATA['version']))
    if host.version != MGMT_SERVER_DATA['version']:
        return { 'action': ACTION_MANUAL, 'safetylevel': SAFETY_NA, 'comment': 'Agent version mistatch (' + host.version + '!=' + MGMT_SERVER_DATA['version'] + ')' }

    nodeSrv = getHostIp(host)
    if 'load-avg' in ENABLED_INSPECTIONS:
        LOAD_AVG_MARGIN = 0.3
        nodeSsh = "echo \"$(grep ^processor /proc/cpuinfo  | wc -l) $(awk '{print $2}' /proc/loadavg)\""
        retcode, output = c.ssh.runSSHCommand(nodeSrv, nodeSsh)
        debug(2, "   + Load average check output: %s" % (output))
        
        (n_cpus, loadavg) = output.split(' ')
        n_cpus = int(n_cpus)
        loadavg = float(loadavg)
        debug(2, "   + Load average check: %d  + %.0f%% < %.1f" % (n_cpus, LOAD_AVG_MARGIN*100, loadavg))
        if loadavg > n_cpus*(1+LOAD_AVG_MARGIN):
            return { 'action': ACTION_UNKNOWN, 'safetylevel': SAFETY_NA, 'comment': 'Hypervisor under pressure (load): %.1f' % loadavg }

    if 'io-abuse' in ENABLED_INSPECTIONS:
        debug(2, ' + Checking I/O abuse...')
        nodeSsh = "/usr/local/nagios/libexec/nrpe_local/check_libvirt_storage.sh"
        retcode, output = c.ssh.runSSHCommand(nodeSrv, nodeSsh)

        if retcode!=0:
            return { 'action': ACTION_MANUAL, 'safetylevel': SAFETY_NA, 'comment': 'check_libvirt_storage.sh seems to be failing' }

        lines = output.split('\n')
        instances = {}
        for line in lines:
            m = re.match("(\S+) (\S+) (\S+)", line)
            if m:
                debug(2, " + check_libvirt_storage: i=%s, m=%s, level=%s" % (m.group(2), m.group(3), m.group(1)))
                # For some reason, someone decided to change the instance name... 
                i_name = m.group(2).replace('_', '-')
                if i_name not in instances.keys():
                    instances[ i_name ] = []
                instances[i_name] += [ m.group(3) ]
                alarmedInstancesCache[i_name] = { 'alarm': 'io-abuse', 'host': host.name, 'level': m.group(1), 'metrics': instances[i_name] }
        if len(instances.keys())>=1:
            return { 'action': ACTION_ESCALATE, 'safetylevel': SAFETY_NA, 'comment': 'IOP abusing instances: '+ ','.join(instances.keys()) }

    if 'conntrack' in ENABLED_INSPECTIONS:
        CONNTRACK_RATIO_THRESHOLD_PC = 70
        debug(2, ' + Checking conntrack...')
        #mgtSsh = "ssh -At %s ssh -At -p 3922 -i /root/.ssh/id_rsa.cloud -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no root@%s ls -la" % (router.hostname, router.linklocalip)
        #nodeSsh = 'CT_MAX=$(cat /proc/sys/net/netfilter/nf_conntrack_max); CT_COUNT=$(cat /proc/sys/net/netfilter/nf_conntrack_count); awk \'BEGIN {printf "%.2f",\${CT_COUNT}/\${CT_MAX}}\''
        nodeSsh = "echo \"$(cat /proc/sys/net/netfilter/nf_conntrack_count) $(cat /proc/sys/net/netfilter/nf_conntrack_max)\""
        retcode, output = c.ssh.runSSHCommand(nodeSrv, nodeSsh)
        debug(2, "   + retcode=%d, output=%s" % (retcode, output))

        m = re.match("(\d+) (\d+)", output)
        if m:
            ct_cur = int(m.group(1))
            ct_max = int(m.group(2))
            debug(2, "   + conntrack: c=%d, max=%d" % (ct_cur, ct_max))
            ct_ratio = 100.0 * ct_cur / ct_max
            if ct_ratio > CONNTRACK_RATIO_THRESHOLD_PC:
                return { 'action': ACTION_MANUAL, 'safetylevel': SAFETY_NA, 'comment': 'Conntrack abuse (' + "{:.2f}%".format(ct_ratio) + ')' }

    return { 'action': None, 'safetylevel': SAFETY_NA, 'comment': '' }

def getAdvisoriesHosts(alarmedInstancesCache):
    debug(2, "getAdvisoriesHosts : begin")
    results = []
    
    hostData = c.getHostData({'type': 'Routing'})
    for host in hostData:
        debug(2, "Processing: host.name = %s, type = %s" % (host.name, host.type))

        diag = examineHost(alarmedInstancesCache, host)
        if opFilterAll or (diag['action'] != None):
            results += [{ 'id': host.id, 'name': host.name, 'domain': 'ROOT', 'asset_type': 'host', 'adv_action': diag['action'], 'adv_safetylevel': diag['safetylevel'], 'adv_comment': diag['comment']}]
 
    debug(2, "getAdvisoriesHosts : end")
    return results


def getAdvisoriesResources():
    debug(2, "getAdvisoriesResources : begin")
    results = []
    
    mgtSsh = "/usr/local/nagios/libexec/nrpe_local/check_free_vcpus"
    retcode, output = c.ssh.runSSHCommand(MGMT_SERVER, mgtSsh)
    if retcode != 0:
        results += [{ 'id': '', 'name': 'free-vcpu', 'domain': 'ROOT', 'asset_type': 'resource', 'adv_action': ACTION_MANUAL, 'adv_safetylevel': SAFETY_NA, 'adv_comment': output}]

    mgtSsh = "/usr/local/nagios/libexec/nrpe_local/check_free_ips"
    retcode, output = c.ssh.runSSHCommand(MGMT_SERVER, mgtSsh)
    if retcode != 0:
        results += [{ 'id': '', 'name': 'free-ip', 'domain': 'ROOT', 'asset_type': 'resource', 'adv_action': ACTION_MANUAL, 'adv_safetylevel': SAFETY_NA, 'adv_comment': output}]

    mgtSsh = "/usr/local/nagios/libexec/nrpe_local/check_cloud_agents"
    retcode, output = c.ssh.runSSHCommand(MGMT_SERVER, mgtSsh)
    if retcode != 0:
        results += [{ 'id': '', 'name': 'cloud-agents', 'domain': 'ROOT', 'asset_type': 'resource', 'adv_action': ACTION_MANUAL, 'adv_safetylevel': SAFETY_NA, 'adv_comment': output}]

    debug(2, "getAdvisoriesResources : end")
    return results

def getAdvisoriesInstances(alarmedInstancesCache):
    debug(2, "getAdvisoriesInstances : begin")
    results = []
    
    for i_name in alarmedInstancesCache.keys():
        i_domain = ''
        i_id = ''
        iinfo = c.listVirtualmachines({'instancename': i_name})
        
        #import pprint
        #pp = pprint.PrettyPrinter(indent=4)
        #pp.pprint(iinfo)
        #break;

        for i in iinfo:
            if i.instancename == i_name:
                i_domain = i.domain
                i_id = i.id
        if alarmedInstancesCache[i_name]['alarm']=='read-only':
            comment = 'Instance is reported read-only'
            action = ACTION_MANUAL
            safety = SAFETY_NA
        elif alarmedInstancesCache[i_name]['alarm']=='io-abuse':
            comment = 'Instance is abusing I/O (' + ','.join(alarmedInstancesCache[i_name]['metrics']) + ')'
            action = ACTION_I_THROTTLE
            safety = SAFETY_NA
        # else should never happen #
        
        results += [{ 'id': i_id, 'name': i_name, 'domain': i_domain, 'asset_type': 'instance', 'adv_action': action, 'adv_safetylevel': safety, 'adv_comment': comment}]

    debug(2, "getAdvisoriesInstances : end")
    return results

def getAdvisoriesNetworks(alarmedRoutersCache):
    debug(2, "getAdvisoriesNetworks/Routers : begin")
    
    results = []

    # This method will analyse the network and return an advisory
    def examineNetwork(network, advRouters):
        if network.restartrequired:
            if network.rr_type:
                return {'action': ACTION_N_RESTART, 'safetylevel': SAFETY_BEST, 'comment': 'Restart flag on, redundancy present'}
            else:
                return {'action': ACTION_N_RESTART, 'safetylevel': SAFETY_DOWNTIME, 'comment': 'Restart flag on, no redundancy'}
        if len(advRouters)>0:
            rnames = [];
            for r in advRouters:
                rnames = rnames + [ r['name'] ];
            if network.rr_type:
                return {'action': ACTION_N_RESTART, 'safetylevel': SAFETY_BEST, 'comment': 'Network tainted (State:' + network.state + '), problems found with router(s): ' + ','.join(rnames)}
            else:
                if network.type == 'Shared':
                    return {'action': ACTION_N_RESTART, 'safetylevel': SAFETY_GOOD, 'comment': 'Network tainted (State:' + network.state + '), problems found with router(s): '+ ','.join(rnames)}
                else:
                    return {'action': ACTION_N_RESTART, 'safetylevel': SAFETY_DOWNTIME, 'comment': 'Network tainted (State:' + network.state + '), problems found with router(s): '+ ','.join(rnames)}
            
        return {'action': None, 'safetylevel': SAFETY_NA, 'comment': ''}

    # Use this when you want to inspect routers real-time
    # Note: Development was dropped in favor of examineRouterInternalsQuick()
    # TODO we should provide a --deep switch
    def examineRouterInternalsDeep(alarmedRoutersCache, router):
        debug(2, "   + router: name: %s, ip=%s, host=%s, tpl=%s" % (router.name, router.linklocalip, router.hostname, router.templateversion))

        # Use the cache anyway, to mark already checked routers:
        if router.name in alarmedRoutersCache.keys():
            if alarmedRoutersCache[router.name]['checked']:
                return 0, None

        #mgtSsh = "ssh -At %s ssh -At -p 3922 -i /root/.ssh/id_rsa.cloud -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no root@%s ls -la" % (router.hostname, router.linklocalip)
        mgtSsh = "/usr/local/bin/check_routervms.py " + router.name
        retcode, output = c.ssh.runSSHCommand(MGMT_SERVER, mgtSsh)
        if retcode != 0:
            return "256", "check_routervms.py returned errors"
            
        lines = output.split('\n')
        retcode = int(lines[-1])
        output = "check_routervms returned errors"
        debug(2, "   + cmd: " + mgtSsh)
        debug(2, "       + retcode=%d" % (retcode))

        # Use the cache anyway, to mark already checked routers:
        alarmedRoutersCache[router.name] = { 'network': router.network, 'code': retcode, 'checked': True }

        return retcode, output

    def examineRouterInternalsQuick(alarmedRoutersCache, router):
        debug(2, "   + router: name: %s, ip=%s, host=%s, tpl=%s" % (router.name, router.linklocalip, router.hostname, router.templateversion))

        if router.name in alarmedRoutersCache.keys():
            if not alarmedRoutersCache[router.name]['checked']:
                alarmedRoutersCache[router.name]['checked'] = True
                return alarmedRoutersCache[router.name]['code'], "check_routervms returned errors"

        return 0, None
        
    def resolveRouterErrorCode(errorCode):
        str = []
        errorCode = int(errorCode)
        if errorCode & 1:
            str = str + [ 'dmesg' ]
        if errorCode & 2:
            str = str + [ 'swap' ]
        if errorCode & 4:
            str = str + [ 'resolver' ]
        if errorCode & 8:
            str = str + [ 'ping' ]
        if errorCode & 16:
            str = str + [ 'filesystem' ]
        if errorCode & 32:
            str = str + [ 'disk' ]
        if errorCode & 64:
            str = str + [ 'password' ]
        if errorCode & 128:
            str = str + [ 'reserved' ]
        if errorCode & 256:
            str = str + [ 'check_routervms.py' ]
        return ",".join(str)

    def getActionForStatus(statuscode, rr_type, net_type):
        if statuscode & 4:
            if rr_type:
                return ACTION_ESCALATE, SAFETY_BEST
            else:
                if net_type == 'Shared':
                    return ACTION_ESCALATE, SAFETY_GOOD
                else:
                    return ACTION_ESCALATE, SAFETY_DOWNTIME
        if statuscode & 8:
            if rr_type:
                return ACTION_ESCALATE, SAFETY_BEST
            else:
                if net_type == 'Shared':
                    return ACTION_ESCALATE, SAFETY_GOOD
                else:
                    return ACTION_ESCALATE, SAFETY_DOWNTIME
        if statuscode & 32:
            return ACTION_R_LOG_CLEANUP, SAFETY_BEST
        if statuscode & 64:
            return ACTION_R_RST_PASSWD_SRV, SAFETY_BEST
        return ACTION_UNKNOWN, SAFETY_UNKNOWN

    def examineRouter(alarmedRoutersCache, network, router, currentRouterTemplateId):
        if router.isredundantrouter and (router.redundantstate not in ['MASTER', 'BACKUP']):
            if network.rr_type:
                return {'action': ACTION_ESCALATE, 'safetylevel': SAFETY_BEST, 'comment': 'Redundancy state broken (' + router.redundantstate + '), redundancy present'}
            else:
                return {'action': ACTION_ESCALATE, 'safetylevel': SAFETY_DOWNTIME, 'comment': 'Redundancy state broken (' + router.redundantstate + '), no redundancy'}
        
        # We should now try to assess the router internal status (with SSH)
        #retcode, output = examineRouterInternals(router)
        if QUICKSCAN==1:
            retcode, output = examineRouterInternalsQuick(alarmedRoutersCache, router)
        else:
            retcode, output = examineRouterInternalsDeep(alarmedRoutersCache, router)

        if retcode != 0:
            action, safetylevel = getActionForStatus(retcode, network.rr_type, network.type)
            return {'action': action, 'safetylevel': safetylevel, 'comment': output + ": " + str(retcode) + " (" + resolveRouterErrorCode(retcode) + ")" }

        # We now assess if the router VM template is current
        if (DEEPSCAN==1) and (currentRouterTemplateId!=None):
            if router.templateid != currentRouterTemplateId:
                if network.rr_type:
                    return {'action': ACTION_ESCALATE, 'safetylevel': SAFETY_BEST, 'comment': 'Router using obsolete template, redundancy present'}
                else:
                    if network.type == 'Shared':
                        return {'action': ACTION_ESCALATE, 'safetylevel': SAFETY_GOOD, 'comment': 'Router using obsolete template, redundancy not critical'}
                    else:
                        return {'action': ACTION_ESCALATE, 'safetylevel': SAFETY_DOWNTIME, 'comment': 'Router using obsolete template, no redundancy'}

        return {'action': None, 'safetylevel': SAFETY_NA, 'comment': ''}


    # One of the router tests we can make is to assess it's template version, if it's 
    # current to the Global Setting router.template.kvm, so let's fetch that one.
    confrtpl = c.getConfiguration("router.template.kvm" )
    routerTemplateName = confrtpl[0].value
    # Watch out for the use of "keyword". It should be "name", but Marvin API returns more results than expected..
    routerTemplateData = c.listTemplates({'templatefilter': 'all', 'keyword': routerTemplateName, 'listall': 'True'})
    routerTemplateId = None
    
    if type(routerTemplateData) is not list:
        print "ERROR: Failed to acquire the current router template"
        sys.exit(2)

    for r in routerTemplateData:
        if r.name == routerTemplateName:
            routerTemplateId = r.id
    if routerTemplateId == None:
        print "WARNING: Could not find the 'router.template.kvm' setting (name: %s)" % (routerTemplateName)


    networkData = c.listNetworks({})
    for network in networkData:
        debug(2, " + Processing: network.name = %s (%s)" % (network.name, network.state))
        
        network.rr_type = False
        net_type = network.type

        if network.service:
            for netsvc in network.service:
                if netsvc.capability:
                    for cap in netsvc.capability:
                        if cap.name == 'RedundantRouter':
                            if cap.value == 'true':
                                network.rr_type = True
        if network.vpcid:
            net_type = 'VPCTier'

        escalated = []
        if opFilterRouters:
            # A network in state Allocated probably has routers Offline.
            # In that case, redundancystate will always be UNKNOWN or even unexplicable states
            if network.state != STATE_ALLOCATED:
                routersData = c.getRouterData({'networkid': network.id})
                if routersData:
                    for r in routersData:
                        diag = examineRouter(alarmedRoutersCache, network, r, routerTemplateId)
                        if ( opFilterAll or (diag['action'] != None) ):
                            if diag['action'] == ACTION_ESCALATE:
                                escalated = escalated + [{ 'id': r.id, 'name': r.name, 'domain': network.domain, 'asset_type': 'router', 'adv_action': diag['action'], 'adv_safetylevel': diag['safetylevel'], 'adv_comment': diag['comment'] }]
                            results = results + [{ 'id': r.id, 'name': r.name, 'domain': network.domain, 'asset_type': 'router', 'adv_action': diag['action'], 'adv_safetylevel': diag['safetylevel'], 'adv_comment': diag['comment'] }]

        
        diag = examineNetwork(network, escalated)
        if ( opFilterNetworks and (opFilterAll or (diag['action'] != None)) ):
            results = results + [{ 'id': network.id, 'type': net_type, 'name': network.name, 'domain': network.domain, 'rr_type': network.rr_type, 'restartrequired': network.restartrequired, 'state': network.state, 'asset_type': 'network', 'adv_action': diag['action'], 'adv_safetylevel': diag['safetylevel'], 'adv_comment': diag['comment'] }]

    vpcData = c.listVPCs({})
    for vpc in vpcData:
        debug(2, " + Processing: vpc.name = %s (%s)" % (vpc.name, vpc.state))
        vpc.rr_type = False
        if vpc.redundantvpcrouter:
            vpc.rr_type = vpc.redundantvpcrouter

        escalated = []
        if opFilterRouters:
            routersData = c.getRouterData({'vpcid': vpc.id})
            if routersData:
                for r in routersData:
                    diag = examineRouter(alarmedRoutersCache, vpc, r, routerTemplateId)
                    # We include 'escalate' in case opFilterNetworks is not set, to notify that we need it
                    # in order to fix this
                    if ( opFilterAll or (diag['action'] != None) ):
                        if diag['action'] == ACTION_ESCALATE:
                            escalated = escalated + [{ 'id': r.id, 'name': r.name, 'domain': vpc.domain, 'asset_type': 'router', 'adv_action': diag['action'], 'adv_safetylevel': diag['safetylevel'], 'adv_comment': diag['comment'] }]
                        results = results + [{ 'id': r.id, 'name': r.name, 'domain': vpc.domain, 'asset_type': 'router', 'adv_action': diag['action'], 'adv_safetylevel': diag['safetylevel'], 'adv_comment': diag['comment'] }]


        diag = examineNetwork(vpc, escalated)
        if ( opFilterNetworks and (opFilterAll or (diag['action'] != None)) ):
            results = results + [{ 'id': vpc.id, 'type': 'VPC', 'name': vpc.name, 'domain': vpc.domain, 'rr_type': vpc.rr_type, 'restartrequired': vpc.restartrequired, 'state': vpc.state, 'asset_type': 'vpc', 'adv_action': diag['action'], 'adv_safetylevel': diag['safetylevel'], 'adv_comment': diag['comment'] }]
    
    debug(2, "getAdvisoriesNetworks/Routers : end")

    return results

def getAdvisories():
    
    # MGMT servers are already checking the routerVMs, we can use that cache
    def retrieveAlarmedInstancesCache():
        alarmedInstancesCache = {}
        debug(2, "Fetching alarmed instances cache...")
        mgtSsh = "grep -v -f /var/local/ack_readonly /tmp/vps_readonly 2>/dev/null || /bin/true"
        retcode, output = c.ssh.runSSHCommand(MGMT_SERVER, mgtSsh)
        debug(2, " + retcode=%d" % (retcode))
        
        import re
        lines = output.split('\n')
        for line in lines:
            m = re.match("(\S+) \[(.*)\]", line)
            if m:
                debug(2, "i: %s, h: %s" % (m.group(1), m.group(2)))
                alarmedInstancesCache[m.group(1)] = { 'alarm': 'read-only', 'name': m.group(1), 'host': m.group(2) }
        return alarmedInstancesCache

    # MGMT servers are already checking the routerVMs, we can use that cache
    def retrieveAlarmedRoutersCache():
        alarmedRoutersCache = {}
        debug(2, "Fetching alarmed routers cache...")
        mgtSsh = "cat /tmp/routervms_problem"
        retcode, output = c.ssh.runSSHCommand(MGMT_SERVER, mgtSsh)
        debug(2, " + retcode=%d" % (retcode))
        
        import re
        lines = output.split('\n')
        for line in lines:
            m = re.match("(\S+) \[(.*)\] (\d+)", line)
            if m:
                debug(2, "r: %s, n: %s, code: %s" % (m.group(1), m.group(2), m.group(3)))
                alarmedRoutersCache[m.group(1)] = { 'network': m.group(2), 'code': int(m.group(3)), 'checked': False }
        return alarmedRoutersCache

    # MGMT servers are already checking the routerVMs, we can use that cache
    def retrieveListHostsCache():
        listHostsCache = {}
        debug(2, "Fetching hosts/nodes cache...")
        listHostsCache = c.getHostData({'type': 'Routing'})
        for h in listHostsCache:
            print " + Host: %s (state:%s, version:%s)" % (h.name, h.state, h.version)

        return listHostsCache
    
    def testMgmtServerConnection():
        # Test connection to MGMT_SERVER, we are going to need it
        debug(2, "+ Testing SSH to '%s'" % (MGMT_SERVER))
        retcode, output = c.ssh.testSSHConnection(MGMT_SERVER)
        debug(2, "   + retcode=%d, output=%s" % (retcode, output))
        if retcode != 0:
            print "Failed to ssh to management server %s, please investigate." % (MGMT_SERVER)
            sys.exit(1)

        MGMT_SERVER_DATA['version'] = '__UNKNOWN__'
        mgtSsh = "if [ -n \"$(which dpkg 2>/dev/null)\" ] ; then dpkg -l cloudstack-management | tail -n 1 | awk '{print $3}'; elif [ -n \"$(which rpm 2>/dev/null)\" ] ; then rpm -qa | grep cloudstack-management | tail -n 1 | sed 's,cloudstack-management-,,g; s,\.el6.*$,,g' ; fi"
        retcode, output = c.ssh.runSSHCommand(MGMT_SERVER, mgtSsh)
        if retcode == 0:
            MGMT_SERVER_DATA['version'] = output
        debug(2, '    + Got MGMTVERSION: ' + MGMT_SERVER_DATA['version'])
        
    testMgmtServerConnection()

    results = []
    if opFilterNetworks or opFilterRouters:
        alarmedRoutersCache = retrieveAlarmedRoutersCache()
        results = results + getAdvisoriesNetworks(alarmedRoutersCache)
    if opFilterInstances or opFilterHosts:
        alarmedInstancesCache = retrieveAlarmedInstancesCache()
    if opFilterHosts:
        #listHostsCache = retrieveListHostsCache()
        results = results + getAdvisoriesHosts(alarmedInstancesCache)
    if opFilterInstances:
        results = results + getAdvisoriesInstances(alarmedInstancesCache)
    if opFilterResources:
        results = results + getAdvisoriesResources()

    def getSortKey(item):
        return item['asset_type'].upper() + '-' + item['name'].upper() 

    # Filter out advisories not in the specified safety level, if set
    newResults = []
    for r in results:
        if (opFilterSafetyLevel==None) or (r['adv_safetylevel']==SAFETYLEVEL):
            newResults = newResults + [ r ]

    return sorted(newResults, key=getSortKey)


def cmdListAdvisories():

    results = getAdvisories()

#    import pprint
#    pp = pprint.PrettyPrinter(indent=4)
#    pp.pprint(networkData)
    
    # Empty line
    print
    t = PrettyTable(["#", "Platf", "Type", "Name", "ID", "Domain", "Action", "SafetyLevel", "Comment"])
    t.align["Comment"] = "l"
    
    if plainDisplay == 1:
        t.border = False
        t.header = False
        t.padding_width = 1

    counter = 0
    for a in results:
        counter = counter + 1
        t.add_row([counter, configProfileName, a['asset_type'], a['name'], a['id'], a['domain'], a['adv_action'], translateSafetyLevel(a['adv_safetylevel']), a['adv_comment']])

    # Display table
    print t

def repairRouter(adv):
    debug(2, "repairRouter(): router:%s, action:%s" % (adv['name'], adv['adv_action']))
    if (DRYRUN==1) and (adv['adv_action'] in [ACTION_R_RST_PASSWD_SRV, ACTION_R_LOG_CLEANUP]):
        return -2, 'Skipping, dryrun is on.'

    if adv['adv_action'] == ACTION_ESCALATE:
        return -2, 'Escalated'

    if adv['adv_action'] == None:
        return -2, ''

    if adv['adv_action'] == ACTION_R_RST_PASSWD_SRV:
        mgtSsh = '/usr/local/bin/routervm_ssh.sh ' + adv['name'] + ' /etc/init.d/cloud-passwd-srvr restart'
        retcode, output = c.ssh.runSSHCommand(MGMT_SERVER, mgtSsh)
        if retcode==0:
            output = 'cloud-passwd-srvr restarted'
        return retcode, output
    if adv['adv_action'] == ACTION_R_LOG_CLEANUP:
        mgtSsh = '/usr/local/bin/routervm_ssh.sh ' + adv['name'] + " '/usr/bin/find /var/log -mtime +2 -type f -exec rm -f \\{\\} \\\\\;'"
        retcode, output = c.ssh.runSSHCommand(MGMT_SERVER, mgtSsh)
        if retcode==0:
            output = 'tried deleted -mtime +2 files'
        return retcode, output

    return -1, 'Not implemented'

def repairNetwork(adv):
    debug(2, "repairNetwork(): network:%s, action:%s" % (adv['name'], adv['adv_action']))
    
    if adv['adv_action'] == None:
        return -2, ''

    if adv['adv_action']==ACTION_N_RESTART:
        if SAFETYLEVEL==adv['adv_safetylevel']:
            debug(2, ' + restart network.name=%s, .id=%s' % (adv['name'], adv['id']))
            if DRYRUN==1:
                return -2, 'Skipping, dryrun is on.'
            print "Restarting network '%s'" % (adv['name'])
            ret = c.restartNetwork(adv['id'], True)
            debug(2, " + ret = " + str(ret))
            if ret and (hasattr(ret, 'success')) and (ret.success == True):
                return 0, 'Network restarted without errors.'
            else:
                return 1, 'Errors during the restart. Check messages above.'
        else:
            return -2, 'Ignored by SafetyLevel scope (' + translateSafetyLevel(SAFETYLEVEL) + ')'

    return -1, 'Not implemented'

def cmdRepair():
    debug(2, "cmdRepair : begin")
    results = getAdvisories()
    debug(2, " + found %d results" % (len(results)))
    for adv in results:
        if opFilterRouters and (adv['asset_type'] == 'router'):
            applied,output = repairRouter(adv)
        if opFilterNetworks and (adv['asset_type'] == 'network'):
            applied, output = repairNetwork(adv)
        if applied==0:
            adv['repair_code'] = 'OK'
            adv['repair_msg'] = 'Repair successful: ' + output
        elif applied>0:
            adv['repair_code'] = 'NOK'
            adv['repair_msg'] = 'Repair unsuccesful: ' + output
        else:
            adv['repair_code'] = 'N/A'
            adv['repair_msg'] = output

    print
    t = PrettyTable(["#", "Type", "Name", "ID", "Domain", "Action", "Result", "Comment"])
    t.align["Comment"] = "l"
    
    if plainDisplay == 1:
        t.border = False
        t.header = False
        t.padding_width = 1

    counter = 0
    for a in results:
        counter = counter + 1
        t.add_row([counter, a['asset_type'], a['name'], a['id'], a['domain'], a['adv_action'], a['repair_code'], a['repair_msg']])
    print t

    debug(2, "cmdRepair : end")

if opFilterSafetyLevel:
    print "Applying filter: safetylevel == %s" % translateSafetyLevel(opFilterSafetyLevel)

if command == 'list':
    cmdListAdvisories()
elif command == 'repair':
    cmdRepair()  
