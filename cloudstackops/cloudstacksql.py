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

# Class to talk to CloudStack SQL database
# Remi Bergsma - rbergsma@schubergphilis.com

# Import the class we depend on
import uuid

from cloudstackopsbase import *
# Import our dependencies
import mysql.connector
from mysql.connector import errorcode


class CloudStackSQL(CloudStackOpsBase):
    # Init function
    def __init__(self, debug=0, dryrun=0, force=0):
        self.DEBUG = debug
        self.DRYRUN = dryrun
        self.FORCE = force

    # Get all DB's
    def getAllDB(self):
        db = []
        try:
            self.configfile = os.getcwd() + '/config'
            config = ConfigParser.RawConfigParser()
            config.read(self.configfile)
            for each_section in config.sections():
                for item, value in config.items(each_section):
                    if item == 'mysqlhostname':
                        db.append(each_section)
        except:
            print "Error: Tried to read username and password from config file 'config', but failed."
            sys.exit(1)
        return db

    # Connect MySQL Cloud DB
    def connectMySQL(self, mysqlhost, mysqlpassword='', mysqluser='cloud'):

        # Try to lookup password if not supplied
        if not mysqlpassword:
            # Try to read MySQL settings from config file
            try:
                self.configfile = os.getcwd() + '/config'
                config = ConfigParser.RawConfigParser()
                config.read(self.configfile)
                mysqlpassword = config.get(mysqlhost, 'mysqlpassword')
                mysqlhostname = config.get(mysqlhost, 'mysqlhostname')
                mysqluser = config.get(mysqlhost, 'mysqluser')
            except:
                print "Error: Tried to read username and password from config file 'config', but failed."
                print "Error: Make sure there is a section [" + mysqlhost + "] with mysqlpassword=password and " \
                                                                            "mysqluser=user or specify password on the command line."
                sys.exit(1)

            try:
                mysqlport = config.get(mysqlhost, 'mysqlport')
            except:
                mysqlport = 3306

        config = {
            'user': mysqluser,
            'password': mysqlpassword,
            'host': mysqlhostname,
            'database': 'cloud',
            'port': mysqlport,
            'raise_on_warnings': True,
            'autocommit': True
        }

        try:
            conn = mysql.connector.connect(**config)
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                print("Something is wrong with your user name or password")
                return 1
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                print("Database does not exists")
                return 1
            else:
                print(err)
                return 1

        self.conn = conn
        return 0

    # Disconnect MySQL connection
    def disconnectMySQL(self):
        self.conn.close()

    # list HA Workers
    def getHAWorkerData(self, hypervisorName):
        if not self.conn:
            return 1

        if len(hypervisorName) > 0:
            hypervisorNameWhere = " AND host.name LIKE '" + hypervisorName + "%'"
        else:
            hypervisorNameWhere = ""

        cursor = self.conn.cursor()
        cursor.execute("SELECT \
        d.name AS domain, \
        vm.name AS vmname, \
        ha.type, \
        vm.state, \
        ha.created, \
        ha.taken, \
        ha.step, \
        host.name AS hypervisor, \
        ms.name AS mgtname, \
        ha.state \
        FROM cloud.op_ha_work ha \
        LEFT JOIN cloud.mshost ms ON ms.msid=ha.mgmt_server_id \
        LEFT JOIN cloud.vm_instance vm ON vm.id=ha.instance_id \
        LEFT JOIN cloud.host ON host.id=ha.host_id \
        LEFT JOIN cloud.domain d ON vm.domain_id = d.id \
        WHERE ha.created > DATE_SUB(NOW(), INTERVAL 1 DAY) " +
                       hypervisorNameWhere + " \
        GROUP BY vm.name \
        ORDER BY domain,ha.created DESC \
        ;")
        result = cursor.fetchall()
        cursor.close()

        return result

    # list Async jobs
    def getAsyncJobData(self):
        if not self.conn:
            return 1

        cursor = self.conn.cursor()
        cursor.execute("SELECT user.username, \
        account.account_name, \
        instance_name, \
        vm_instance.state AS vm_state, \
        job_cmd, job_dispatcher, async_job.created, \
        mshost.name, async_job.id, related \
        FROM async_job \
        LEFT JOIN user ON user_id = user.id \
        LEFT JOIN account ON async_job.account_id = account.id \
        LEFT JOIN vm_instance ON instance_id = vm_instance.id \
        LEFT JOIN mshost ON job_init_msid = mshost.id \
        WHERE job_result IS NULL;")
        result = cursor.fetchall()
        cursor.close()

        return result

    # list ip adress info
    def getIpAddressData(self, ipaddress):
        if not self.conn:
            return 1

        cursor = self.conn.cursor()
        cursor.execute("SELECT \
        vpc.name, \
        'n/a' AS 'mac_address', \
        user_ip_address.public_ip_address, \
        'n/a' AS 'netmask', \
        'n/a' AS 'broadcast_uri', \
        networks.mode, \
        user_ip_address.state, \
        user_ip_address.allocated AS 'created', \
        'n/a' AS 'vm_instance' \
        FROM cloud.user_ip_address \
        LEFT JOIN vpc ON user_ip_address.vpc_id = vpc.id \
        LEFT JOIN networks ON user_ip_address.source_network_id = networks.id \
        WHERE public_ip_address LIKE '%" + ipaddress + "%' \
        UNION \
        SELECT networks.name, \
        nics.mac_address, \
        nics.ip4_address, \
        nics.netmask, \
        nics.broadcast_uri, \
        nics.mode, \
        nics.state, \
        nics.created, \
        vm_instance.name \
        FROM cloud.nics, cloud.vm_instance, \
        cloud.networks \
        WHERE nics.instance_id = vm_instance.id \
        AND nics.network_id = networks.id \
        AND ip4_address \
        LIKE '%" + ipaddress + "%' \
        AND nics.removed IS NULL;")
        result = cursor.fetchall()
        cursor.close()

        return result

    # list ip adress info
    def getIpAddressDataBridge(self, ipaddress):
        if not self.conn:
            return 1

        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT \
        vm_instance.name, public_ip_address, update_time, networks.name, user_ip_address.state \
        FROM vm_instance \
        JOIN vm_network_map ON vm_network_map.vm_id = vm_instance.id \
        JOIN networks ON networks.id = vm_network_map.network_id \
        JOIN user_ip_address ON networks.id = user_ip_address.network_id \
        WHERE user_ip_address.public_ip_address LIKE '%" + ipaddress + "%' ;")

        result = cursor.fetchall()
        cursor.close()

        return result

    # list ip adress info
    def getIpAddressDataInfra(self, ipaddress):
        if not self.conn:
            return 1

        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT \
        name, \
        nics.vm_type, \
        nics.state, \
        ip4_address, \
        instance_id \
        FROM nics \
        JOIN vm_instance ON vm_instance.id = nics.instance_id \
        WHERE nics.ip4_address LIKE '%" + ipaddress + "%' ;")

        result = cursor.fetchall()
        cursor.close()

        return result

    # list mac adress info
    def getMacAddressData(self, macaddress):
        if not self.conn:
            return 1

        cursor = self.conn.cursor()
        cursor.execute("SELECT networks.name, \
        nics.mac_address, \
        nics.ip4_address, \
        nics.netmask, \
        nics.broadcast_uri, \
        nics.mode, \
        nics.state, \
        nics.created, \
        vm_instance.name \
        FROM cloud.nics, cloud.vm_instance, \
        cloud.networks \
        WHERE nics.instance_id = vm_instance.id \
        AND nics.network_id = networks.id \
        AND mac_address \
        LIKE '%" + macaddress + "%' \
        AND nics.removed IS NULL;")
        result = cursor.fetchall()
        cursor.close()

        result = cursor.fetchall()
        cursor.close()

        return result

    # Return uuid of router volume
    def getRouterRootVolumeUUID(self, routeruuid):
        if not self.conn:
            return 1
        if not routeruuid:
            return 1

        cursor = self.conn.cursor()
        cursor.execute("SELECT volumes.uuid, \
        volumes.name, \
        vm_instance.name \
        FROM volumes, vm_instance \
        WHERE volumes.instance_id = vm_instance.id \
        AND volumes.name LIKE 'ROOT%' \
        AND volumes.state='Ready' \
        AND vm_instance.uuid = '" + routeruuid + "';")
        result = cursor.fetchall()
        cursor.close()

        return result

    # Return volumes that belong to a given instance ID
    def get_volumes_for_instance(self, instancename):
        if not self.conn:
            return 1
        if not instancename:
            return 1

        cursor = self.conn.cursor()
        cursor.execute("SELECT volumes.name, volumes.path, volumes.uuid, volumes.size, vm_instance.state as vmstate, "
                       "volumes.volume_type as voltype" +
                       " FROM vm_instance, volumes" +
                       " WHERE volumes.instance_id = vm_instance.id AND volumes.removed IS NULL AND volumes.state = 'Ready'" +
                       " AND instance_name='" + instancename + "' ORDER by `voltype` DESC;")
        result = cursor.fetchall()
        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        cursor.close()

        return result

    # Return volumes that belong to a given instance ID
    def get_volume_paths_for_instance(self, instancename):
        if not self.conn:
            return 1
        if not instancename:
            return 1

        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT CONCAT('/mnt/', `storage_pool`.`uuid`, '/', `volumes`.`uuid`) AS `path`, `storage_pool`.`name` AS `storage_pool_name`, `storage_pool`.`uuid` AS `storage_pool_uuid`, `volumes`.`name` AS `volume_name`, `volumes`.`uuid` AS `volume_uuid`, `volumes`.`volume_type` AS `volume_type`, `vm_instance`.`state` AS `vm_state`
            FROM `storage_pool`, `vm_instance`, `volumes`
            WHERE
            (
                `volumes`.`instance_id` = `vm_instance`.`id`
                AND
                `volumes`.`removed` IS NULL
                AND
                `volumes`.`state` = 'Ready'
                AND
                `instance_name` ='%s'
                AND
                `storage_pool`.`id` = `volumes`.`pool_id`
            );
           """ % instancename
        )
        result = cursor.fetchall()
        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        cursor.close()

        return result

    # Return volumes that belong to a given instance ID
    def get_volume(self, volumename):
        if not self.conn:
            return 1
        if not volumename:
            return 1

        cursor = self.conn.cursor()
        cursor.execute("SELECT volumes.name, volumes.path, volumes.uuid, volumes.volume_type as voltype" +
                       " FROM volumes" +
                       " WHERE volumes.removed IS NULL AND volumes.state = 'Ready'" +
                       " AND name='" + volumename + "';")
        result = cursor.fetchall()
        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        cursor.close()

        return result

    # Return new template id
    def get_template_id_from_name(self, template_name):
        if not self.conn:
            return False
        if not template_name:
            return False

        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM vm_template WHERE name = '" + template_name + "' AND removed IS NULL LIMIT 1;")
        result = cursor.fetchall()
        if self.DEBUG == 1:
            print cursor.statement
        cursor.close()

        try:
            return result[0][0]
        except:
            return False

    # Return guest_os id
    def get_guest_os_id_from_name(self, guest_os_name):
        if not self.conn:
            return False
        if not guest_os_name:
            return False

        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM guest_os WHERE display_name ='"
                       + guest_os_name + "' AND removed IS NULL LIMIT 1;")
        result = cursor.fetchall()
        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement
        cursor.close()

        try:
            return result[0][0]
        except:
            return False

    # Return storage_pool id
    def get_storage_pool_id_from_name(self, storage_pool_name):
        if not self.conn:
            return False
        if not storage_pool_name:
            return False

        cursor = self.conn.cursor()
        cursor.execute("SELECT storage_pool.id FROM cluster, storage_pool WHERE storage_pool.cluster_id = cluster.id " +
                       " AND storage_pool.name='" + storage_pool_name + "'" +
                       " AND cluster.removed IS NULL" +
                       " AND storage_pool.removed IS NULL LIMIT 1;")
        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        result = cursor.fetchall()
        cursor.close()

        try:
            return result[0][0]
        except:
            return False

    # Return instance_id
    def get_istance_id_from_name(self, instance_name):
        if not self.conn:
            return False
        if not instance_name:
            return False

        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM vm_instance WHERE instance_name ='"
                       + instance_name + "' AND removed IS NULL LIMIT 1;")
        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        result = cursor.fetchall()
        cursor.close()

        try:
            return result[0][0]
        except:
            return False

    # Return instance_id
    def get_affinity_group_id_from_name(self, affinity_group_name):
        if not self.conn:
            return False
        if not affinity_group_name:
            return False

        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM affinity_group WHERE name ='" + affinity_group_name + "';")
        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        result = cursor.fetchall()
        cursor.close()

        try:
            return result[0][0]
        except:
            return False

    # Set instance to KVM in the db
    def update_instance_to_kvm(self, instance_name, vm_template_name, to_storage_pool_name,
                               guest_os_name="Other PV (64-bit)"):
        if self.DRYRUN:
            return True
        if not self.update_instance_from_xenserver_cluster_to_kvm_cluster(instance_name, vm_template_name,
                                                                          guest_os_name):
            print "Error: vm_instance query failed"
            return False
        if not self.update_all_volumes_of_instance_from_xenserver_cluster_to_kvm_cluster(instance_name,
                                                                                         to_storage_pool_name):
            print "Error: volumes query failed"
            return False
        return True

    # Update db vm_instance table
    def update_instance_from_xenserver_cluster_to_kvm_cluster(self, instance_name, vm_template_name, guest_os_name):
        if not self.conn:
            return False
        if not vm_template_name or not guest_os_name or not instance_name:
            return False

        vm_template_id = self.get_template_id_from_name(vm_template_name)
        guest_os_id = self.get_guest_os_id_from_name(guest_os_name)

        if not vm_template_id or not guest_os_id:
            print "Error: Template or GuestOS not found."
            return False

        cursor = self.conn.cursor()

        try:
            cursor.execute("""
               UPDATE vm_instance
               SET last_host_id=NULL, hypervisor_type='KVM', vm_template_id=%s, guest_os_id=%s
               WHERE instance_name=%s LIMIT 1
            """, (vm_template_id, guest_os_id, instance_name))

            if self.DRYRUN == 0:
                self.conn.commit()
            else:
                print "Note: Would have executed: %s" % cursor.statement

            if self.DEBUG == 1:
                print "DEBUG: Executed SQL: " + cursor.statement

        except mysql.connector.Error as err:
            print("Error: MySQL: {}".format(err))
            print cursor.statement
            cursor.close()
            return False

        cursor.close()
        return True

    # Update db volumes table
    def update_all_volumes_of_instance_from_xenserver_cluster_to_kvm_cluster(self, instance_name, to_storage_pool_name):
        if not self.conn:
            return 1
        if not instance_name or not to_storage_pool_name:
            return 1

        instance_id = self.get_istance_id_from_name(instance_name)
        to_storage_pool_id = self.get_storage_pool_id_from_name(to_storage_pool_name)

        cursor = self.conn.cursor()

        try:
            cursor.execute("""
               UPDATE volumes
               SET template_id=NULL, last_pool_id=NULL, format='QCOW2', pool_id=%s
               WHERE instance_id=%s
            """, (to_storage_pool_id, instance_id))

            if self.DRYRUN == 0:
                self.conn.commit()
            else:
                print "Note: Would have executed: %s" % cursor.statement

            if self.DEBUG == 1:
                print "DEBUG: Executed SQL: " + cursor.statement

        except mysql.connector.Error as err:
            print("Error: MySQL: {}".format(err))
            print cursor.statement
            cursor.close()
            return False

        cursor.close()
        return True

    # Update db volumes table
    def update_volume_from_xenserver_cluster_to_kvm_cluster(self, volume_uuid, to_storage_pool_name):
        if not self.conn:
            return 1
        if not volume_uuid or not to_storage_pool_name:
            return 1

        to_storage_pool_id = self.get_storage_pool_id_from_name(to_storage_pool_name)

        cursor = self.conn.cursor()

        try:
            cursor.execute("""
               UPDATE volumes
               SET template_id=NULL, last_pool_id=NULL, format='QCOW2', pool_id=%s
               WHERE uuid=%s
            """, (to_storage_pool_id, volume_uuid))

            if self.DRYRUN == 0:
                self.conn.commit()
            else:
                print "Note: Would have executed: %s" % cursor.statement

            if self.DEBUG == 1:
                print "DEBUG: Executed SQL: " + cursor.statement

        except mysql.connector.Error as err:
            print("Error: MySQL: {}".format(err))
            print cursor.statement
            cursor.close()
            return False

        cursor.close()
        return True

    # Generate revert queries
    def get_current_config(self, instancename):

        if not self.conn:
            return False
        if not instancename:
            return False

        cursor = self.conn.cursor()
        cursor.execute("SELECT vm_instance.id AS instance_id, vm_instance.vm_template_id AS vm_template_id, " +
                       "vm_instance.guest_os_id AS guest_os_id, volumes.pool_id AS pool_id " +
                       "FROM vm_instance, volumes " +
                       "WHERE vm_instance.id = volumes.instance_id " +
                       "AND vm_instance.instance_name='" + instancename + "' " +
                       "AND volumes.removed is NULL "
                       "AND vm_instance.removed is NULL LIMIT 1;")

        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        result = cursor.fetchall()
        cursor.close()

        try:
            return result[0]
        except:
            return False

    # Generate revert queries
    def get_current_volume_config(self, volumeUUID):

        if not self.conn:
            return False
        if not volumeUUID:
            return False

        cursor = self.conn.cursor()
        cursor.execute("SELECT id, pool_id "
                       "FROM volumes " +
                       "WHERE uuid='" + volumeUUID + "' " +
                       "AND removed IS NULL "
                       "LIMIT 1;")

        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        result = cursor.fetchall()
        cursor.close()

        try:
            return result[0]
        except:
            return False

    # Generate revert query
    def generate_revert_query(self, instancename):
        instance_id, vm_template_id, guest_os_id, pool_id = self.get_current_config(instancename)

        revert_sql_instance = "UPDATE vm_instance SET last_host_id=NULL, hypervisor_type='XenServer', " \
                              "vm_template_id=" + str(vm_template_id) + ", guest_os_id=" + str(guest_os_id) + " " \
                                                                                                              "WHERE instance_name='" + str(
            instancename) + "' LIMIT 1;"

        revert_sql_volume = "UPDATE volumes SET template_id=NULL, last_pool_id=NULL, format='VHD', " \
                            "pool_id=" + str(pool_id) + " WHERE instance_id='" + str(instance_id) + "';"

        revert_sql = revert_sql_instance
        revert_sql += "\n" + revert_sql_volume
        print revert_sql
        return revert_sql

    # Generate revert query
    def generate_revert_query_volume(self, volumeUUID):
        volume_id, pool_id = self.get_current_volume_config(volumeUUID)

        revert_sql_volume = "UPDATE volumes SET template_id=NULL, last_pool_id=NULL, format='VHD', " \
                            "pool_id=" + str(pool_id) + " WHERE id='" + str(volume_id) + "';"

        print revert_sql_volume
        return revert_sql_volume

    def get_network_db_id(self, network_uuid):
        if not self.conn:
            return False
        if not network_uuid:
            return False

        cursor = self.conn.cursor()
        cursor.execute('SELECT `id` FROM `networks` WHERE `uuid` = "%s";' % network_uuid)

        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        result = cursor.fetchall()
        cursor.close()

        try:
            return result[0][0]
        except:
            return False

    def create_vpc(self, network_id, vpc_offering_id):
        create_vpc_query = """
INSERT INTO `vpc` 
(
  `uuid`,
  `name`,
  `display_text`,
  `cidr`,
  `vpc_offering_id`,
  `zone_id`,
  `state`,
  `domain_id`,
  `account_id`,
  `network_domain`,
  `removed`,
  `created`,
  `restart_required`,
  `display`,
  `uses_distributed_router`,
  `region_level_vpc`,
  `redundant`,
  `source_nat_list`,
  `syslog_server_list`
)
VALUES
(
  UUID(), -- uuid
  (SELECT `name` FROM `networks` WHERE `id` = %(network_id)s), -- name
  (SELECT `name` FROM `networks` WHERE `id` = %(network_id)s), -- display_text
  (SELECT `cidr` FROM `networks` WHERE `id` = %(network_id)s), -- cidr
  %(vpc_offering_id)s, -- vpc_offering_id
  (SELECT `data_center_id` FROM `networks` WHERE `id` = %(network_id)s), -- zone_id
  'Enabled', -- state
  (SELECT `domain_id` FROM `networks` WHERE `id` = %(network_id)s), -- domain_id
  (SELECT `account_id` FROM `networks` WHERE `id` = %(network_id)s), -- account_id
  (SELECT `network_domain` FROM `networks` WHERE `id` = %(network_id)s), -- network_domain
  NULL, -- removed
  (SELECT `created` FROM `networks` WHERE `id` = %(network_id)s), -- created
  0, -- restart_required
  1, -- display
  0, -- uses_distributed_router
  0, -- region_level_vpc
  (SELECT `redundant` FROM `networks` WHERE `id` = %(network_id)s), -- redundant
  NULL, -- source_nat_list
  NULL -- syslog_server_list
);
""" % dict(network_id=network_id, vpc_offering_id=vpc_offering_id)

        cursor = self.conn.cursor()
        cursor.execute(create_vpc_query)

        vpc_db_id = cursor.getlastrowid()

        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        cursor.close()

        return vpc_db_id

    def fill_vpc_service_map(self, vpc_id):
        fill_vpc_service_map_query = """
INSERT INTO `vpc_service_map`
(
  `vpc_id`,
  `service`,
  `provider`,
  `created`
)
SELECT
  %(vpc_id)s,
  `service`,
  `provider`,
  `created`
FROM `vpc_offering_service_map`  
WHERE `vpc_offering_id` = (SELECT `vpc_offering_id` FROM `vpc` WHERE `id` = %(vpc_id)s);
""" % dict(vpc_id=vpc_id)

        cursor = self.conn.cursor()
        cursor.execute(fill_vpc_service_map_query)

        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        cursor.close()

    def create_network_acl_for_vpc(self, vpc_id, name):
        create_network_acl_query = """
INSERT INTO `network_acl`
(
  `name`,
  `uuid`,
  `vpc_id`,
  `description`,
  `display`
)
VALUES
(
  '%(name)s', -- name
  UUID(), -- uuid
  %(vpc_id)s, -- vpc_id
  '%(name)s', -- description
  1 -- display
);      
""" % dict(vpc_id=vpc_id, name=name)

        cursor = self.conn.cursor()
        cursor.execute(create_network_acl_query)

        network_acl_db_id = cursor.getlastrowid()

        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        cursor.close()

        return network_acl_db_id

    def convert_isolated_network_egress_rules_to_network_acl(self, network_id, network_acl_id):
        # Gather list of rule ids for the isolated network
        query = """
SELECT `id`
FROM `firewall_rules`
WHERE
(
  `Purpose` = 'Firewall' 
  AND
  `traffic_type` = 'Egress'
  AND
  `ip_address_id` IS NULL
  AND
  `network_id` = %(network_id)s
);    
""" % dict(network_id=network_id)

        cursor = self.conn.cursor()
        cursor.execute(query)

        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        isolated_network_egress_firewall_rules = cursor.fetchall()
        cursor.close()

        ids = (rule[0] for rule in isolated_network_egress_firewall_rules)

        self.migrate_firewall_rules_to_network_acl_items(network_acl_id, ids)

    def convert_isolated_network_public_ip_rules_to_network_acl(self, public_ip_db_id, network_acl_id):
        # Gather list of rule ids for the isolated network
        query = """
SELECT `id`
FROM `firewall_rules`
WHERE
(
  `Purpose` = 'Firewall'
  AND
  `traffic_type` = 'Ingress'
  AND
  `ip_address_id` = %(ip_address_id)s
);    
""" % dict(ip_address_id=public_ip_db_id)

        cursor = self.conn.cursor()
        cursor.execute(query)

        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        public_ip_ingress_firewall_rules = cursor.fetchall()
        cursor.close()

        ids = (rule[0] for rule in public_ip_ingress_firewall_rules)

        self.migrate_firewall_rules_to_network_acl_items(network_acl_id, ids)

    def migrate_firewall_rules_to_network_acl_items(self, network_acl_id, firewall_rules_ids):
        query = """
SELECT MAX(`number`)
FROM `network_acl_item`
WHERE
(
  `acl_id` = %(acl_id)s
);

""" % dict(acl_id=network_acl_id)

        cursor = self.conn.cursor()
        cursor.execute(query)
        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        rule_counter = 0

        number = cursor.fetchone()
        if number[0]:
            rule_counter = number[0]

        cursor.close()

        # Convert each rule
        for firewall_rule_id in firewall_rules_ids:
            rule_counter += 1

            query = """
INSERT INTO `network_acl_item`
(
  `uuid`,
  `acl_id`,
  `start_port`,
  `end_port`,
  `state`,
  `protocol`,
  `created`,
  `icmp_code`,
  `icmp_type`,
  `traffic_type`,
  `number`,
  `action`,
  `display`
)
SELECT 
  UUID(), -- uuid
  %(acl_id)s, -- acl_id
  `start_port`,
  `end_port`,
  `state`,
  `protocol`,
  `created`,
  `icmp_code`,
  `icmp_type`,
  `traffic_type`,
  %(number)s, -- number
  'Allow', -- action
  `display`
FROM `firewall_rules`
WHERE
(
  `id` = %(firewall_rule_id)s
);
""" % dict(acl_id=network_acl_id, number=rule_counter, firewall_rule_id=firewall_rule_id)

            cursor = self.conn.cursor()
            cursor.execute(query)

            if self.DEBUG == 1:
                print "DEBUG: Executed SQL: " + cursor.statement

            network_acl_item_db_id = cursor.getlastrowid()

            cursor.close()

            query = """
INSERT INTO `network_acl_item_cidrs`
(
  `network_acl_item_id`,
  `cidr`
)
SELECT
  %(network_acl_item_id)s,
  `source_cidr`
FROM `firewall_rules_cidrs`
WHERE
(
  `firewall_rule_id` = %(firewall_rule_id)s
);
""" % dict(network_acl_item_id=network_acl_item_db_id, firewall_rule_id=firewall_rule_id)

            cursor = self.conn.cursor()
            cursor.execute(query)

            if self.DEBUG == 1:
                print "DEBUG: Executed SQL: " + cursor.statement

            cursor.close()

    def update_isolated_network_to_be_a_vpc_tier(self, vpc_id, network_acl_id, network_offering_id, network_id):
        query = """
UPDATE `networks`
SET
  `vpc_id` = %(vpc_id)s,
  `network_acl_id` = %(network_acl_id)s,
  `network_offering_id` = %(network_offering_id)s
WHERE
(
  `id` = %(network_id)s
);
""" % dict(vpc_id=vpc_id, network_acl_id=network_acl_id, network_offering_id=network_offering_id, network_id=network_id)

        cursor = self.conn.cursor()
        cursor.execute(query)

        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        cursor.close()

    def get_all_ipaddresses_from_network(self, network_id):
        query = """
SELECT `id`, `public_ip_address`
FROM `user_ip_address`
WHERE
(
  `network_id` = %(network_id)s
);
""" % dict(network_id=network_id)

        cursor = self.conn.cursor()
        cursor.execute(query)

        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        ids = cursor.fetchall()

        cursor.close()

        return ids

    def migrate_public_ip_from_isolated_network_to_vpc(self, vpc_id, ip_acl_id, public_ip_id):
        query = """
SELECT `id`
FROM `firewall_rules`
WHERE
(
  `ip_address_id` = %(public_ip_id)s
  AND
  `purpose` IN ('PortForwarding', 'LoadBalancing')
);
""" % dict(public_ip_id=public_ip_id)

        cursor = self.conn.cursor()
        cursor.execute(query)

        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        result = cursor.fetchall()
        cursor.close()

        if len(result) is 0:
            query = """
UPDATE `user_ip_address`
SET
  `vpc_id` = %(vpc_id)s,
  `ip_acl_id` = %(ip_acl_id)s,
  `network_id` = NULL
WHERE
(
  `id` = %(public_ip_id)s
);
""" % dict(vpc_id=vpc_id, ip_acl_id=ip_acl_id, public_ip_id=public_ip_id)
        else:
            query = """
UPDATE `user_ip_address`
SET
  `vpc_id` = %(vpc_id)s,
  `ip_acl_id` = %(ip_acl_id)s
WHERE
(
  `id` = %(public_ip_id)s
);
""" % dict(vpc_id=vpc_id, ip_acl_id=ip_acl_id, public_ip_id=public_ip_id)

        cursor = self.conn.cursor()
        cursor.execute(query)

        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        cursor.close()

    def migrate_routers_from_isolated_network_to_vpc(self, vpc_id, network_id):
        query = """
UPDATE `domain_router`
SET
  `vpc_id` = %(vpc_id)s
WHERE
(
  `id` IN (
  	SELECT `instance_id`
	FROM `nics`
	WHERE
	(
	  `network_id` = %(network_id)s
	  AND
	  `vm_type` = 'DomainRouter'
	)  
  )
);
""" % dict(vpc_id=vpc_id, network_id=network_id)

        cursor = self.conn.cursor()
        cursor.execute(query)

        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        cursor.close()

    def migrate_ntwk_service_map_from_isolated_network_to_vpc(self, network_id):
        query = """
UPDATE `ntwk_service_map`
SET
  `provider` = 'VpcVirtualRouter'
WHERE
(
  `network_id` = %(network_id)s
  AND
  `provider` = 'VirtualRouter'
);
""" % dict(network_id=network_id)

        cursor = self.conn.cursor()
        cursor.execute(query)

        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        cursor.close()

        query = """
UPDATE `ntwk_service_map`
SET
  `service` = 'NetworkACL'
WHERE
(
  `network_id` = %(network_id)s
  AND
  `service` = 'Firewall'
);
""" % dict(network_id=network_id)

        cursor = self.conn.cursor()
        cursor.execute(query)

        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        cursor.close()

    def fix_egress_cidr_allow_all(self, network_acl_id):
        query = """
UPDATE `network_acl_item_cidrs`
SET
  `cidr` = '0.0.0.0/0'
WHERE
(
  `network_acl_item_id` IN
  (
    SELECT `id`
 	FROM `network_acl_item`
	WHERE
	(
	  `acl_id` = %(network_acl_id)s
	  AND
	  `traffic_type` = 'Egress'
	)
  )
);
""" % dict(network_acl_id=network_acl_id)

        cursor = self.conn.cursor()
        cursor.execute(query)

        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        cursor.close()

    def check_if_network_is_vpc_tier(self, network_id):
        query = """
SELECT `vpc_id`
FROM `networks`
WHERE
(
  `id` = %(network_id)s
);
""" % dict(network_id=network_id)

        cursor = self.conn.cursor()
        cursor.execute(query)

        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        result = cursor.fetchone()

        cursor.close()

        if result[0]:
            return True
        else:
            return False

    def get_vpc_offering_id(self, vpc_offering_name):
        query = """
SELECT `id`
FROM `vpc_offerings`
WHERE
(
  `name` = '%(vpc_offering_name)s'
  AND
  `removed` IS NULL
);
""" % dict(vpc_offering_name=vpc_offering_name)

        cursor = self.conn.cursor()
        cursor.execute(query)

        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        result = cursor.fetchall()

        if len(result) is not 1:
            print "Couldn't find vpc offering!"
            print result
            exit(1)

        cursor.close()

        return result[0][0]

    def get_network_offering_id(self, network_offering_name):
        query = """
SELECT `id`
FROM `network_offerings`
WHERE
(
  `name` = '%(network_offering_name)s'
    AND
  `removed` IS NULL
);
""" % dict(network_offering_name=network_offering_name)

        cursor = self.conn.cursor()
        cursor.execute(query)

        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        result = cursor.fetchall()

        if len(result) is not 1:
            print "Couldn't find network offering!"
            print result
            exit(1)

        cursor.close()

        return result[0][0]

    # Update db volumes table
    def kill_jobs_of_instance(self, instance_id):
        if not self.conn:
            return False
        if len(instance_id) == 0:
            print "Error: We have no instance_id passed: %s" % instance_id
            return False

        cursor = self.conn.cursor()

        # Kill Jobs
        try:
            query = "DELETE FROM `async_job` WHERE `instance_id` = %s;" % instance_id
            cursor.execute(query)

            if self.DRYRUN == 0:
                self.conn.commit()
            else:
                print "Note: Would have executed: %s" % cursor.statement

            if self.DEBUG == 1:
                print "DEBUG: Executed SQL: " + cursor.statement

        except mysql.connector.Error as err:
            print("Error: MySQL: {}".format(err))
            print cursor.statement
            cursor.close()
            return False

        try:
            query = "DELETE FROM `vm_work_job` WHERE  `vm_instance_id` = %s;" % instance_id
            cursor.execute(query)

            if self.DRYRUN == 0:
                self.conn.commit()
            else:
                print "Note: Would have executed: %s" % cursor.statement

            if self.DEBUG == 1:
                print "DEBUG: Executed SQL: " + cursor.statement

        except mysql.connector.Error as err:
            print("Error: MySQL: {}".format(err))
            print cursor.statement
            cursor.close()
            return False

        try:
            query = "DELETE FROM `sync_queue` WHERE `sync_objid` = %s;" % instance_id
            cursor.execute(query)

            if self.DRYRUN == 0:
                self.conn.commit()
            else:
                print "Note: Would have executed: %s" % cursor.statement

            if self.DEBUG == 1:
                print "DEBUG: Executed SQL: " + cursor.statement

        except mysql.connector.Error as err:
            print("Error: MySQL: {}".format(err))
            print cursor.statement
            cursor.close()
            return False

        cursor.close()
        return True


    def get_disk_offering_id(self, disk_offering_name):
            query = """
                SELECT id FROM disk_offering_view WHERE removed IS NULL AND domain_name='Cust' AND `name` = '%(disk_offering_name)s';
    """ % dict(disk_offering_name=disk_offering_name)

            cursor = self.conn.cursor()
            cursor.execute(query)

            if self.DEBUG == 1:
                print "DEBUG: Executed SQL: " + cursor.statement

            result = cursor.fetchall()

            if len(result) is not 1:
                print "Couldn't find disk offering!"
                print result
                exit(1)

            cursor.close()

            return result[0][0]

    # Set ZWPS disks to CWPS
    def update_zwps_to_cwps(self, instance_name, disk_offering_name):

        cursor = self.conn.cursor()

        disk_offering_id = self.get_disk_offering_id(disk_offering_name=disk_offering_name)
        instance_id = self.get_istance_id_from_name(instance_name)

        query = """
            UPDATE volumes SET disk_offering_id=%(disk_offering_id)s WHERE volume_type='DATADISK' AND instance_id=%(instance_id)s;
                    """ % dict(disk_offering_id=disk_offering_id, instance_id=instance_id)

        try:
            if self.DRYRUN == 0:
                cursor.execute(query)
                print "Note: Executed: %s" % cursor.statement
            else:
                print "Note: Would have executed: %s" % query
        except mysql.connector.Error as err:
            print("Error: MySQL: {}".format(err))
            print cursor.statement
            cursor.close()
            return False

        cursor.close()
        return True

    # Get size
    def get_volume_size(self, path):
        if not self.conn:
            return 1
        if not path:
            return 1

        cursor = self.conn.cursor()
        cursor.execute("SELECT volumes.name, volumes.path, volumes.uuid, volumes.volume_type as voltype, volumes.size" +
                       " FROM volumes" +
                       " WHERE volumes.removed IS NULL AND volumes.state = 'Ready'" +
                       " AND path='" + path + "';")
        result = cursor.fetchall()
        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        cursor.close()

        return result[0]

   # Set ZWPS disks to CWPS
    def update_volume_size(self, instance_name, path, size):

        cursor = self.conn.cursor()
        instance_id = self.get_istance_id_from_name(instance_name)

        query = """
            UPDATE volumes SET size=%(size)s WHERE path="%(path)s" AND instance_id=%(instance_id)s;
                    """ % dict(size=size, path=path, instance_id=instance_id)

        try:

            if self.DRYRUN == 0:
                cursor.execute(query)
                print "Note: Executed: %s" % cursor.statement
            else:
                print "Note: Would have executed: %s" % query
        except mysql.connector.Error as err:
            print("Error: MySQL: {}".format(err))
            print cursor.statement
            cursor.close()
            return False

        cursor.close()
        return True

    def add_vm_to_affinity_group(self, instance_name, affinity_group_name):
        cursor = self.conn.cursor()
        instance_id = self.get_istance_id_from_name(instance_name=instance_name)
        affinity_group_id = self.get_affinity_group_id_from_name(affinity_group_name=affinity_group_name)

        # Did we get a valid integer response?
        try:
            affinity_group_id = int(affinity_group_id)
        except:
            return False

        query = """
            INSERT IGNORE INTO affinity_group_vm_map (instance_id, affinity_group_id) VALUES (%(instance_id)s, %(affinity_group_id)s);
                    """ % dict(instance_id=instance_id, affinity_group_id=affinity_group_id)

        try:

            if self.DRYRUN == 0:
                cursor.execute(query)
                print "Note: Executed: %s" % cursor.statement
            else:
                print "Note: Would have executed: %s" % query
        except mysql.connector.Error as err:
            print("Error: MySQL: {}".format(err))
            print cursor.statement
            cursor.close()
            return False

        cursor.close()
        return True

    def get_service_offering_id(self, service_offering_name):
        query = """
        SELECT `id`
        FROM `service_offering_view`
        WHERE
        (
          `name` = '%(service_offering_name)s'
          AND
          `removed` IS NULL
          AND `domain_path` = '/Cust/' 
        );
        """ % dict(service_offering_name=service_offering_name)

        cursor = self.conn.cursor()
        cursor.execute(query)

        if self.DEBUG == 1:
            print "DEBUG: Executed SQL: " + cursor.statement

        result = cursor.fetchall()

        if len(result) is not 1:
            print "Couldn't find vpc offering!"
            print result
            exit(1)

        cursor.close()

        return result[0][0]

    # Update db volumes table
    def update_service_offering_of_vm(self, instance_name, service_offering_name):
        if not self.conn:
            return 1
        if not instance_name or not service_offering_name:
            return 1

        instance_id = self.get_istance_id_from_name(instance_name)
        to_service_offering_id = self.get_service_offering_id(service_offering_name)

        cursor = self.conn.cursor()

        try:
            cursor.execute("""
               UPDATE vm_instance
               SET service_offering_id=%s
               WHERE id=%s
               LIMIT 1
            """, (to_service_offering_id, instance_id))

            if self.DRYRUN == 0:
                self.conn.commit()
            else:
                print "Note: Would have executed: %s" % cursor.statement

            if self.DEBUG == 1:
                print "DEBUG: Executed SQL: " + cursor.statement

        except mysql.connector.Error as err:
            print("Error: MySQL: {}".format(err))
            print cursor.statement
            cursor.close()
            return False

        cursor.close()
        return True
