#!/usr/bin/env bash

if ! type "bc" &> /dev/null
then
    echo "bc is required for this script to work. please install with 'yum install bc'"
    exit 1
fi
sane_users=$(cat /etc/userdomains | awk '{print $2}' | sort | uniq)

all_bytes=0
while read -r user
do
    if [ -d /home/${user} ]
    then
        total_acct_size=0
        echo "Account: ${user}"
        homesize=$(du -sh /home/${user} | awk '{ print $1 }' )
        total_acct_size=$(du -s /home/${user} | awk '{ print $1 }' )
        echo "Size: ${homesize}"
        if [ -f "/var/cpanel/suspended/${user}" ]
        then
            echo "State: Suspended"
        else
            echo "State: Active"
        fi
        if [ -f "/var/cpanel/datastore/${user}/mysql-db-usage" ]
        then
            dbinfo=$(cat /var/cpanel/datastore/${user}/mysql-db-usage)
            echo "# of databases: $(echo "${dbinfo}" | wc -l)"
            echo "Databases:"
            while read -r database
            do
                dbname=$(echo ${database} | awk '{print $1}' | sed 's/://')
                dbsize=$(du -sh /var/lib/mysql/${dbname} | awk '{ print $1 }')
                dbbytes=$(du -s /var/lib/mysql/${dbname} | awk '{ print $1 }')
                total_acct_size=$((total_acct_size+dbbytes))
                echo "  - ${dbname} (${dbsize})"
            done <<< "${dbinfo}"
        else
            echo "# of databases: 0"
        fi
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
        total_acct_size=$((total_acct_size+backupsize))
        backupmb=$(awk "BEGIN {printf \"%.2f\",${backupsize}/1024}")
        backupgb=$(awk "BEGIN {printf \"%.2f\",${backupmb}/1024}")
        if (( $(echo "${backupgb} > 1" | bc -l) ))
        then
            echo "Size of backups: ${backupgb}GB"
        else
            echo "Size of backups: ${backupmb}MB"
        fi
        echo "########"
        acctmb=$(awk "BEGIN {printf \"%.2f\",${total_acct_size}/1024}")
        acctgb=$(awk "BEGIN {printf \"%.2f\",${acctmb}/1024}")
        if (( $(echo "${acctgb} > 1" | bc -l) ))
        then
            echo "Total Size: ${acctgb}GB"
        else
            echo "Total Size: ${acctmb}MB"
        fi
        echo "-------------------------"
        all_bytes=$((all_bytes+total_acct_size))
    fi
done <<< "${sane_users}"

echo "########################################"
all_mbs=$(awk "BEGIN {printf \"%.2f\",${all_bytes}/1024}")
all_gbs=$(awk "BEGIN {printf \"%.2f\",${all_mbs}/1024}")
if (( $(echo "${all_gbs} > 1" | bc -l) ))
then
    echo "All Accounts total: ${all_gbs}GB"
else
    echo "All Accounts total: ${all_mbs}MB"
fi
