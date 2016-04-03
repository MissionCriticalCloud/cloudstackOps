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

# Function to handle our arguments


def handleArguments(argv):
    global DEBUG
    DEBUG = 0
    global DRYRUN
    DRYRUN = 1
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
    global opFilterAll
    opFilterAll = False
    global PLATFORM
    PLATFORM = None
    global MGMT_SERVER

    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options] ' + \
        '\n  --config-profile -c <profilename>\t\tSpecify the CloudMonkey profile name to get the credentials from (or specify in ./config file)' + \
        '\n  --debug\t\t\t\t\tEnable debug mode' + \
        '\n  --plain-display\t\t\t\tEnable plain display, no pretty tables' + \
        '\n' + \
        '\n  Filters:' + \
        '\n  -n \t\tScan networks (incl. VPCs)' + \
        '\n  -r \t\tScan routerVMs' + \
        '\n  -i \t\tScan instances' + \
        '\n  -H \t\tScan hypervisors' + \
        '\n  --all \tReport all assets of the selected types, independently of the presence of advisory '

    try:
        opts, args = getopt.getopt(
            argv, "hc:nriH", [
                "config-profile=", "debug", "exec", "plain-display", "all" ])
    except getopt.GetoptError as e:
        print "Error: " + str(e)
        print help
        sys.exit(2)

    if len(opts) == 0:
        print help
        sys.exit(2)

    for opt, arg in opts:
        if opt == '-h':
            print help
            sys.exit()
        elif opt in ("-c", "--config-profile"):
            configProfileName = arg
            PLATFORM = configProfileName
        elif opt in ("--debug"):
            DEBUG = 2
        #elif opt in ("--exec"):
        #    DRYRUN = 0
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
        elif opt in ("--all"):
            opFilterAll = True

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



def getAdvisoriesHosts():
    if DEBUG > 0:
        print "getAdvisoriesHosts : begin"
    results = []
    if DEBUG > 0:
        print "getAdvisoriesHosts : end"
    return results

def getAdvisoriesInstances():
    if DEBUG > 0:
        print "getAdvisoriesInstances : begin"
    results = []
    if DEBUG > 0:
        print "getAdvisoriesInstances : end"
    return results

def getAdvisoriesNetworks(alarmedRoutersCache):
    if DEBUG > 0:
        print "getAdvisoriesNetworks/Routers : begin"
    results = []

    # This method will analyse the network and return an advisory
    def examineNetwork(network, advRouters):
        if network.restartrequired:
            if network.rr_type:
                return {'action': 'restart', 'safetylevel': 'Best', 'comment': 'Restart flag on, redundancy present'}
            else:
                return {'action': 'restart', 'safetylevel': 'Downtime', 'comment': 'Restart flag on, no redundancy'}
        if len(advRouters)>0:
            rnames = [];
            for r in advRouters:
                rnames = rnames + [ r['name'] ];
            if network.rr_type:
                return {'action': 'restart', 'safetylevel': 'Best', 'comment': 'Network tainted, problems found with router(s): ' + ','.join(rnames)}
            else:
                return {'action': 'restart', 'safetylevel': 'Downtime', 'comment': 'Network tainted, problems found with router(s): '+ ','.join(rnames)}
            
        return {'action': None, 'safetylevel': None, 'comment': None}

    # Use this when you want to inspect routers real-time
    # Note: Development was dropped in favor of examineRouterInternalsQuick()
    # TODO we should provide a --deep switch
    def examineRouterInternalsDeep(router):
        if DEBUG > 0:
            print "   + router: name: %s, ip=%s, host=%s, tpl=%s" % (router.name, router.linklocalip, router.hostname, router.templateversion)

        #mgtSsh = "ssh -At %s ssh -At -p 3922 -i /root/.ssh/id_rsa.cloud -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no root@%s ls -la" % (router.hostname, router.linklocalip)
        mgtSsh = "/usr/local/bin/check_routervms.py " + router.name
        retcode, output = c.ssh.runSSHCommand(MGMT_SERVER, mgtSsh)
        print "       + retcode=%d" % (retcode)
        return retcode, output

    def examineRouterInternalsQuick(alarmedRoutersCache, router):
        if DEBUG > 0:
            print "   + router: name: %s, ip=%s, host=%s, tpl=%s" % (router.name, router.linklocalip, router.hostname, router.templateversion)

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
        if errorCode & 9:
            str = str + [ 'ping' ]
        if errorCode & 16:
            str = str + [ 'filesystem' ]
        if errorCode & 32:
            str = str + [ 'disk' ]
        return ",".join(str)
        if errorCode & 64:
            str = str + [ 'password' ]
        return ",".join(str)
        if errorCode & 128:
            str = str + [ 'reserved' ]
        return ",".join(str)
                
            

    def examineRouter(alarmedRoutersCache, network, router):
        if router.isredundantrouter and (router.redundantstate not in ['MASTER', 'BACKUP']):
            if network.rr_type:
                return {'action': 'restart', 'safetylevel': 'Best', 'comment': 'Redundancy state broken, redundancy present'}
            else:
                return {'action': 'restart', 'safetylevel': 'Downtime', 'comment': 'Redundancy state broken, no redundancy'}
        
        # We should now try to assess the router internal status (with SSH)
        #retcode, output = examineRouterInternals(router)
        
        retcode, output = examineRouterInternalsQuick(alarmedRoutersCache, router)
        if retcode == 32:
            return {'action': 'log-cleanup', 'safetylevel': 'Best', 'comment': output + ": " + str(retcode) + " (" + resolveRouterErrorCode(retcode) + ")" }
        if retcode != 0:
            return {'action': 'unknown', 'safetylevel': 'Unknown', 'comment': output + ": " + str(retcode) + " (" + resolveRouterErrorCode(retcode) + ")" }

        return {'action': None, 'safetylevel': None, 'comment': None}

    networkData = c.listNetworks({})
    for network in networkData:
        if DEBUG > 0:
            print " + Processing: network.name = %s (%s)" % (network.name, network.state)
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

        advRouters = []
        if opFilterRouters:
            routersData = c.getRouterData({'networkid': network.id})
            if routersData:
                for r in routersData:
                    diag = examineRouter(alarmedRoutersCache, network, r)
                    if ( opFilterAll or (diag['action'] != None) ):
                        advRouters = advRouters + [{ 'id': r.id, 'name': r.name, 'domain': network.domain, 'asset_type': 'router', 'adv_action': diag['action'], 'adv_safetylevel': diag['safetylevel'], 'adv_comment': diag['comment'] }]
                        results = results + [{ 'id': r.id, 'name': r.name, 'domain': network.domain, 'asset_type': 'router', 'adv_action': diag['action'], 'adv_safetylevel': diag['safetylevel'], 'adv_comment': diag['comment'] }]

        
        diag = examineNetwork(network, advRouters)
        if ( opFilterAll or (opFilterNetworks and (diag['action'] != None)) ):
            results = results + [{ 'id': network.id, 'type': net_type, 'name': network.name, 'domain': network.domain, 'rr_type': network.rr_type, 'restartrequired': network.restartrequired, 'state': network.state, 'asset_type': 'network', 'adv_action': diag['action'], 'adv_safetylevel': diag['safetylevel'], 'adv_comment': diag['comment'] }]

    vpcData = c.listVPCs({})
    for vpc in vpcData:
        if DEBUG > 0:
            print " + Processing: vpc.name = %s (%s)" % (vpc.name, vpc.state)
        vpc.rr_type = False
        if vpc.redundantvpcrouter:
            vpc.rr_type = vpc.redundantvpcrouter

        advRouters = []
        if opFilterRouters:
            routersData = c.getRouterData({'vpcid': vpc.id})
            if routersData:
                for r in routersData:
                    diag = examineRouter(alarmedRoutersCache, vpc, r)
                    if ( opFilterAll or (diag['action'] != None) ):
                        advRouters = advRouters + [{ 'id': r.id, 'name': r.name, 'domain': vpc.domain, 'asset_type': 'router', 'adv_action': diag['action'], 'adv_safetylevel': diag['safetylevel'], 'adv_comment': diag['comment'] }]
                        results = results + [{ 'id': r.id, 'name': r.name, 'domain': vpc.domain, 'asset_type': 'router', 'adv_action': diag['action'], 'adv_safetylevel': diag['safetylevel'], 'adv_comment': diag['comment'] }]


        diag = examineNetwork(vpc, advRouters)
        if ( opFilterAll or (opFilterNetworks and (diag['action'] != None)) ):
            results = results + [{ 'id': vpc.id, 'type': 'VPC', 'name': vpc.name, 'domain': vpc.domain, 'rr_type': vpc.rr_type, 'restartrequired': vpc.restartrequired, 'state': vpc.state, 'asset_type': 'vpc', 'adv_action': diag['action'], 'adv_safetylevel': diag['safetylevel'], 'adv_comment': diag['comment'] }]
    
    if DEBUG > 0:
        print "getAdvisoriesNetworks/Routers : end"

    return results


def cmdListAdvisories():
    def retrieveAlarmedRoutersCache():
        print "+ Testing SSH to '%s'" % (MGMT_SERVER)
        retcode, output = c.ssh.testSSHConnection(MGMT_SERVER)
        print "   + retcode=%d, output=%s" % (retcode, output)
        if retcode != 0:
            print "Failed to ssh to management server %s, please investigate." % (MGMT_SERVER)
            sys.exit(1)

        # MGMT servers are already checking the routerVMs, we can use that cache
        alarmedRoutersCache = {}
        if DEBUG>0:
            print "Fetching alarmed routers cache..."
        mgtSsh = "cat /tmp/routervms_problem"
        retcode, output = c.ssh.runSSHCommand(MGMT_SERVER, mgtSsh)
        print " + retcode=%d" % (retcode)
        import re
        lines = output.split('\n')
        for line in lines:
            m = re.match("(\S+) \[(.*)\] (\d+)", line)
            if m:
                if DEBUG>0:
                    print "r: %s, n: %s, code: %s" % (m.group(1), m.group(2), m.group(3))
                alarmedRoutersCache[m.group(1)] = { 'network': m.group(2), 'code': int(m.group(3)), 'checked': False }
        return alarmedRoutersCache
        
    
    results = []
    if opFilterNetworks or opFilterRouters:
        alarmedRoutersCache = retrieveAlarmedRoutersCache()
        results = results + getAdvisoriesNetworks(alarmedRoutersCache)
    if opFilterHosts:
        results = results + getAdvisoriesHosts()
    if opFilterInstances:
        results = results + getAdvisoriesInstances()
    counter = 0

    def getSortKey(item):
        return item['asset_type'].upper() + '-' + item['name'].upper() 

    results = sorted(results, key=getSortKey)
    
#    import pprint
#    pp = pprint.PrettyPrinter(indent=4)
#    pp.pprint(networkData)
    
    # Empty line
    print
    t = PrettyTable(["#", "Type", "Name", "ID", "Domain", "Action", "SafetyLevel", "Comment"])
    t.align["Comment"] = "l"
    
    if plainDisplay == 1:
        t.border = False
        t.header = False
        t.padding_width = 1

    for a in results:
        counter = counter + 1

        t.add_row([counter, a['asset_type'], a['name'], a['id'], a['domain'], a['adv_action'], a['adv_safetylevel'], a['adv_comment']])

    # Display table
    print t



if command == 'list':
    cmdListAdvisories()
