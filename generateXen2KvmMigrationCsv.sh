#!/bin/bash

PROFILE="xxx"
OUTPUT_DIR="output"

cloudmonkey set display table
cloudmonkey set profile $PROFILE

UUIDs=$(cloudmonkey list domains filter=id,name | grep -v id | grep -v '+')

rm -rf $OUTPUT_DIR
mkdir -p $OUTPUT_DIR

cloudmonkey set display csv

IFS=$'\n'
for line in $UUIDs; do
    NAME=$(echo $line | awk '{ print $4 }')
    UUID=$(echo $line | awk '{ print $2 }')

    if [ -z "$NAME" ]; then
        continue
    fi

    echo $NAME
    echo $UUID
    cloudmonkey list virtualmachines listall=true domainid=$UUID hypervisor=XenServer filter=domain,templatename,state,name,created,serviceofferingname > $OUTPUT_DIR/$NAME.csv
done

cloudmonkey set display table
