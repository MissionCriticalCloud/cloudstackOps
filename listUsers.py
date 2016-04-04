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

# Script to simplify CS user management
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
    global opFilterUsername
    opFilterUsername = None
    global opFilterDomain
    opFilterDomain = None
    global plainDisplay
    plainDisplay = 0
    global optFirstName, optLastName, optEmail, optPassword, optAccount
    optFirstName = None
    optLastName = None
    optEmail = None
    optPassword = None
    optAccount = None
    


    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options] ' + \
        '\n  --config-profile -c <profilename>\t\tSpecify the CloudMonkey profile name to get the credentials from (or specify in ./config file)' + \
        '\n  --debug\t\t\t\t\tEnable debug mode' + \
        '\n  --plain-display\t\t\t\tEnable plain display, no pretty tables' + \
        '\n' + \
        '\n  Commands:' + \
        '\n  --list\t\t\t\tLists users applying filters (see below). This is the default command' + \
        '\n  --create\t\t\t\tCreate user. See required parameters below' + \
        '\n  --delete\t\t\t\tDelete user. WARNING it deletes all commands within the search filters, verify before with --list' + \
        '\n  --enable\t\t\t\tEnable user(s). WARNING idem.' + \
        '\n  --disable\t\t\t\tDisable user(s). WARNING idem.' + \
        '\n' + \
        '\n  Filters:' + \
        '\n  --username -u <username> \t\tSelects only the specified username' + \
        '\n  --domain -d <domain> \t\t\tSearch only within <domain> domain' + \
        '\n  --account -a <account> \t\tUse account <account> as filter' + \
        '\n' + \
        '\n  Parameters --create:' + \
        '\n  --first <name> \t\t\tFirst name' + \
        '\n  --last <name> \t\t\tLast name' + \
        '\n  --email <email> \t\t\tEmail' + \
        '\n  --password <password> \t\tPassword (plaintext)' + \
        '\n  --domain <name> \t\t\tDomain name' + \
        '\n  --account <name> \t\t\tAccount name'

    try:
        opts, args = getopt.getopt(
            argv, "hc:u:d:a:", [
                "config-profile=", "debug", "username=", "plain-display", "domain=", "list", "create", "delete", "enable", "disable", "first=", "last=", "email=", "password=", "domain=", "account="])
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
        elif opt in ("--domain", "-d"):
            opFilterDomain = arg
        elif opt in ("--debug"):
            DEBUG = 1
        elif opt in ("--create"):
            command = 'create'
        elif opt in ("--delete"):
            command = 'delete'
        elif opt in ("--disable"):
            command = 'disable'
        elif opt in ("--enable"):
            command = 'enable'
        elif opt in ("--list"):
            command = 'list'
        elif opt in ("-u", "--username"):
            opFilterUsername = arg
        elif opt in ("--plain-display"):
            plainDisplay = 1
        elif opt in ("--first"):
            optFirstName = arg
        elif opt in ("--last"):
            optLastName = arg
        elif opt in ("--email"):
            optEmail = arg
        elif opt in ("--password"):
            optPassword = arg
        elif opt in ("--account", "-a"):
            optAccount = arg

    # Default to cloudmonkey default config file
    if len(configProfileName) == 0:
        configProfileName = "config"

    if command == 'create' and (opFilterUsername == None or optFirstName == None or optLastName == None or optEmail == None or optPassword == None or opFilterDomain == None or optAccount == None):
        print 'Error: For --create command you need to specify --username, --first, --last, --email, --password, --domain, --acount'
        print "Current values are: username=%s, first=%s, last=%s, email=%s, password=%s, domain=%s, account=%s" % (opFilterUsername, optFirstName, optLastName, optEmail, optPassword, opFilterDomain, optAccount)
        sys.exit(2)

    if DEBUG==1:
        print '[d-d] filterUsername=%s, filterDomain=%s' % (opFilterUsername, opFilterDomain) 

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


def getListUsers(filters):
    domainId = None
    if filters['domain']:
        domainIdr = c.listDomainsExt({'name': filters['domain']})
        if domainIdr and len(domainIdr)>0:
            domainId = domainIdr[0].id
        print '[d] resolved: domainName=%s, domainId=%s' % (filters['domain'], domainId)
    
    userData = c.listUsersExt({'username': filters['username'], 'domainid': domainId, 'account': filters['account']})
    results = []
    if userData:
        for user in userData:
            if DEBUG==1:
                import pprint
                pp = pprint.PrettyPrinter(indent=4)
                pp.pprint(user);
        
            results = results + [{ 'id': user.id, 'username': user.username, 'firstname': user.firstname, 'lastname': user.lastname, 'state': user.state, 'domain': user.domain, 'account': user.account, 'accounttype': user.accounttype }]

    def getSortKey(item):
        return item['username'].upper()
    
    return sorted(results, key=getSortKey)


def cmdListUsers():
    userData = getListUsers({'username' : opFilterUsername, 'domain': opFilterDomain, 'account': optAccount})
    counter = 0

    # Empty line
    print
    t = PrettyTable(["#", "Domain", "Account", "Type", "Username", "Id", "First", "Last", "State"])
    #t.align["VM"] = "l"
    
    if plainDisplay == 1:
        t.border = False
        t.header = False
        t.padding_width = 1

    if userData:
        for u in userData:
            counter = counter + 1
            t.add_row([counter, u['domain'], u['account'], u['accounttype'], u['username'], u['id'], u['firstname'], u['lastname'], u['state']])

    # Display table
    print t

def cmdDisableUsers():
    userData = getListUsers({'username' : opFilterUsername, 'domain': opFilterDomain})
    cmdListUsers()
    if userData:
        for user in userData:
            c.disableUser(user['id'])
    cmdListUsers()

def cmdEnableUsers():
    userData = getListUsers({'username' : opFilterUsername, 'domain': opFilterDomain})
    cmdListUsers()
    if userData:
        for user in userData:
            c.enableUser(user['id'])
    cmdListUsers()

def cmdDeleteUsers():
    userData = getListUsers({'username' : opFilterUsername, 'domain': opFilterDomain})
    
    if userData:
        for user in userData:
            r = c.deleteUser(user['id'])
            if type(r) is int:
                # We rely on the core library to print the error... (?)
                return 1

    cmdListUsers()

def cmdCreateUser():
    domainId = None
    domainIdr = c.listDomainsExt({'name': opFilterDomain})
    if not domainIdr or len(domainIdr)<=0:
        print "Error: Domain '%s' can not be found" % (opFilterDomain)
        sys.exit(2)
    domainId = domainIdr[0].id
    print '[d] resolved: domainName=%s, domainId=%s' % (opFilterDomain, domainId)
    
    r = c.createUser({ 'username': opFilterUsername, 'firstname': optFirstName, 'lastname': optLastName, 'email': optEmail, 'password': optPassword, 'domainid': domainId, 'account': optAccount})
    if type(r) is int:
        # We rely on the core library to print the error... (?)
        return 1

    cmdListUsers()

    

if command == 'list':
    cmdListUsers()
elif command == 'enable':
    cmdEnableUsers()
elif command == 'disable':
    cmdDisableUsers()
elif command == 'create':
    cmdCreateUser()
elif command == 'delete':
    cmdDeleteUsers()
