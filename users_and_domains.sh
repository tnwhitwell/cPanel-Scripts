#!/usr/bin/env bash

sane_users=$(cat /etc/userdomains | awk '{print $2}' | sort | uniq)

while read -r user
do
    if [ -d /home/${user} ]
    then
    echo "Account: ${user}"
        homesize=$(du -sh /home/${user} | awk '{ print $1 }' )
        echo "Size: ${homesize}"
        echo "Domains:"
        while read -r domain
        do
            echo "  - ${domain}"
        done <<< "$(grep "${user}" /etc/userdomains | awk '{ print $1}' | sed 's/://g')"
        backupfiles="$(find /backup -iname ${user}.tar.gz)"
        echo "# of backups: $(echo "${backupfiles}" | wc -l)"
        backupsize=0
        while read -r backupfile
        do
            thissize=$(du -s ${backupfile} | awk '{ print $1}')
            backupsize=$((backupsize + thissize))
        done <<< "${backupfiles}"
        backupmb=$(awk "BEGIN {printf \"%.2f\",${backupsize}/1024}")
        backupgb=$(awk "BEGIN {printf \"%.2f\",${backupmb}/1024}")
        if (( $(echo "${backupgb} > 1" | bc -l) ))
        then
            echo "Size of backups: ${backupgb}GB"
        else
            echo "Size of backups: ${backupmb}MB"
        fi
        echo "-------------------------"
    fi
done <<< "${sane_users}"
