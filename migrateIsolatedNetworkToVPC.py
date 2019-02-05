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
    global networkname
    networkname = ''
    global networkuuid
    networkuuid = ''
    global vpcofferingname
    vpcofferingname = ''
    global networkofferingname
    networkofferingname = ''
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
           '\n  --network-name -n <network-name>\tMigrate Isolated network with this name.' \
           '\n  --uuid -u <uuid>\t\t\tThe UUID of the network. When provided, the network name will be ignored.' \
           '\n  --vpc-offering -v <vpc-offering-name>\tThe name of the VPC offering.' \
           '\n  --network-offering -o <network-offering-name>\tThe name of the VPC tier network offering.' \
           '\n  --mysqlserver -s <mysql hostname>\tSpecify MySQL server config section name' + \
           '\n  --mysqlpassword <passwd>\t\tSpecify password to cloud MySQL user' + \
           '\n  --debug\t\t\t\tEnable debug mode' + \
           '\n  --exec\t\t\t\tExecute for real'

    try:
        opts, args = getopt.getopt(
            argv, "hc:n:u:v:o:t:p:s:b:", [
                "config-profile=", "network-name=", "uuid=", "vpc-offering=", "network-offering=", "mysqlserver=",
                "mysqlpassword=", "debug", "exec", "force"
            ])
    except getopt.GetoptError as e:
        print("Error: " + str(e))
        print(help)
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print(help)
            sys.exit()
        elif opt in ("-c", "--config-profile"):
            configProfileName = arg
        elif opt in ("-n", "--network-name"):
            networkname = arg
        elif opt in ("-u", "--uuid"):
            networkuuid = arg
        elif opt in ("-v", "--vpc-offering"):
            vpcofferingname = arg
        elif opt in ("-o", "--network-offering"):
            networkofferingname = arg
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
    if (len(networkname) == 0 and len(networkuuid) == 0) or len(mysqlHost) == 0 or len(vpcofferingname) == 0 or \
                    len(networkofferingname) == 0:
        print("networkname: " + networkname)
        print("networkuuid: " + networkuuid)
        print("mysqlHost: " + mysqlHost)
        print("vpcofferingname: " + vpcofferingname)
        print("networkofferingname: " + networkofferingname)
        print("Required parameter not passed!")
        print(help)
        sys.exit()


def exit_script(message):
    print("Fatal Error: %s" % message)
    sys.exit(1)


# Parse arguments
if __name__ == "__main__":
    handleArguments(sys.argv[1:])

# Start time
print("Note: Starting @ %s" % time.strftime("%Y-%m-%d %H:%M"))
start_time = datetime.now()

if DEBUG == 1:
    print("Warning: Debug mode is enabled!")

if DRYRUN == 1:
    print("Warning: dry-run mode is enabled, not running any commands!")

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
    print("DEBUG: MySQL connection successful")
    print(s.conn)

# make credentials file known to our class
c.configProfileName = configProfileName

# Init the CloudStack API
c.initCloudStackAPI()

if not networkuuid:
    networkuuid = c.checkCloudStackName({
        'csname': networkname,
        'csApiCall': 'listNetworks',
        'listAll': 'true',
        'isProjectVm': False
    })

if DEBUG == 1:
    print("API address: " + c.apiurl)
    print("ApiKey: " + c.apikey)
    print("SecretKey: " + c.secretkey)
    print("Username: " + c.username)
    print("Password: " + c.password)

# Check cloudstack IDs
if DEBUG == 1:
    print("Debug: Checking CloudStack IDs of provided input..")
    print("Network UUID: %s" % networkuuid)

# Get Isolated network details
isolated_network = c.listNetworks(networkuuid)[0]
isolated_network_db_id = s.get_network_db_id(networkuuid)

# Pretty Slack messages
c.instance_name = isolated_network.name
c.slack_custom_title = "Network"
c.slack_custom_value = isolated_network.name
c.zone_name = isolated_network.zonename
c.task = "Converting legacy network to VPC tier"

to_slack = True
if DRYRUN == 1:
    to_slack = False

# Pre-flight checks
# 1. Check if network is actually already an VPC tier
if s.check_if_network_is_vpc_tier(isolated_network_db_id):
    message = "Network '%s' is already part of a VPC. Nothing to do!" % isolated_network.name
    c.print_message(message=message, message_type="Note", to_slack=to_slack)
    exit(1)

# 2 Gather VPC / network offering
vpc_offering_db_id = s.get_vpc_offering_id(vpcofferingname)
vpc_tier_offering_db_id = s.get_network_offering_id(networkofferingname)

if DRYRUN:
    message = "Would have migrated classic network '%s' to a VPC!" % isolated_network.name
    c.print_message(message=message, message_type="Note", to_slack=to_slack)
    exit(0)

message = "Starting migration of classic network '%s' to VPC" % isolated_network.name
c.print_message(message=message, message_type="Note", to_slack=to_slack)

# Migration
# 1. Create the new VPC
vpc_db_id = s.create_vpc(isolated_network_db_id, vpc_offering_db_id)

# 2. Fill the vpc service map
s.fill_vpc_service_map(vpc_db_id)

# 3. Update network service map
s.migrate_ntwk_service_map_from_isolated_network_to_vpc(isolated_network_db_id)

# 4. Create network acl from isolated network egress for vpc
egress_network_acl_db_id = s.create_network_acl_for_vpc(vpc_db_id, networkuuid + '-fwrules')

# TODO Think about default deny / default allow
# 5. Fill egress network acl
s.convert_isolated_network_egress_rules_to_network_acl(isolated_network_db_id, egress_network_acl_db_id)

# 6. Update network to become a VPC tier
s.update_isolated_network_to_be_a_vpc_tier(vpc_db_id, egress_network_acl_db_id, vpc_tier_offering_db_id,
                                           isolated_network_db_id)

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

message = "Migration of classic network '%s' to VPC succeeded! Restart+Cleanup needed to complete migration!"\
          % isolated_network.name
c.print_message(message=message, message_type="Note", to_slack=to_slack)
