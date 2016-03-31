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
        elif opt in ("--debug"):
            DEBUG = 1
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

    # Default to cloudmonkey default config file
    if len(configProfileName) == 0:
        configProfileName = "config"

# Parse arguments
if __name__ == "__main__":
    handleArguments(sys.argv[1:])

# Init our class
c = cloudstackops.CloudStackOps(DEBUG, DRYRUN)

if DEBUG == 1:
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
    if DEBUG == 1:
        print "getAdvisoriesHosts : begin"
    results = []
    if DEBUG == 1:
        print "getAdvisoriesHosts : end"
    return results

def getAdvisoriesInstances():
    if DEBUG == 1:
        print "getAdvisoriesInstances : begin"
    results = []
    if DEBUG == 1:
        print "getAdvisoriesInstances : end"
    return results

def getAdvisoriesNetworks():
    if DEBUG == 1:
        print "getAdvisoriesNetworks/Routers : begin"
    results = []

    # This method will analyse the network and return an advisory
    def examineNetwork(network):
        if network.restartrequired:
            if network.rr_type:
                return {'action': 'restart', 'safetylevel': 'Best', 'comment': 'Restart flag on, redundancy present'}
            else:
                return {'action': 'restart', 'safetylevel': 'Downtime', 'comment': 'Restart flag on, no redundancy'}
        return {'action': None, 'safetylevel': None, 'comment': None}

    def examineRouter(network, router):
        if router.isredundantrouter and (router.redundantstate not in ['MASTER', 'BACKUP']):
            if network.rr_type:
                return {'action': 'restart', 'safetylevel': 'Best', 'comment': 'Redundancy state broken, redundancy present'}
            else:
                return {'action': 'restart', 'safetylevel': 'Downtime', 'comment': 'Redundancy state broken, no redundancy'}
        
        # We should now try to assess the router internal status (with SSH)
        
        return {'action': None, 'safetylevel': None, 'comment': None}

    networkData = c.listNetworks({})
    for network in networkData:
        if DEBUG == 1:
            print "net.name " + network.name
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

        if opFilterRouters:
            routersData = c.getRouterData({'networkid': network.id})
            routers = []
            if routersData:
                for r in routersData:
                    diag = examineRouter(network, r)
                    if ( opFilterAll or (diag['action'] != None) ):
                        results = results + [{ 'id': r.id, 'name': r.name, 'domain': network.domain, 'asset_type': 'router', 'adv_action': diag['action'], 'adv_safetylevel': diag['safetylevel'], 'adv_comment': diag['comment'] }]                

        diag = examineNetwork(network)
        if ( opFilterAll or (opFilterNetworks and (diag['action'] != None)) ):
            results = results + [{ 'id': network.id, 'type': net_type, 'name': network.name, 'domain': network.domain, 'rr_type': network.rr_type, 'restartrequired': network.restartrequired, 'state': network.state, 'asset_type': 'network', 'adv_action': diag['action'], 'adv_safetylevel': diag['safetylevel'], 'adv_comment': diag['comment'] }]

    vpcData = c.listVPCs({})
    for vpc in vpcData:
        if DEBUG == 1:
            print "vpc.name " + network.name
        vpc.rr_type = False
        if vpc.redundantvpcrouter:
            vpc.rr_type = vpc.redundantvpcrouter

        if opFilterRouters:
            routersData = c.getRouterData({'vpcid': vpc.id})
            routers = []
            if routersData:
                for r in routersData:
                    diag = examineRouter(vpc, r)
                    if ( opFilterAll or (diag['action'] != None) ):
                        results = results + [{ 'id': r.id, 'name': r.name, 'domain': network.domain, 'asset_type': 'router', 'adv_action': diag['action'], 'adv_safetylevel': diag['safetylevel'], 'adv_comment': diag['comment'] }]                


        diag = examineNetwork(vpc)
        if ( opFilterAll or (opFilterNetworks and (diag['action'] != None)) ):
            results = results + [{ 'id': vpc.id, 'type': 'VPC', 'name': vpc.name, 'domain': vpc.domain, 'rr_type': vpc.rr_type, 'restartrequired': vpc.restartrequired, 'state': vpc.state, 'asset_type': 'vpc', 'adv_action': diag['action'], 'adv_safetylevel': diag['safetylevel'], 'adv_comment': diag['comment'] }]
    
    if DEBUG == 1:
        print "getAdvisoriesNetworks/Routers : end"

    return results


def cmdListAdvisories():
    results = []
    if opFilterNetworks or opFilterRouters:
        results = results + getAdvisoriesNetworks()
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
