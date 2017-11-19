#!/usr/bin/python

import getopt
import os.path
import sys
import time
from datetime import datetime

from cloudstackops import cloudstackops
from cloudstackops import cloudstacksql


# Function to handle our arguments


def handleArguments(argv):
    global DEBUG
    DEBUG = 0
    global DRYRUN
    DRYRUN = 1
    global networkid
    networkid = ''
    global configProfileName
    configProfileName = ''
    global force
    force = 0
    global threads
    threads = 5
    global mysqlHost
    mysqlHost = ''
    global mysqlPasswd
    mysqlPasswd = ''

    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options] ' + \
           '\n  --config-profile -c <profilename>\tSpecify the CloudMonkey profile name to get the credentials from ' \
           '(or specify in ./config file)' + \
           '\n  --network-id -i <network-id>\tMigrate Isolated network with this UUID. Network name is also' \
           'supported as long as it is unique.' \
           '\n  --mysqlserver -s <mysql hostname>\tSpecify MySQL server config section name' + \
           '\n  --mysqlpassword <passwd>\t\tSpecify password to cloud MySQL user' + \
           '\n  --debug\t\t\t\tEnable debug mode' + \
           '\n  --exec\t\t\t\tExecute for real'

    try:
        opts, args = getopt.getopt(
            argv, "hc:i:t:p:s:b:", [
                "config-profile=", "network-id=", "mysqlserver=", "mysqlpassword=",
                "debug", "exec", "force"])
    except getopt.GetoptError as e:
        print "Error: " + str(e)
        print help
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print help
            sys.exit()
        elif opt in ("-c", "--config-profile"):
            configProfileName = arg
        elif opt in ("-i", "--network-id"):
            networkid = arg
        elif opt in ("-s", "--mysqlserver"):
            mysqlHost = arg
        elif opt in ("-p", "--mysqlpassword"):
            mysqlPasswd = arg
        elif opt in ("--debug"):
            DEBUG = 1
        elif opt in ("--exec"):
            DRYRUN = 0
        elif opt in ("--force"):
            force = 1

    # Default to cloudmonkey default config file
    if len(configProfileName) == 0:
        configProfileName = "config"

    # We need at least these vars
    if len(networkid) == 0 or len(mysqlHost) == 0:
        print help
        sys.exit()


def exit_script(message):
    print "Fatal Error: %s" % message
    sys.exit(1)


# Parse arguments
if __name__ == "__main__":
    handleArguments(sys.argv[1:])

# Start time
print "Note: Starting @ %s" % time.strftime("%Y-%m-%d %H:%M")
start_time = datetime.now()

if DEBUG == 1:
    print "Warning: Debug mode is enabled!"

if DRYRUN == 1:
    print "Warning: dry-run mode is enabled, not running any commands!"

# Init CloudStackOps class
c = cloudstackops.CloudStackOps(DEBUG, DRYRUN)
c.task = "Isolated network -> VPC migration"
c.slack_custom_title = "Migration details"

# Init SQL class
s = cloudstacksql.CloudStackSQL(DEBUG, DRYRUN)

# Connect MySQL
result = s.connectMySQL(mysqlHost, mysqlPasswd)
if result > 0:
    message = "MySQL connection failed"
    c.print_message(message=message, message_type="Error", to_slack=True)
    sys.exit(1)
elif DEBUG == 1:
    print "DEBUG: MySQL connection successful"
    print s.conn

# make credentials file known to our class
c.configProfileName = configProfileName

# Init the CloudStack API
c.initCloudStackAPI()

# TODO Make a dict out of this, match it with the existing network offerings
# Default VPC offering
vpc_offering_db_id = 1
# DefaultIsolatedNetworkOfferingForVpcNetworks
vpc_tier_offering_db_id = 14

network_uuid = c.checkCloudStackName({'csname': networkid,
                                      'csApiCall': 'listNetworks',
                                      'listAll': 'true',
                                      'isProjectVm': False})

if DEBUG == 1:
    print "API address: " + c.apiurl
    print "ApiKey: " + c.apikey
    print "SecretKey: " + c.secretkey
    print "Username: " + c.username
    print "Password: " + c.password

# Check cloudstack IDs
if DEBUG == 1:
    print "Debug: Checking CloudStack IDs of provided input.."
    print "Network UUID: %s" % network_uuid

# Get Isolated network details
isolated_network_db_id = s.get_network_db_id(network_uuid)

# 1. Create the new VPC
vpc_db_id = s.create_vpc(isolated_network_db_id, vpc_offering_db_id)
# vpc_db_id = 1

# 2. Fill the vpc service map
s.fill_vpc_service_map(vpc_db_id)

# 3. Update network service map
s.migrate_ntwk_service_map_from_isolated_network_to_vpc(isolated_network_db_id)

# 4. Create network acl from isolated network egress for vpc
egress_network_acl_db_id = s.create_network_acl_for_vpc(vpc_db_id, networkid + '-fwrules')
# egress_network_acl_db_id = 6

# TODO Think about default deny / default allow
# 5. Fill egress network acl
s.convert_isolated_network_egress_rules_to_network_acl(isolated_network_db_id, egress_network_acl_db_id)

# 6. Update network to become a VPC tier
s.update_isolated_network_to_be_a_vpc_tier(vpc_db_id, egress_network_acl_db_id, vpc_tier_offering_db_id, isolated_network_db_id)

# 7. Migrate public ips to vpc
ipadresses = s.get_all_ipaddresses_from_network(isolated_network_db_id)
for ipaddress in ipadresses:
    # Create ACL for ingress rules
    # ingress_acl_db_id = s.create_network_acl_for_vpc(vpc_db_id, ipaddress[1] + '-ingress_rules')

    # Fill ingress ACL with rules
    s.convert_isolated_network_public_ip_rules_to_network_acl(ipaddress[0], egress_network_acl_db_id)

    # Migrate public ip to vpc
    s.migrate_public_ip_from_isolated_network_to_vpc(vpc_db_id, 2, ipaddress[0])

# HACK Update Egress cidrs to be allow all
s.fix_egress_cidr_allow_all(egress_network_acl_db_id)


# 8. Migrate routers
s.migrate_routers_from_isolated_network_to_vpc(vpc_db_id, isolated_network_db_id)
