#!/bin/bash

if [ $# -lt 3 ]; then
    echo "Usage: $(basename $0) <zone> <from-hv> <to-hv>"
    exit 1
fi

CLOUD=$1
FROM_HOST=$2
TO_HOST=$3

cloudmonkey set display default

SUCCESS_RETURN='0'
FAILURE=0

FROM_HOST_ID=$(cloudmonkey -p ${CLOUD} list hosts hypervisor=KVM filter=name,id name=${FROM_HOST} | awk '$1=="id" {print $3}')
TO_HOST_ID=$(cloudmonkey -p ${CLOUD} list hosts hypervisor=KVM filter=name,id name=${TO_HOST} | awk '$1=="id" {print $3}')

if [ -z "$FROM_HOST_ID" ] || [ -z "$TO_HOST_ID" ]; then
    echo "Source or destination HV not found"
    exit 1
fi

USER_VMS_NAMES=$(cloudmonkey -p ${CLOUD} list virtualmachines listall=true filter=id,name,memory hostid=${FROM_HOST_ID} | grep '^id\|^name\|^memory' | awk '{print $3}' | paste - - - | sort -k 3)
SYSTEM_VMS_NAMES=$(cloudmonkey -p ${CLOUD} list systemvms listall=true filter=id,name hostid=${FROM_HOST_ID} | grep 'id\|name' | awk '{print $3}' | paste - -)
ROUTER_VMS_NAMES=$(cloudmonkey -p ${CLOUD} list routers listall=true filter=id,name hostid=${FROM_HOST_ID} | grep 'id\|name' | awk '{print $3}' | paste - -)


echo ""
echo "Migrating all VMs from host -> host:"
echo ""
echo "    ${FROM_HOST}    ->    ${TO_HOST}"
echo ""

IFS=$'\n'
echo "Affected user VMs:"
for vm in ${USER_VMS_NAMES}; do 
    echo "    ${vm}"
done

echo ""
echo "Affected system VMs:" 
for vm in ${SYSTEM_VMS_NAMES}; do
    echo "    ${vm}";
done

echo ""
echo "Affected router VMs:"
for vm in ${ROUTER_VMS_NAMES}; do
    echo "    ${vm}";
done
unset IFS

echo ""
read -r -p "Do you want to continue? [y/N] " response
case $response in
    [yY][eE][sS]|[yY])
        ;;
    *)
        exit 2
        ;;
esac

echo ""
read -r -p "Disable source host ${FROM_HOST}? [y/N] " response
case $response in
    [yY][eE][sS]|[yY])
        ret=$(cloudmonkey update host allocationstate=Disable id=${FROM_HOST_ID})
        ;;
    *)
        ;;
esac

echo ""
echo "Starting live migration!"

IFS=$'\n'
for vm in ${USER_VMS_NAMES}; do
    name=$(echo ${vm} | awk '{print $2}')
    uuid=$(echo ${vm} | awk '{print $1}')
    echo ""
    echo "Starting migration of user VM:"
    echo "    name: ${name}"
    echo "    uuid: ${uuid}"
    ret=$(cloudmonkey -p ${CLOUD} migrate virtualmachine virtualmachineid=${uuid} hostid=${TO_HOST_ID} | grep jobresultcode | awk '{print $3}')
    if [ $SUCCESS_RETURN=$ret ]; then
        echo "Migration finished successful!"
    else
        echo "Migration finished unsuccessful, please investigate!"
        echo "VM UUID: ${uuid}"
        FAILURE=1
    fi
done
for vm in ${SYSTEM_VMS_NAMES}; do
    name=$(echo ${vm} | awk '{print $2}')
    uuid=$(echo ${vm} | awk '{print $1}')
    echo ""
    echo "Starting migration of system VM:"
    echo "    name: ${name}"
    echo "    uuid: ${uuid}"
    ret=$(cloudmonkey -p ${CLOUD} migrate systemvm virtualmachineid=${uuid} hostid=${TO_HOST_ID} | grep jobresultcode | awk '{print $3}')
    if [ $SUCCESS_RETURN=$ret ]; then
        echo "Migration finished successful!"
    else
        echo "Migration finished unsuccessful, please investigate!"
        echo "VM UUID: ${uuid}"
        FAILURE=1
    fi
done
for vm in ${ROUTER_VMS_NAMES}; do
    name=$(echo ${vm} | awk '{print $2}')
    uuid=$(echo ${vm} | awk '{print $1}')
    echo ""
    echo "Starting migration of router VM:"
    echo "    name: ${name}"
    echo "    uuid: ${uuid}"
    ret=$(cloudmonkey -p ${CLOUD} migrate systemvm virtualmachineid=${uuid} hostid=${TO_HOST_ID} | grep jobresultcode | awk '{print $3}')
    if [ $SUCCESS_RETURN=$ret ]; then
        echo "Migration finished successful!"
    else
        echo "Migration finished unsuccessful, please investigate!"
        echo "VM UUID: ${uuid}"
        FAILURE=1
    fi
done
unset IFS

echo ""
if [ $FAILURE='0' ]; then
    echo "Finished successfully!"
else
    echo "Finished, but there is/are failure(s)! Please investigate!"
fi

