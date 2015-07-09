CloudStackOps
===============

Collection of scripts that make operating a CloudStack cloud easier :-).

This collection of scripts was written to automate operating the Schuberg Philis Mission Critical Cloud, which is built on top of CloudStack. It consists of handy scripts when you're working with CloudStack on a day-to-day basis.

API Credentials
---------------
To talk to the CloudStack API, you need to configure your root admin API keys. You can either configure them in the config file `config`, or tell the script which CloudMonkey profile to use by using the `--config-profile` or `-c` command line argument.

CloudMonkey is **NOT** used to execute the API calls, it just **uses its config file** since many of us have this already setup and it makes life easier.

Command line arguments
----------------------
Using arguments you specify on the command line, you can control the behaviour of the scripts. When no arguments are specified, these scripts will display usage. So, it is safe to run them without arguments to learn what options are available.

Each of the command line arguments has a long version (prefixed by double-dash), like `--domain` and a shorter one (prefixed with one dash), like `-d`. You can use either method, or mix them.

DRY-run and DEBUG modes
-----------------------
All scripts run in DRY-run mode by default. This means it will tell you what it wants to do, but that's all. If you're OK with it, run it again with the `--exec` parameter specified. It will then really execute the API calls and change stuff. When using scripts that only show listings, you do not need the `--exec` parameter as nothing would change by just listing information anyway.

At any time, add `--debug` as a parameter and the script will add some useful debug info.

E-mail notifications
--------------------
All scripts that do stuff that impacts users, will lookup an e-mailadres in CloudStack, and send an e-mail notification when maintenance starts and completes. An example is the `upgradeRouterVM.py` that you use to upgrade a router vm to a new templete, for example after an CloudStack upgrade.

Please be sure to edit the `config` file, to edit the e-mail settings before sending e-mail.

If something goes wrong, a notification is e-mailed to  the `errors-to` e-mail address in the `config` file.

Getting started
===

1. Setup config file
----
An example file `config.sample` is provided as a starting point. Copy the file to start:

`cp -pr config.sample config`

Next, have a look at the config parameters. Example config:

```
# Config file for CloudStack Operations scripts

[cloudstackOps]
organization = The Iaas Team 

[mail]
smtpserver = localhost
mail_from = cloudstackOps@example.com
errors_to = cloudstackOps@example.com

[config]
username = admin
apikey = whMTYFZh3n7C4M8VCSpwEhpqZjYkzhYTufcpaLPH9hInYGTx4fOnrJ3dgL-3AZC_STMBUeTFQgqlETPEile4_A
url = http://127.0.0.1:8080/client/api
expires = 600
secretkey = 9Z0S5-ryeoCworyp2x_tuhw5E4bAJ4JTRrpNaftTiAl488q5rvUt8_pG7LxAeg3m_VY-AafXQj-tVhkn9tFv1Q
timeout = 3600
password = password

[mysqlservername]
mysqlpassword=password
````

Again, if you use CloudMonkey you can ommit the `[config]` part. If you like, you can add multiple sections like `[devcloud]` and `[prodcloud]` and refer to them with the `-c` flag (like you can do with the CloudMonkey config file, too.

A given profile is first looked up in the CloudMonkey config file, then in the local config file. If both exist, CloudMonkey profile is used.

Remember: you need **root** API credentials to use most scripts.

The MySQL part is used for scripts that query the database. You can specify the mysql server on the command line and specify the password in the config file, using a section with the same name. Alternatively, you can also specify the password on the command line (not recommended).


2. Setup Marvin
---
To talk to the CloudStack API, these scripts use the `Marvin` Python library that comes with `Apache CloudStack`. Unfortunately, Marvin has changed quite a few times during the development of these scripts. Without backwards compatibility that is. Therefore, use the one in this repository and you're fine. Support for the latest version is being worked on, but that takes some time. You can setup an virtual environment (see below) to use multiple versions at the same time.

Install the `tar.gz` from this repo using `pip`

  `pip install -Iv marvin/Marvin-0.1.0.tar.gz`


3. Optional: Python virtual environment (non-root):
---------------
Especially when you are using different versions of Marvin or other packages, a virtual environment is handy. It also does not require root privileges to install.

Make sure you have a system with python including virtualenv support. Install by running:

`sudo yum install python-virtualenv`

* Make a python virtual environment

  `virtualenv ~/python_cloud`

* When working with the scripts activate this virtual env

  `source ~/python_cloud/bin/activate`


* install marvin python cloudstack library within the virtual env

  `pip install -Iv marvin/Marvin-0.1.0.tar.gz`

* Call scripts with `python` instead of `./`, example:

  `python listVirtualMachines.py --oncluster CLUSTER-3`


4. Dependencies
------------
Install `clint` to display colors on the terminal.

`pip install -Iv clint`

You also need `pretty table`.

`pip install -Iv prettytable`


Tips
----
* Always run in `DRY-mode` first, so you get an idea what will happen.
* Always run the commands in `screen` (so it keeps running when your connection gets lost)


Using the provided scripts
=========
For each script included, the use-case and usage examples are provided below.


Display overview of VMs / used capacity
--------------------------------------
This script lists all instances and their consumed capacity. You can limit it to only display instances or only routers, filter on domain name, project name, a keyword, or a combination. At the bottom, a summary is displayed with the number of VMs, the total used disk space, and the total allocated RAM.

This script has two main use cases: to display an overview and to be used to make a selection and then pipe it to the next script. See section about Batch processing for more info.

For usage, run:
`./listVirtualMachines.py`

**Examples:**

* To list all VMs on cluser with name 'CLUSTER-2':
  `./listVirtualMachines.py --oncluster CLUSTER-2`

* To list all VMs on POD with name 'POD-2':
  `./listVirtualMachines.py --pod POD-2`

* To list all VMs on cluser with name 'CLUSTER-2', but only from domain 'domainname':
  `./listVirtualMachines.py --oncluster CLUSTER-2 --domain domainname`

* To list all VMs on cluser with name 'CLUSTER-2', but only from domain 'domainname', filter on 'keyword':
  `./listVirtualMachines.py --oncluster CLUSTER-2 --domain domainname --filter keyword`

* To list all VMs on cluser with name 'CLUSTER-2', filter on 'keyword':
  `./listVirtualMachines.py --oncluster CLUSTER-2 --filter keyword`

* To list all project VMs on cluser with name 'CLUSTER-2':
  `./listVirtualMachines.py --oncluster CLUSTER-2 --is-projectvm`

* To list all project VMs on cluser with name 'CLUSTER-2' where projectname is 'linuxbase':
  `./listVirtualMachines.py --oncluster CLUSTER-2 --project linuxbase`

* To list all project VMs on cluser with name 'CLUSTER-2', filter on 'keyword':
  `./listVirtualMachines.py --oncluster CLUSTER-2 --filter keyword`

* To list all VMs on cluser with name 'CLUSTER-1', and specify a config profile to use:
  `./listVirtualMachines.py --config-profile config_cloud_admin --oncluster CLUSTER-2`

* To list the capacity used in zone 'ZONE-1':
  `./listVirtualMachines.py --zone ZONE-1 --summary`

* To list the capacity used in zone 'ZONE-1' by domain 'domainname':
  `./listVirtualMachines.py --zone ZONE-1 --domainname domain --summary`

* To list the VMs for a domain with non-admin credentials:
  `./listVirtualMachines.py --non-admin-credentials --domain domainname`

* To list the VMs for all domains except the domain called 'domainname':
  `./listVirtualMachines.py --ignore-domain domainname`

* To list the VMs for all domains except the specified domain names:
  `./listVirtualMachines.py --ignore-domain domainnamei1,domainname2,domainname3`

Working with routers:

* To list the router VMs on on cluser with name 'CLUSTER-2':
  `./listVirtualMachines.py --oncluster CLUSTER-2 --only-routers`

* To list the router VMs on on cluser with name 'CLUSTER-2' that have exactly 2 nics:
  `./listVirtualMachines.py --oncluster CLUSTER-2 --only-routers --router-nic-count 2`

* To list the router VMs on on cluser with name 'CLUSTER-2' that have more than 3 nics:
  `./listVirtualMachines.py --oncluster CLUSTER-2 --only-routers --router-nic-count 3 --nic-count-is-minumum`

* To list the router VMs on on cluser with name 'CLUSTER-2' that have 3 or less nics:
  `./listVirtualMachines.py --oncluster CLUSTER-2 --only-routers --router-nic-count 3 --nic-count-is-maximum`

* To list the router VMs on on cluser with name 'CLUSTER-2' that require a systemvm template upgrade:
  `./listVirtualMachines.py --oncluster CLUSTER-2 --only-routers-to-be-upgraded`

Tips:

* If you want to display instances only, use the `--no-routers` switch.

* If you want to display routers only, use the `--only-routers` switch.


Migrate a Virtual Machine
-------------------------
This script will migrate a given VM to the cluster specified. The vm will be shut down, and the user is informed by e-mail. We use this to migrate between old and new clusters.

For usage, run:
`./migrateVirtualMachine.py`

**Examples:**

* To migrate a VM with instance-id 'i-123-45678-VM' to cluster 'CLUSTER-2':
  `./migrateVirtualMachine.py --instance-name i-123-45678-VM --tocluster CLUSTER-2 --exec`

* To migrate a VM with instance-id 'i-123-45678-VM' to cluster 'CLUSTER-2' in DRY-run mode:
  `./migrateVirtualMachine.py --instance-name i-123-45678-VM --tocluster CLUSTER-2`

* To migrate a VM with instance-id 'i-123-45678-VM' to cluster 'CLUSTER-2' and belongs to a project:
  `./migrateVirtualMachine.py --instance-name i-123-45678-VM --tocluster CLUSTER-2 --exec --is-projectvm`

*Tip: We recommend using instance names instead of hostnames. When a hostname is not unique, the script will refuse to operate.*

* To migrate a VM with name 'server001' to cluster 'CLUSTER-2':
  `./migrateVirtualMachine.py --vmname server001 --tocluster CLUSTER-2 --exec`

Migrate all Virtual Machines in a domain
----------------------------------------
There used to be a separate script for this, but that has been depricated. Instead, you can use `./listVirtualMachine.py` and pipe its output to `./migrateVirtualMachine.py`. This allows for more flexability and removes duplicate code.

Just play with `./listVirtualMachine.py` to get the desired list of VMs, then pipe it through `egrep` and `awk` to generate the migrate commands and finally feed it to `sh` for execution.

**Example:**
* Migrate all VMs in domain 'domainname' to cluster 'CLUSTER-2'
` ./listVirtualMachines.py -d domainname |`
`egrep "i\-(.*)\-VM" |`
`cut -d\| -f6 |`
`awk {'print "./migrateVirtualMachine.py --instance " $1 " --tocluster CLUSTER-2" '} | sh`

When you are sure it works as expected, add `--exec` and all VMs will be migrated sequentially.

Migrate offline volumes
-----------------------
This script migrate all *offline* volumes from one storage pool to another. An offline volume is a volume that is currently not attached to a running vm. It is mainly useful to *empty* a cluster's storage pool so you can decommision it.

In DRY-RUN mode, it will display a nice table of what will be migrated.

For usage, run:
`./migrateOfflineVolumes.py`

**Examples:**
* To display which offline volumes can be migrated from CLUSTER-6 to CLUSTER-12:
`./migrateOfflineVolumes.py --fromcluster CLUSTER-6 --tocluster CLUSTER-12`

* To migrate offline volumes from CLUSTER-6 to CLUSTER-12:
`./migrateOfflineVolumes.py --fromcluster CLUSTER-6 --tocluster CLUSTER-12 --exec`

Upgrade a router VM
--------------------
This script will upgrade a router to a new systemVM template. CloudStack will destroy it and re-create it using the same instance-id when you just reboot it. This script works on CloudStack 4.3 and above, because it uses the `requiresUpgrade` flag.

The script is most powerful when used in combination with the `listVirtualMachines.py` script and the `--only-routers-to-be-upgraded` flag. See Batch processing section below for an example.

When a router does not need an update, the script will do nothing.

For usage, run:
`./upgradeRouterVM.py`

**Examples:**
* To upgrade a router VM:
`./upgradeRouterVM.py --routerinstance-name r-12345-VM --exec`

* To upgrade a router VM that belongs to a project:
`./upgradeRouterVM.py --routerinstance-name r-12345-VM --is-projectrouter --exec`

Update a hosts hosttags
-----------------------
This script will update the hosttags of a given host. You can eiter add a new hosttag or replace all tags with new ones.

For usage, run:
`./updateHostTags.py`

**Examples:**
* To add a tag 'new-tag':
`./updateHostTags.py --hostname hypervisor01 --tags new-tag --exec`

* To replace all tags with a new tag 'new-tag':
`./updateHostTags.py --hostname hypervisor01 --tags new-tag --replace --exec`

* To replace all tags with new tags 'new-tag,new-tag-2':
`./updateHostTags.py --hostname hypervisor01 --tags new-tag,new-tag-2 --replace --exec`

* To remove all tags:
`./updateHostTags.py --hostname hypervisor01 --tags ' ' --replace --exec`

Manage a cluster
-----------------
These scripts allow you to set the Allocation- and Managed state. This is handy when you want to patch a cluster. Currently only XenServer is supported.

You can see the status of the cluster, inclusing its hosts. Also, it's easy to see who the poolmaster is.

For usage, run:
`./clusterMaintenance.py`

**Examples:**

* To show an overview of a cluster:
`./clusterMaintenance.py --clustername cluster001`

* To set the cluster in Unmanage state: (As a result, all hosts get disconnected.)
`./clusterMaintenance.py --clustername cluster001 --managedstate Unmanaged --exec`

* To set it to manage, run:
`./clusterMaintenance.py --clustername cluster001 --managedstate Managed --exec`

* To disable a cluster:
`./clusterMaintenance.py --clustername cluster001 --allocationstate Disabled --exec`

* To enable it again:
`./clusterMaintenance.py --clustername cluster001 --allocationstate Enabled --exec` 


Rolling reboot of XenServer cluster
------------------------------------
The purpose of this script is to reboot all hypervisors in a XenServer cluster (aka pool) without impacting the uptime of the VMs running on the cluster. This requires a N+1 situation, where one hypervisor can be empty (this is a wise configuration anyway). The script will start with the poolmaster, live migrate all VMs to other hypervisors and then reboot. When it comes back, one-by-one all other hypervisors will be rebooted and VMs are live migrated around.

Using the --prepare flag, some pre-work is done: ejecting CDs, faking XenTools and pushing some scripts.

The script requires the following PIP modules: Marvin, clint, fabric.

Overview of what it does:

This script will:
  - Set the specified cluster to unmanage in CloudStack
  - Turn OFF XenServer poolHA for the specified cluster
  - For any hypervisor it will do this (poolmaster first):
      - put it to Disabled aka Maintenance in XenServer
      - live migrate all VMs off of it using XenServer evacuate command
      - when empty, it will reboot the hypervisor
      - will wait for it to come back online (checks SSH connection)
      - set the hypervisor to Enabled in XenServer
      - continues to the next hypervisor
  - When the rebooting is done, it enables XenServer poolHA again for the specified cluster
  - Finally, it sets the specified cluster to Managed again in CloudStack
  - CloudStack will update its admin according to the new situation
Then the reboot cyclus for the specified cluster is done!
 
To kick it off, run with the --exec flag.

For usage, run:
`./xenserver_rolling_reboot.py`

**Examples:**

* To display the above help message for 'CLUSTER-1':
  `./xenserver_rolling_reboot.py --clustername CLUSTER-1`

* To prepare the rolling reboot for 'CLUSTER-1':
  `./xenserver_rolling_reboot.py --clustername CLUSTER-1 --prepare`

* To start the rolling reboot for 'CLUSTER-1':
  `./xenserver_rolling_reboot.py --clustername CLUSTER-1 --exec`

* To start the rolling reboot for 'CLUSTER-1' and use 6 threads (instead of the default 5):
  `./xenserver_rolling_reboot.py --clustername CLUSTER-1 --threads 6 --exec`

* To start the rolling reboot for 'CLUSTER-1' but skip the host called 'host1':
  `./xenserver_rolling_reboot.py --clustername CLUSTER-1 --ignore-hosts host1 --exec`


Display the CloudStack HA-Worker table
--------------------------------------
This script lists all entries in the HA-Worker table. This is useful when a hypervisor failed and you need to know the impact (to send out a notification e-mail to customers for example).

The hostname of the MySQL server needs to be provided as an argument. The password for the *cloud* user is optional. When it is not supplied, it will try looking it up in the 'config' config file. You need to make a section with the hostname, and mysqlpassword=password.

For usage, run:
`./listHAWorkers.py`

**Examples:**

* To display the HA-worker table for a CloudStack instance using MySQL server 'mysql001':
  `./listHAWorkers.py --mysqlserver mysql001`

* To display the HA-worker table for a CloudStack instance using MySQL server 'mysql001' and specify password 'passwd':
  `./listHAWorkers.py --mysqlserver mysql001 --mysqlpassword passwd`

* To display only records about 'hypevisor001':
  `./listHAWorkers.py --mysqlserver mysql001 --hypervisor-name hypevisor001`

* To display only records about 'hypevisor001' of VMs that are currently non running:
  `./listHAWorkers.py --mysqlserver mysql001 --hypervisor-name hypevisor001 --non-running`

* To display only records about a VMs with a certain name:
  `./listHAWorkers.py --mysqlserver mysql001 --name-filter testvm`

* Generate a plain table:
  `./listHAWorkers.py --mysqlserver mysql001 --hypervisor-name hypevisor001 --plain-display`

If you want to e-mail a list of vm's that were running on a hypervisor, use:
  `./listHAWorkers.py --mysqlserver mysql001 --hypervisor-name hypevisor001 --plain-display | awk {'print $1'}`


Batch / Bulk processing
----------
Most scripts do only a single operation, like migrating one instance. Combined with the `./listVirtualMachines.py` script, you can create powerful workflows.

This selects all routers on 'CLUSTER-3' that have 2 nics, and upgrade those:

```
./listVirtualMachines.py -c config_cloud_admin --oncluster CLUSTER-3 --only-routers-to-be-upgraded --router-nic-count=2 |\
grep -E '[r]\-(.*)\-VM' | cut -d\| -f6 | awk {'print "./upgradeRouterVM.py -r " $1 '} | sh
```

You could also use the output from a CloudMonkey select, straight to one of the scripts. Like this when using table display:

```
cloudmonkey list clusters filter=name |\
tr -d '|' |\
tr -d '+' |\
grep -v name |\
grep -v "\-\-" |\
grep -v count |\
grep -v host |\
grep -v cluster |\
tr -d ' ' |\
awk {'print "./listVirtualMachines.py --oncluster " $1 '} | sh
```

This will execute the `./listVirtualMachines.py` script for each result of the `cloudmonkey` call.

Note: for this to work, you need to disable colors in cloudmonkey:

`cloudmonkey set color false`

Feature templates
------------------
At Schuberg Philis, we build weekly snapshots of several images we upload. We want these to be featured, and after 4 weeks to be deleted. This script takes care of that process.

Our builds have names like m2015-03 or w2015-10 referring to weekly/monthly builds and the week/month number.

For usage, run:
`./featureTemplates.py`

**Examples:**

* Display what would be (un)featured and deleted:
  `./featureTemplates.py -c configname`

* Execute it:
`./featureTemplates.py -c configname --exec`

This script is work in progress, as it currently only supports XenServer.

Report Accounts
----------------
At Schuberg Philis audit and control is important. For that reason we send overviews of active admin accounts on a montly basis to the Teams. This script can display and email such a report.

For usage, run:
`./featureTemplates.py`

**Examples:**

* Display report on screen:
  `./reportAccounts.py -c configname`

* Send report by e-mail to each account's email address:
  `./reportAccounts.py -c configname --display email --exec`


Experimental and advanced stuff
=========================
The below scripts use certain hacks or are for specific use cases. Feel free to use them, but be warned you may need to tweak them to get them to work. This is not for the ordinary or unexperienced user.

Put a hypervisor in Maintenance mode
------------------------------------
This script will put a XenServer hypervisor in maintenance mode and is also able to cancel it. It makes sure only one host is in maintenance at the same time.

In theory, all you have to do is use the `prepareHostForMaintenance()` API call. In practice, we learned that this will sometimes fail with a resourcestate `ErrorInMaintenance` or simply gets stuck in `PreparForMaintenance` state. 

Another issue we had was when CloudStack and XenServer would disagree on the available resources. That's why we came up with a different approach. We look for all vm's running, migrate the away using separate calls and finally put the host in maintenance. If that does not work, we call XAPI to migrate it anyway. Our goal is to automatically empty a hypervisor to do automated maintenance without user impact. We used it to automatically patch XenServers, including reboots without downtime for the user.

In DRY-RUN mode, a similation will be done of a manual migration of all vm's. This allows you to spot problems before-hand. 

For usage, run:
`./hypervisorMaintenance.py`

**Examples:**

* To see what will happen when you would put host `hypervisor001` in maintenance run:
`./hypervisorMaintenance.py --hostname hypervisor001`

* To have more than one hypervisor in maintenance use `--force` flag:
`./hypervisorMaintenance.py --hostname hypervisor001 --force`

* To put host `hypervisor001` in maintenance run:
`./hypervisorMaintenance.py --hostname hypervisor001 --exec`

* To cancel maintenance for `hypervisor001` run:
`./hypervisorMaintenance.py --hostname hypervisor001 --exec --cancel-maintenance`


Migrate a Virtual Router (SQL)
------------------------------
This script will *migrate* the specified router VM to another cluster in the same zone. Be warned, it's a bit of a hack helped us migrate hundreds of routers to new clusters.

Please note: There is *no supported* way in CloudStack to move routers around, other than live-migrating them between the same cluster. For live-migration between clusters to work, both clusters need access to both primary storages and that is not the case in our setup.

Another way is to destroy the router, and when a new VM is started a new router will also be created. This wasn't the way we wanted it wo work, as it would cause too much down time and also a lot of trouble with capacity limits etc. 

We needed this, because we wanted to move from old to new clusters. We came up with a new way:

**Requirements**

1. Put the cluster that the router VM is currently running on in Disabled state (aka the old cluster)
2. Make sure that any host and storage tags that are defined in the router VM's service offering, are removed from the current cluster's hypervisors

**How does it work?**

A router VM has only one disk, and this disk is always called "ROOT-" followed by an identifier. This identifier is the same as in the router VM's instance name. So, r-1234-VM has a disk called ROOT-1234.

Unfortunately the CloudStack API does not return any results when calling listVolues() with a name like ROOT-1234. As a work-around, we query the CloudStack database and look for the ROOT volume's UUID. Then, it is possible to call the migrateVolume() API with the router VM's ROOT volume (using it's UUID).

This script will:

1. Stop the router
2. Migrate the ROOT volume of the router
3. Start the router

This usually takes ~3 minutes or less and if you have a redundant setup, you won't notice as the router will fail-over.

It will also send e-mail notifications to inform the user.

**Checks**

To be sure it all works as expected a lot of checks are done:
- Redundant routers will not end up on the same cluster
- If a redundant router's peer router is in FAULT state (and thus a fail-over would fail) the script will not do the migration
- Make sure the current cluster is Disabled and any tags are removed
- Make sure the destination cluster has the required host and storags tags as defined in the Service Offering
 
When you do not specify the destination cluster, a random cluster within the same zone will be selected, that has the required tags, is in state 'Enabled' and is not the same cluster as the router's peer.

**Connecting to the database**

You need to specify the MySQL server and optionally the 'cloud' user's password. If not specified, the script tries to look up the password using the config file 'config'. Make a section with the name of the mysql server and specify mysqlpassword=password. See config.sample.

For usage, run:
`./migrateRouterVM.py`

**Examples:**

* To migrate a router VM with instance-id 'r-1234-VM' in DRY-RUN mode:
  `./migrateRouterVM.py --mysqlserver mysqlserver01 --routerinstance-name r-1234-VM`

* To migrate a router VM with instance-id 'r-1234-VM':
  `./migrateRouterVM.py --mysqlserver mysqlserver01 --routerinstance-name r-1234-VM --exec`

* To migrate a router VM with instance-id 'r-1234-VM' to cluster 'CLUSTER-2':
  `./migrateRouterVM.py --mysqlserver mysqlserver01 --routerinstance-name r-1234-VM --tocluster CLUSTER-2 --exec`

* To migrate a router VM with instance-id 'r-1234-VM':
  `./migrateRouterVM.py --mysqlserver mysqlserver01 --mysqlpassword test123 --routerinstance-name r-1234-VM --exec`


List running Async jobs (SQL)
-----------------------------
Restarting CloudStack when migrations are ongoing or snapshots are being made is not wise. This script shows what jobs are running so you can see if restarting now is OK. It's not 100% safe, but the best guestimate we currently have.

For usage, run:
`./listRunningJobs.py`

**Examples:**

* To list running jobs of a Cloud that uses 'mysqlserver01' as its MySQL host:
  `./listRunningJobs.py --mysqlserver mysqlserver01`


Who is using a given ip address (SQL)
---------------------------------
This is a script that looks up a given ip address and shows who uses it. Handy for abuse handling.

For usage, run:
`./whoHasThisIp.py`

**Examples:**

* Look who uses 1.2.3.4 address:
  `./whoHasThisIp.py --mysqlserver mysqlserver01 --ip-address 1.2.3.4`

* Look for ip addresses that have match '10.20.':
  `./whoHasThisIp.py --mysqlserver mysqlserver01 --ip-address 10.20.`


Clean DHCP ip addresses
------------------------
Script to clean an old ip address that is still left behind on the (VPC) router. It can use the `edit_hosts.sh` script (that lives on the router VM), but you don't have to manually lookup hostname and mac-address.

Make sure you copy this script to the router VM, give it exec permission `chmod 755 cleanDHCPipaddress.sh` and then run it to clean the ip addresses.

* To clean an address using the provided 'edit_hosts.sh' scipt:
`./cleanDHCPipaddress.sh 1.2.3.4`

* If it's in a weird state, use force to clean as much as possible on its own:
`./cleanDHCPipaddress.sh 1.2.3.4 1`


Bugs
=====
The scripts have been well tested during migrations, but there could still be bugs (in handling unexpected conditions for example). If you encounter problems, please open an issue.
