#!/bin/bash

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

# Script to clean old DHCP ip address config
# Remi Bergsma - rbergsma@schubergphilis.com

# Config files
DHCP_LEASES="/var/lib/misc/dnsmasq.leases"
DHCP_HOSTS="/etc/dhcphosts.txt"
HOSTS="/etc/hosts"

# Ip address is required argument
ipv4=$1
if [ ! $ipv4 ]
then
  echo "Usage: $0 1.2.3.4 [0|1]"
  echo "first arg: ip address, second force no/yes"
  exit 1
fi

# Be friendly, or use force
FORCE=$2
if [ ! $FORCE ]
then
  FORCE=0
fi

# Debug info
echo "Cleaning $ipv4, force=$FORCE"

# Try to find mac address and hostname
MAC=$(grep $ipv4 $DHCP_LEASES | awk '{print $2}')
HOST=$(grep $ipv4 $DHCP_HOSTS | cut -d, -f4)

# Find mac address, alternative version
if [ ! $MAC ]
then
  MAC=$(grep $ipv4 $DHCP_HOSTS | cut -d, -f1)
fi

# Need some force
if [ $FORCE -eq 1 ]
then
  # Clean ip address
  echo "Forcing removal of $ipv4 from $DHCP_HOSTS"
  sed -i  /$ipv4,/d $DHCP_HOSTS

  # Clean hosts file
  echo "Forcing removal of $ipv4 from $HOSTS"
  sed -i  /"$ipv4 "/d $HOSTS

  # Clean old mac
  if [ $MAC ]
  then
    echo "Forcing removal of $MAC from $DHCP_HOSTS"
    sed -i  /$MAC/d $DHCP_HOSTS
  fi
  exit 0
fi

# No mac found
echo $MAC
if [ ! $MAC ]
then
  echo "Error: Could not find Mac address in $DHCP_LEASES"
  exit 1
fi

echo $HOST
if [ ! $HOST ]
then
  echo "Error: Could not find hostname in $DHCP_HOSTS"
  exit 1
fi

# Run the clean script with its required arguments
echo "Running /opt/cloud/bin/edithosts.sh -m $MAC -4 $ipv4 -h $HOST to clean it up. If it does not work, run with force parameter:"
echo "Force like this: $0 $ipv4 1"
/opt/cloud/bin/edithosts.sh -m $MAC -4 $ipv4 -h $HOST

