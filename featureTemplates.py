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

# Script to manage / (un)feature custom build templates
# Remi Bergsma - rbergsma@schubergphilis.com

import time
import sys
import getopt
from cloudstackops import cloudstackops
import os.path
from random import choice
from prettytable import PrettyTable
from datetime import date
import re

# Function to handle our arguments


def handleArguments(argv):
    global DEBUG
    DEBUG = 0
    global DRYRUN
    DRYRUN = 1
    global configProfileName
    configProfileName = ''
    global zoneName
    zoneName = ''

    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options]' + \
        '\n  --config-profile -c \t\t\tSpecify the CloudMonkey profile name to get the credentials from (or specify in ./config file)' + \
        '\n  --zone -z <zonename>\t\t\tLimit to this zone' + \
        '\n  --debug\t\t\t\tEnable debug mode' + \
        '\n  --exec\t\t\t\tExecute for real'

    try:
        opts, args = getopt.getopt(
            argv, "hc:z:", [
                "config-profile=", "zone", "debug", "exec"])
    except getopt.GetoptError as e:
        print("Error: " + str(e))
        print(help)
        sys.exit(2)

    if len(opts) == 0:
        print(help)
        sys.exit(2)

    for opt, arg in opts:
        if opt == '-h':
            print(help)
            sys.exit()
        elif opt in ("-c", "--config-profile"):
            configProfileName = arg
        elif opt in ("-z", "--zone"):
            zoneName = arg
        elif opt in ("--debug"):
            DEBUG = 1
        elif opt in ("--exec"):
            DRYRUN = 0

    # Default to cloudmonkey default config file
    if len(configProfileName) == 0:
        configProfileName = "config"

# Parse arguments
if __name__ == "__main__":
    handleArguments(sys.argv[1:])

# Init our class
c = cloudstackops.CloudStackOps(DEBUG, DRYRUN)

if DEBUG == 1:
    print("Warning: Debug mode is enabled!")

if DRYRUN == 1:
    print("Warning: dry-run mode is enabled, not running any commands!")

# make credentials file known to our class
c.configProfileName = configProfileName

# Init the CloudStack API
c.initCloudStackAPI()

if len(zoneName) > 1:
    zoneID = c.checkCloudStackName(
        {'csname': zoneName, 'csApiCall': 'listZones'})
    print("Note: Only processing templates in zone " + zoneName)

print("Warning: We only manage XenServer templates!")

if DEBUG == 1:
    print("API address: " + c.apiurl)
    print("ApiKey: " + c.apikey)
    print("SecretKey: " + c.secretkey)

# get templates from CloudStack
if len(zoneName) > 1:
    templateData = c.listTemplates({'templatefilter': 'all', 'zoneid': zoneID})
else:
    templateData = c.listTemplates({'templatefilter': 'all'})
# Sort by creation date, newest first
templateData.sort(key=lambda x: x.created, reverse=True)

if DEBUG == 1:
    c.pp.pprint(templateData)

# We need this later
featureTemplates = {}
unfeatureTemplates = {}
deleteTemplates = {}
keepCount = {}

# Keep this many templates per zone per OStype
keepNr = 4

# Let's see what we currently have
for template in templateData:
    if template is None:
        continue
    # Skip templates that are not usable anyway
    if template.isready == False:
        continue
    # Don't mess with BUILTIN and SYSTEM templates, just for sure
    if template.templatetype.upper() != "USER":
        continue
    # Our build templates are XenServer only, don't touch others
    if template.hypervisor != "XenServer":
        continue

    # Delete cross-zone templates as they only bring trouble. But keep
    # systemvm templates.
    if template.crossZones and "systemvm" not in template.name.lower():
        deleteTemplates[template.id] = template
        if template.isfeatured:
            unfeatureTemplates[template.id] = template
        continue

    # Find templates that match our build pattern: like m2015-02 or w2015-01
    m = re.findall('[mw]\d{4}-\d{2}', template.name)
    # Skip all others
    if len(m) == 0:
        # Only our build templates should be featured. Unfeature the others.
        if template.isfeatured:
            unfeatureTemplates[template.id] = template
        continue

    # Extract week / month number
    parts = m[0].split('-')
    for p in parts:
        if p.isdigit():
            buildNr = int(p)
        elif p.startswith('w'):
            buildType = "Week"
        elif p.startswith('m'):
            buildType = "Month"

    # Figure out OS names
    osName = template.name[:9].replace("_", "").replace(" ", "_")

    # Feature the latest ostypename + zonename combi
    key = osName.lower() + template.zonename
    if osName.lower().startswith(
        ("rhel",
         "centos_6",
         "centos_7",
         "ubuntu",
         "win")):
        if key in featureTemplates:
            if featureTemplates[key].created < template.created:
                featureTemplates[key] = template
            elif template.isfeatured:
                unfeatureTemplates[template.id] = template
        else:
            featureTemplates[key] = template
    elif template.isfeatured:
        unfeatureTemplates[key] = template

    # Mark the ones we will keep and delete
    countkey = osName + template.zonename
    if countkey in keepCount:
        keepCount[countkey] += 1
    else:
        keepCount[countkey] = 0

    if DEBUG == 1:
        print("Counter " + countkey + " " + str(keepCount[countkey]))

    keepkey = countkey + str(keepCount[countkey])
    if keepCount[countkey] > keepNr:
        deleteTemplates[keepkey] = template

# This is the work we need to process
loopWork = ['featureTemplates', 'unfeatureTemplates', 'deleteTemplates']

# Just print what we would do
if DRYRUN == 1:
    for work in loopWork:
        t = PrettyTable(["Name",
                         "Displaytext",
                         "ostypename",
                         "zonename",
                         "isfeatured",
                         "isready",
                         "Created",
                         "CrossZones",
                         "Type"])
        print(work + ":")
        # Generate table
        for templatekey, template in eval(work).items():
            t.add_row([template.name,
                       template.displaytext,
                       template.ostypename,
                       template.zonename,
                       template.isfeatured,
                       template.isready,
                       template.created,
                       template.crossZones,
                       template.templatetype])
        print(t)

# Make changes to the templates
elif DRYRUN == 0:
    for work in loopWork:
        print("Processing " + work + "..")
        if work == "featureTemplates":
            for templatekey, template in eval(work).items():
                if DEBUG == 1:
                    print("DEBUG: Setting feature flag for " + template.name + " ..")
                if template.isfeatured == False:
                    result = c.updateTemplatePermissins(
                        {'templateid': template.id, 'isfeatured': 'true'})
                    if result == 1:
                        print("ERROR: Something went wrong!")
                    else:
                        print("Feature flag set OK for " + template.name)
                else:
                    print("Note: Template " + template.name + " is alreay featured, ignoring.")
        elif work == "unfeatureTemplates":
            for templatekey, template in eval(work).items():
                if DEBUG == 1:
                    print("DEBUG: Unsetting feature flag for " + template.name + " ..")
                if template.isfeatured:
                    result = c.updateTemplatePermissins(
                        {'templateid': template.id, 'isfeatured': 'false'})
                    if result == 1:
                        print("ERROR: Something went wrong!")
                    else:
                        print("Feature flag removed OK for " + template.name)
                else:
                    print("Note: Template " + template.name + " is not featured, ignoring.")
        elif work == "deleteTemplates":
            for templatekey, template in eval(work).items():
                if DEBUG == 1:
                    print("DEBUG: Deleting template " + template.name + " ..")
                result = c.deleteTemplate({'id': template.id})
                if result == 1:
                    print("ERROR: Something went wrong!")
                else:
                    print("Template " + template.name + " removed OK!")

if DEBUG == 1:
    print("Note: We're done!")
