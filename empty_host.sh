#!/bin/bash

CLOUD=$1
FROM_HOST=$2
TO_HOST=$3

`cloudmonkey set display default`
`cloudmonkey sync`

SUCCESS_RETURN='0'
FAILURE=0

FROM_HOST_NAME=`cloudmonkey -p ${CLOUD} list hosts hypervisor=KVM filter=name,id id=${FROM_HOST} | grep name | awk '{print $3}'`
TO_HOST_NAME=`cloudmonkey -p ${CLOUD} list hosts hypervisor=KVM filter=name,id id=${TO_HOST} | grep name | awk '{print $3}'`

USER_VMS_NAMES=`cloudmonkey -p ${CLOUD} list virtualmachines listall=true filter=id,name hostid=${FROM_HOST} | grep 'id\|name' | awk '{print $3}' | paste - -`
SYSTEM_VMS_NAMES=`cloudmonkey -p ${CLOUD} list systemvms listall=true filter=id,name hostid=${FROM_HOST} | grep 'id\|name' | awk '{print $3}' | paste - -`
ROUTER_VMS_NAMES=`cloudmonkey -p ${CLOUD} list routers listall=true filter=id,name hostid=${FROM_HOST} | grep 'id\|name' | awk '{print $3}' | paste - -`


echo ""
echo "Migrating all VMs from host -> host:"
echo ""
echo "    ${FROM_HOST_NAME}    ->    ${TO_HOST_NAME}"
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
echo "Starting live migration!"

IFS=$'\n'
for vm in ${USER_VMS_NAMES}; do
    name=`echo ${vm} | awk '{print $2}'`
    uuid=`echo ${vm} | awk '{print $1}'`
    echo ""
    echo "Starting migration of user VM:"
    echo "    name: ${name}"
    echo "    uuid: ${uuid}"
    ret=`cloudmonkey -p ${CLOUD} migrate virtualmachine virtualmachineid=${uuid} hostid=${TO_HOST} | grep jobresultcode | awk '{print $3}'`
    if [ $SUCCESS_RETURN=$ret ]; then
        echo "Migration finished successful!"
    else
        echo "Migration finished unsuccessful, please investigate!"
        echo "VM UUID: ${uuid}"
        FAILURE=1
    fi
done
for vm in ${SYSTEM_VMS_NAMES}; do
    name=`echo ${vm} | awk '{print $2}'`
    uuid=`echo ${vm} | awk '{print $1}'`
    echo ""
    echo "Starting migration of system VM:"
    echo "    name: ${name}"
    echo "    uuid: ${uuid}"
    ret=`cloudmonkey -p ${CLOUD} migrate systemvm virtualmachineid=${uuid} hostid=${TO_HOST} | grep jobresultcode | awk '{print $3}'`
    if [ $SUCCESS_RETURN=$ret ]; then
        echo "Migration finished successful!"
    else
        echo "Migration finished unsuccessful, please investigate!"
        echo "VM UUID: ${uuid}"
        FAILURE=1
    fi
done
for vm in ${ROUTER_VMS_NAMES}; do
    name=`echo ${vm} | awk '{print $2}'`
    uuid=`echo ${vm} | awk '{print $1}'`
    echo ""
    echo "Starting migration of router VM:"
    echo "    name: ${name}"
    echo "    uuid: ${uuid}"
    ret=`cloudmonkey -p ${CLOUD} migrate systemvm virtualmachineid=${uuid} hostid=${TO_HOST} | grep jobresultcode | awk '{print $3}'`
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

