#!/bin/bash

ZONE=$1
VMNAME=$2

cloudmonkey set display table

HOSTNAME=$(cloudmonkey -p $ZONE list virtualmachines hypervisor=XenServer name=$VMNAME listall=true filter=hostname | grep -i mccp | awk '{ print $2 }')

if [ -z "$HOSTNAME" ]
then
      # Couldn't find VM / host
      exit 1
fi

PODNAME=$(cloudmonkey -p $ZONE list hosts name=$HOSTNAME filter=podname | grep -i mccp | awk '{ print $2 }')

if [ "$ZONE" == "admin-nl1" ]; then
  if echo $PODNAME | grep -q -i SBP; then
    echo "./migrateVirtualMachineFromXenServerToKVM.py -c $ZONE -t mccppod052-cs01 -s $ZONE --helper-scripts-path /home/mcc_stenley/shared/cosmic/xen2kvm/ -i $VMNAME --exec"
  else
    echo "./migrateVirtualMachineFromXenServerToKVM.py -c $ZONE -t mccppod062-cs01 -s $ZONE --helper-scripts-path /home/mcc_stenley/shared/cosmic/xen2kvm/ -i $VMNAME --exec"
  fi
elif [ "$ZONE" == "nl1" ]; then
  if echo $PODNAME | grep -q -i SBP; then
    echo "./migrateVirtualMachineFromXenServerToKVM.py -c $ZONE -t mccppod053-cs01 -s $ZONE --helper-scripts-path /home/mcc_stenley/shared/cosmic/xen2kvm/ -i $VMNAME --exec"
  else
    echo "./migrateVirtualMachineFromXenServerToKVM.py -c $ZONE -t mccppod063-cs01 -s $ZONE --helper-scripts-path /home/mcc_stenley/shared/cosmic/xen2kvm/ -i $VMNAME --exec"
  fi
fi
