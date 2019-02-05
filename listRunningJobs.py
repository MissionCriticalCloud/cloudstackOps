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

# Script to list all VMs in a given cluster
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
    global hypervisorName
    hypervisorName = ''
    global plainDisplay
    plainDisplay = 0

    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options] ' + \
        '\n  --mysqlserver -s <mysql hostname>\tSpecify MySQL server to ' + \
        'read HA worker table from' + \
        '\n  --mysqlpassword <passwd>\t\tSpecify password to cloud ' \
        'MySQL user' + \
        '\n  --plain-display\t\t\tEnable plain display, no pretty tables' + \
        '\n  --debug\t\t\t\tEnable debug mode' + \
        '\n  --exec\t\t\t\tExecute for real (not needed for list* scripts)'

    try:
        opts, args = getopt.getopt(argv, "hs:n:", [
            "mysqlserver=",
            "mysqlpassword=",
            "plain-display",
            "debug",
            "exec"
        ])
    except getopt.GetoptError as e:
        print("Error: " + str(e))
        print(help)
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print(help)
            sys.exit()
        elif opt in ("-s", "--mysqlserver"):
            mysqlHost = arg
        elif opt in ("-p", "--mysqlpassword"):
            mysqlPasswd = arg
        elif opt in ("--plain-display"):
            plainDisplay = 1
        elif opt in ("--debug"):
            DEBUG = 1
        elif opt in ("--exec"):
            DRYRUN = 0

    # We need at least these vars
    if len(mysqlHost) == 0:
        print(help)
        sys.exit()

# Parse arguments
if __name__ == "__main__":
    handleArguments(sys.argv[1:])

# Init our class
s = cloudstacksql.CloudStackSQL(DEBUG, DRYRUN)

if DEBUG == 1:
    print("Warning: Debug mode is enabled!")

if DRYRUN == 1:
    print("Warning: dry-run mode is enabled, not running any commands!")

# Connect MySQL
result = s.connectMySQL(mysqlHost, mysqlPasswd)
if result > 0:
    print("Error: MySQL connection failed")
    sys.exit(1)
elif DEBUG == 1:
    print("DEBUG: MySQL connection successful")
    print(s.conn)

asyncjobs = s.getAsyncJobData()
counter = 0
t = PrettyTable([
    "username",
    "account_name",
    "instance_name",
    "vm_state",
    "job_cmd",
    "job_dispatcher",
    "Job created",
    "Mgt Server",
    "Job ID",
    "Related job ID"
])
t.align["instance_name"] = "l"

if plainDisplay == 1:
    t.border = Falsusername, account_name, instance_id, vm_state, job_cmd, \
        job_dispatcher, created, mgtserver, jobid, related
    t.header = False
    t.padding_width = 1

for (username, account_name, instance_id, vm_state, job_cmd, job_dispatcher,
        created, mgtserver, jobid, related) in asyncjobs:
    counter = counter + 1
    t.add_row([
        username,
        account_name,
        instance_id,
        vm_state,
        job_cmd,
        job_dispatcher,
        created,
        mgtserver,
        jobid,
        related
    ])

# Disconnect MySQL
s.disconnectMySQL()
print(t.get_string(sortby="instance_name"))

if plainDisplay == 0:
    print("Note: Found " + str(counter) + " running jobs.")
