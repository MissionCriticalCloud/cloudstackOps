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

# Script to report the users that exist in accounts
# Remi Bergsma - rbergsma@schubergphilis.com

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
    global display
    display = "screen"

    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options] ' + \
        '\n  --config-profile -c <profilename>\tSpecify the CloudMonkey profile name to get the credentials from (or specify in ./config file)' + \
        '\n  --display -d <email|screen>\t\tEmail the result or print on screen (defaults to screen)' + \
        '\n  --debug\t\t\t\tEnable debug mode' + \
        '\n  --exec\t\t\t\tExecute for real'

    try:
        opts, args = getopt.getopt(
            argv, "hc:d:p:", [
                "config-profile=", "display=", "debug", "exec"])
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
        elif opt in ("-d", "--display"):
            display = arg
        elif opt in ("--debug"):
            DEBUG = 1
        elif opt in ("--exec"):
            DRYRUN = 0

    # Default to cloudmonkey default config file
    if len(configProfileName) == 0:
        configProfileName = "config"

    # Sanity check
    if display != "screen" and display != "email":
        print "Error: invalid display value '" + display + "'"
        sys.exit(1)

# Parse arguments
if __name__ == "__main__":
    handleArguments(sys.argv[1:])

# Init our class
c = cloudstackops.CloudStackOps(DEBUG, DRYRUN)

if DEBUG == 1:
    print "Warning: Debug mode is enabled!"

if DRYRUN == 1:
    print "Warning: dry-run mode is enabled, not running any commands!"

# make credentials file known to our class
c.configProfileName = configProfileName

# Init the CloudStack API
c.initCloudStackAPI()

if DEBUG == 1:
    print "API address: " + c.apiurl
    print "ApiKey: " + c.apikey
    print "SecretKey: " + c.secretkey

# get users
userData = c.reportUsers()

# Empty line
if display == "screen":
    print

counter = 0

for domainid, domain in userData.iteritems():
    # Get domain data
    domainResult = c.listDomains(domainid)
    domainData = domainResult[0]

    # Display on screen
    if display == "screen":
        print "\nOverview for " + domainData.name + " (" + domainData.path + "):"

    # Start table
    t = PrettyTable(
        ["User Account", "Username", "E-mail", "Firstname", "Lastname"])

    if domain is None:
        continue

    for userArray in domain:
        if userArray is None:
            continue

        for user in userArray:
            # Handle special chars in names
            user.firstname = c.removeNonAscii(user.firstname)
            user.lastname = c.removeNonAscii(user.lastname)

            # Generate table
            t.add_row([user.account,
                       user.username,
                       user.email,
                       user.firstname,
                       user.lastname])

            if user.email is None:
                user.email = "Unknown"

    if display == "screen":
        print t
    elif display == "email":
        userTable = t.get_html_string(format=True)

    # E-mail the report
    if display == "email":
        # Get user data to e-mail
        adminData = c.getDomainAdminUserData(domainid)
        if adminData is None or adminData == 1 or not adminData.email:
            print "Warning: no valid e-mail address found, skipping " + domainData.name
            continue

        print "Note: Sending report to " + adminData.email
        if not adminData.email:
            print "Warning: Skipping mailing due to missing e-mail address."

        templatefile = open("email_template/reportAccounts.txt", "r")
        emailbody = templatefile.read()
        emailbody = emailbody.replace("FIRSTNAME", adminData.firstname)
        emailbody = emailbody.replace("LASTNAME", adminData.lastname)
        emailbody = emailbody.replace("USERTABLE", userTable)
        emailbody = emailbody.replace("DOMAIN", domainData.name)
        emailbody = emailbody.replace("PATH", domainData.path)
        emailbody = emailbody.replace("ORGANIZATION", c.organization)
        emailbody = emailbody.replace("EMAILADRESS", c.mail_from)
        templatefile.close()

        if DRYRUN == 1:
            print "Note: Not sending notification e-mails due to DRYRUN setting. Would have e-mailed (from " + c.mail_from + ") to " + adminData.email + " for domain " + domainData.name
        else:
            try:
                # Notify user
                msgSubject = 'Monthly overview of users in your domain "' + \
                    domainData.name + '"'
                c.sendMail(c.mail_from, adminData.email, msgSubject, emailbody)

                # Notify admin
                c.sendMail(c.mail_from, c.errors_to, msgSubject, emailbody)
            except:
                print "Warning: failed to send e-mail notification (from " + c.mail_from + ") to " + adminData.email + " for domain " + domainData.name

        if DEBUG == 1:
            print emailbody

if DEBUG == 1:
    print "Note: We're done!"
