#!/usr/bin/env bash

if [ "$(xe host-list name-label=$HOSTNAME --minimal)" == "$(xe pool-list params=master --minimal)" ]
then
    echo "We are the poolmaster, so let's process the patches."

    echo "Unzipping patches"
    cd /root/xenserver_patches
    for file in $(ls /root/xenserver_patches/*.zip); do unzip ${file}; done

    echo "Deleting what we don't need"
    rm -f /root/xenserver_patches/*.zip /root/xenserver_patches/*.bz2

    # Check if already included
    XEN_ALL_PATCHES=$(xe patch-list params=name-label --minimal | tr ',' '\n' )
    for patch in $(ls *.xsupdate)
    do
        echo "Processing patch file ${patch}"

        patchname=${patch%.*}
        echo "Checking if ${patchname} from file ${patch} is already uploaded"
        echo ${XEN_ALL_PATCHES} | tr ' ' '\n' | grep ^${patchname}$ 2>&1 >/dev/null
        if [ $? -eq 0 ]; then
           echo Patch ${patch} is already installed, skipping.
        else
            echo "Uploading patch ${patchname}"
            xe patch-upload file-name=${patch}
            if [ $? -gt 0 ]; then
                echo "Uploading failed, continuing with other patches"
            fi
        fi
    done
else
    echo "We are NOT poolmaster, so skipping uploading patches"
fi
