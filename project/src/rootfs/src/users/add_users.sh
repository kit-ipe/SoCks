#!/bin/bash

#
# This script can be used to add users to an AlmaLinux 8 RootFS
# (This script is based on this one: https://gitlab.com/apollo-lhc/soc-os/-/blob/feature/alma/scripts/add_users.sh)
#

user_info_file=/tmp/users/user_info.txt

while IFS= read -r line
do 
    info_array=($line)

    info_array_size=${#info_array[@]}
    if [ ${info_array_size} -ne 2 ]
    then
	echo "$info_array is invalid"
	exit 1
    fi

    username=${info_array[0]}
    password_hash=${info_array[1]}

    echo "Setting up user: $username"

    if [ $username != "root" ]
    then
	useradd -m $username
	chown -R $username:$username /home/$username 
    fi
    usermod -p $password_hash $username
    usermod -a -G wheel $username
    usermod -a -G dialout $username
    
done < "$user_info_file"

