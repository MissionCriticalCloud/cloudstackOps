#!/usr/bin/env bash

echo "This is the post_empty script you could customise."

#echo "Downgrading openvswitch RPM to the XenServer default"
#rpm -Uvh http://10.200.10.10/software/xenserver/openvswitch-1.4.6-143.9926.i386.rpm --force --nodeps

echo "Applying patches"
HOST_UUID=$(xe host-list name-label=${HOSTNAME} --minimal)

# Check for 6.5
cat /etc/redhat-release | grep "6.5"
if [ $? -eq 0 ]; then
    SERVICE_PACK_PATCH=XS65ESP1
fi
# Check for 6.2
cat /etc/redhat-release | grep "6.2"
if [ $? -eq 0 ]; then
    SERVICE_PACK_PATCH=XS62ESP1
fi

# First apply SP1
xe patch-list name-label=${SERVICE_PACK_PATCH} params=hosts --minimal | tr ',' '\n' | grep ${HOST_UUID}
if [ $? -eq 0 ]; then
   echo Service Pack ${SERVICE_PACK_PATCH} is already installed, skipping.
else
   echo Installing ${SERVICE_PACK_PATCH}...
   PATCH_UUID=$(xe patch-list name-label=${SERVICE_PACK_PATCH} | grep uuid | sed -e 's/^.*: //g')
   if [ ${PATCH_UUID} ]; then
       xe patch-apply uuid=${PATCH_UUID} host-uuid=${HOST_UUID}
   fi
fi

# Apply any other available patch
XEN_ALL_PATCHES=$(xe patch-list params=name-label --minimal | tr ',' '\n' )
XEN_INSTALLED_PATCHES=$(xe patch-list hosts:contains=${HOST_UUID} params=name-label --minimal | tr ',' '\n' )

for patch in ${XEN_ALL_PATCHES}; do
    echo "Checking patch " ${patch}

    # Check if already included
    echo ${XEN_INSTALLED_PATCHES} | grep ${patch} 2>&1 >/dev/null
    if [ $? -eq 0 ]; then
       echo Patch ${patch} is already installed, skipping.
    else
       echo Installing $patch...
       PATCH_UUID=$(xe patch-list name-label=${patch}| grep uuid | sed -e 's/^.*: //g')
       if [ ${PATCH_UUID} ]; then
           xe patch-apply uuid=${PATCH_UUID} host-uuid=${HOST_UUID}
       fi
    fi
done

echo "Upgrading drivers"
yum -y install bnx2x-* fnic* qla2* glnic* qlge* tg3* hpsa* openvswitch-modules-xen*
yum -y upgrade nicira-ovs-hypervisor-node

echo "Fixing openvswitch installation back to the newest"
yum reinstall openvswitch