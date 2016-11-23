#!/bin/bash

bonds="$@"

ERRORS=( )
GOOD=( )

for bond in $bonds; do
    state=$(sudo /bin/ovs-appctl bond/show ${bond})

    if [ -z "${state}" ]; then
        ERRORS+=( "${bond} is missing" )
    fi

    lacp_status=$(echo "${state}" | grep ^lacp_status | cut -f2 -d\ )

    # check slaves
    slave_count=0
    while read slave_state; do
        slave=${slave_state//slave }
        slave=${slave//: *}
        slave_status=${slave_state//* }

        if [ "${slave_status}" == "enabled" ]; then
            ((slave_count++))
            else
                ERRORS+=( "${bond}: ${slave} status ${slave_status}" )
        fi
    done < <(echo "${state}" | grep ^slave)

    if [ "${lacp_status}" == "negotiated" ]; then
        if [ ${slave_count} -ge 2 ]; then
                GOOD+=( "${bond} ${slave_count} slaves enabled" )
            else
            ERRORS+=( "${bond} only ${slave_count} slaves enabled" )
            fi
    else
        ERRORS+=( "${bond} LACP status '${lacp_status}'" )
    fi
done

if [ -z "${ERRORS}" -a -z "${GOOD}" ]; then
    echo "UNKNOWN: no bond found"
    exit 3
elif [ -z "${ERRORS}" ]; then
    echo "OK: ${GOOD}"
    exit 0
else
    echo "CRITICAL: ${ERRORS}"
    exit 2
fi
