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

# Script to create the missing VLANs on a XEN host
# Ferenc Born - fborn@schubergphilis.com

networks=$(xe network-list params=name-label | grep "\ VLAN" | awk -F': ' '{ print $2}')

for network in $networks
do
	if [[ -z $(xe pif-list network-name-label=$network host-name-label=${HOSTNAME} --minimal) ]]; then
		vlan=${network##*-}
		networkuuid=$(xe network-list name-label=$network --minimal)
		pifuuid=$(xe pif-list device=bond0 VLAN=-1 host-name-label=${HOSTNAME} --minimal)
		echo "Note: Creating VLAN $vlan on hypervisor `hostname`"
		xe vlan-create network-uuid=$networkuuid pif-uuid=$pifuuid vlan=$vlan
		result=$?
		if [[ $result != 0 ]]; then
			echo "Error: Creating VLAN $vlan on hypervisor `hostname` failed with exit code $result"
			exit 1
		fi
	fi
done
