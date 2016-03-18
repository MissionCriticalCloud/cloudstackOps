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

# Script to list and cycle all networks
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
    global opFilter
    opFilter = None
    global opFilterNoRR
    opFilterNoRR = None
    global opFilterName
    opFilterName = None
    global plainDisplay
    plainDisplay = 0

    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options] ' + \
        '\n  --config-profile -c <profilename>\t\tSpecify the CloudMonkey profile name to get the credentials from (or specify in ./config file)' + \
        '\n  --debug\t\t\t\t\tEnable debug mode' + \
        '\n  --restart -r\t\t\t\t\tRestarts network w/ cleanup=True' + \
        '\n  --exec\t\t\t\t\tExecute for real (not needed for list* scripts), default: dry-run' + \
        '\n  --plain-display\t\t\t\tEnable plain display, no pretty tables' + \
        '\n' + \
        '\n  Filters:' + \
        '\n  --type <networkType> \t\t\t\tApplies filter to operation, Possible networkTypes: Isolated,Shared,VPC,Isolated' + \
        '\n  --onlyNoRR \t\t\t\t\tSelects only non-redudant VR networks' + \
        '\n  --onlyRR \t\t\t\t\tSelects only redudant VR networks' + \
        '\n  --name -n <name> \t\t\t\tSelects only the specified asset (VPC/network)'

    try:
        opts, args = getopt.getopt(
            argv, "hc:rn:", [
                "config-profile=", "debug", "exec", "restart", "type=", "onlyNoRR", "onlyRR", "name", "plain-display"])
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
        elif opt in ("--exec"):
            DRYRUN = 0
        elif opt in ("-r", "--restart"):
            command = 'restartcleanup'
        elif opt in ("--type"):
            opFilter = arg
        elif opt in ("--onlyNoRR"):
            opFilterNoRR = False
        elif opt in ("--onlyRR"):
            opFilterNoRR = True
        elif opt in ("--name", "-n"):
            opFilterName = arg
        elif opt in ("--plain-display"):
            plainDisplay = 1

    # Default to cloudmonkey default config file
    if len(configProfileName) == 0:
        configProfileName = "config"

    if opFilter != '' and opFilter not in [None, 'Isolated','Shared', 'VPC']:
        print "ERROR: Invalid filter: %s" % opFilter
        sys.exit(3)


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


def getListNetworks(filter=None, filterNoRR=None, assetName=None):
    results = []
    if DEBUG == 1:
        print '[d] getListNetworks() - networkType = %s, rrType = %s' % (opFilter, opFilterNoRR)

    networkData = c.listNetworks()
    for network in networkData:
        rr_type = False
        if network.service:
            for netsvc in network.service:
                if netsvc.capability:
                    for cap in netsvc.capability:
                        if cap.name == 'RedundantRouter':
                            if cap.value == 'true':
                                rr_type = True

        routersData = c.getRouterData({'networkid': network.id})
        routers = []
        if routersData:
            for r in routersData:
                routers = routers + [ r.name ]

        if ( (filter in [None, network.type]) and (filterNoRR in [None, rr_type]) and (assetName in [None, network.name]) ):
            results = results + [{ 'id': network.id, 'type': network.type, 'name': network.name, 'domain': network.domain, 'rr_type': rr_type, 'restartrequired': network.restartrequired, 'state': network.state, 'vrs': ','.join(routers) }]

    vpcData = routers = c.listVPCs()
    for vpc in vpcData:
        rr_type = False
        if vpc.redundantvpcrouter:
            rr_type = vpc.redundantvpcrouter

        routersData = c.getRouterData({'vpcid': vpc.id})
        routers = []
        if routersData:
            for r in routersData:
                routers = routers + [ r.name ]

        if ( (filter in [None, 'VPC']) and (filterNoRR in [None, rr_type]) and (assetName in [None, vpc.name]) ):
             results = results + [{ 'id': vpc.id, 'type': 'VPC', 'name': vpc.name, 'domain': vpc.domain, 'rr_type': rr_type, 'restartrequired': vpc.restartrequired, 'state': vpc.state, 'vrs': ','.join(routers) }]

    def getSortKey(item):
        return item['name'].upper()
    
    return sorted(results, key=getSortKey)


def cmdListNetworks():
    networkData = getListNetworks(opFilter, opFilterNoRR, opFilterName)
    counter = 0

#    import pprint
#    pp = pprint.PrettyPrinter(indent=4)
#    pp.pprint(networkData)
    
    # Empty line
    print
    t = PrettyTable(["#", "Network", "Type", "ID", "Domain", "State", "Redundant?", "RestartReq?", "VRs"])
    #t.align["VM"] = "l"
    
    if plainDisplay == 1:
        t.border = False
        t.header = False
        t.padding_width = 1

    for n in networkData:
        counter = counter + 1

        t.add_row([counter, n['name'], n['type'], n['id'], n['domain'], n['state'], n['rr_type'], n['restartrequired'], n['vrs']])

    # Display table
    print t

def cmdRestartNetworks():
    networkData = getListNetworks(opFilter, opFilterNoRR, opFilterName)

    print
    import pprint
    pp = pprint.PrettyPrinter(indent=4)
#    pp.pprint(networkData)

    for n in networkData:
        print "[I] Restarting network/VPC: %s" % n['name']
        if DEBUG ==1:
            print "[d] + state=%s, type=%s, rr_type=%s" % (n['state'], n['type'], n['rr_type'])
            print "[d] + id=%s" % (n['id'])
        
        if n['type'] == 'VPC':
            routersData = c.getRouterData({'vpcid': n['id']})
        else:
            routersData = c.getRouterData({'networkid': n['id']})
        if routersData:
            for r in routersData:
                #pp.pprint(r)
                print "[d]   + %s (state=%s, rr=%s)" % (r.name, r.state, r.redundantstate)

        sys.stdout.flush()
        if n['type'] == 'VPC' and n['state'] == 'Enabled':
            c.restartVPC(n['id'], True)
        elif n['type'] in ('Isolated', 'Shared') and n['state'] == 'Implemented':
            print c.restartNetwork(n['id'], True)



if command == 'list':
    cmdListNetworks()
elif command == 'restartcleanup':
    cmdRestartNetworks()
