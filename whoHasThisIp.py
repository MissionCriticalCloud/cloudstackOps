#!/usr/bin/python

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

# Script to display who uses a given ip address
# Remi Bergsma - rbergsma@schubergphilis.com

import time
import sys
import getopt
from cloudstackops import cloudstacksql
import os.path
from random import choice
from prettytable import PrettyTable

# Function to handle our arguments


def handleArguments(argv):
    global DEBUG
    DEBUG = 0
    global DRYRUN
    DRYRUN = 0
    global mysqlHost
    mysqlHost = ''
    global mysqlPasswd
    mysqlPasswd = ''
    global ipaddress
    ipaddress = ''

    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options] ' + \
        '\n  --ip-address -i <ip address>\t\tSearch for this ip address ' + \
        '(partial is allowed)' + \
        '\n  --mysqlserver -s <mysql hostname>\tSpecify MySQL server ' + \
        'to read HA worker table from' + \
        '\n  --mysqlpassword <passwd>\t\tSpecify password to cloud ' + \
        'MySQL user' + \
        '\n  --debug\t\t\t\tEnable debug mode' + \
        '\n  --exec\t\t\t\tExecute for real (not needed for list* scripts)'

    try:
        opts, args = getopt.getopt(
            argv, "hs:i:", [
                "mysqlserver=",
                "ip-address=",
                "mysqlpassword=",
                "debug",
                "exec"])
    except getopt.GetoptError as e:
        print "Error: " + str(e)
        print help
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print help
            sys.exit()
        elif opt in ("-s", "--mysqlserver"):
            mysqlHost = arg
        elif opt in ("-p", "--mysqlpassword"):
            mysqlPasswd = arg
        elif opt in ("-i", "--ip-address"):
            ipaddress = arg
        elif opt in ("--debug"):
            DEBUG = 1
        elif opt in ("--exec"):
            DRYRUN = 0

    # We need at least these vars
    if len(mysqlHost) == 0 or len(ipaddress) == 0:
        print help
        sys.exit()

# Parse arguments
if __name__ == "__main__":
    handleArguments(sys.argv[1:])

# Init our class
s = cloudstacksql.CloudStackSQL(DEBUG, DRYRUN)

if DEBUG == 1:
    print "# Warning: Debug mode is enabled!"

if DRYRUN == 1:
    print "# Warning: dry-run mode is enabled, not running any commands!"

# Connect MySQL
result = s.connectMySQL(mysqlHost, mysqlPasswd)
if result > 0:
    print "Error: MySQL connection failed"
    sys.exit(1)
elif DEBUG == 1:
    print "DEBUG: MySQL connection successful"
    print s.conn

ipaddresses = s.getIpAddressData(ipaddress)
counter = 0
t = PrettyTable(["VM name",
                 "Network Name",
                 "Mac Address",
                 "Ipv4",
                 "Netmask",
                 "Mode",
                 "State",
                 "Created"])
t.align["VM name"] = "l"
t.align["Network Name"] = "l"

for (
        networkname,
        mac_address,
        ip4_address,
        netmask,
        broadcast_uri,
        mode,
        state,
        created,
        vmname) in ipaddresses:
    counter = counter + 1

    vmname = (vmname[:22] + '..') if len(vmname) > 24 else vmname
    networkname = (
        networkname[:22] + '..') if networkname is not None \
        and len(networkname) > 24 else networkname
    t.add_row([vmname,
               networkname,
               mac_address,
               ip4_address,
               netmask,
               mode,
               state,
               created])

# Disconnect MySQL
s.disconnectMySQL()

print t
print "Note: Found " + str(counter) + " results."
