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
from cloudstackopsbase import *
# Import our dependencies
import mysql.connector
from mysql.connector import errorcode


class CloudStackSQL(CloudStackOpsBase):

    # Connect MySQL Cloud DB
    def connectMySQL(self, mysqlhost, mysqlpassword=''):
        # Try to lookup password if not supplied
        if not mysqlpassword:
            # Try to read MySQL settings from config file
            try:
                self.configfile = os.getcwd() + '/config'
                config = ConfigParser.RawConfigParser()
                config.read(self.configfile)
                mysqlpassword = config.get(mysqlhost, 'mysqlpassword')
            except:
                print "Error: Tried to read password from config file 'config', but failed."
                print "Error: Make sure there is a section [" + mysqlhost + "] with mysqlpassword=password or specify password on the command line."
                sys.exit(1)

        config = {
            'user': 'cloud',
            'password': mysqlpassword,
            'host': mysqlhost,
            'database': 'cloud',
            'raise_on_warnings': True,
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
            hypervisorNameWhere = " AND host.name = '" + hypervisorName + "'"
        else:
            hypervisorNameWhere = ""

        cursor = self.conn.cursor()
        cursor.execute("SELECT vm.name, \
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
        WHERE ha.created > DATE_SUB(NOW(), INTERVAL 1 DAY) " +
                       hypervisorNameWhere + " \
        ORDER BY ha.created desc \
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
        vm_instance.state as vm_state, \
        job_cmd, job_dispatcher, async_job.created, \
        mshost.name, async_job.id, related \
        FROM async_job \
        LEFT JOIN user ON user_id = user.id \
        LEFT JOIN account ON async_job.account_id = account.id \
        LEFT JOIN vm_instance ON instance_id = vm_instance.id \
        LEFT JOIN mshost ON job_init_msid = mshost.id \
        WHERE job_result is null;")
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
        user_ip_address.allocated as 'created', \
        'n/a' AS 'vm_instance' \
        FROM cloud.user_ip_address \
        LEFT JOIN vpc ON user_ip_address.vpc_id = vpc.id \
        LEFT JOIN networks ON user_ip_address.source_network_id = networks.id \
        WHERE public_ip_address like '%" + ipaddress  + "%' \
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
        LIKE '%" + ipaddress  + "%' \
        AND nics.removed is null;")
        result = cursor.fetchall()
        cursor.close()

        return result

    # get uuid of router volume
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
        AND volumes.name like 'ROOT%' \
        AND volumes.state='Ready' \
        AND vm_instance.uuid = '" + routeruuid + "';")
        result = cursor.fetchall()
        cursor.close()

        return result
