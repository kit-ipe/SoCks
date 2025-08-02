#!/bin/bash

#
# This is used by SoCks to modify the base AlmaLinux RootFS
#
# $1: Target architecture
# $2: Release version
# $3: dnf configuration file
# $4: Install root directory
#

target_arch=$1
printf "Argument target_arch is: $target_arch\n"
release_ver=$2
printf "Argument release_ver is: $release_ver\n"
dnf_conf_file=$3
printf "Argument dnf_conf_file is: $dnf_conf_file\n"
install_root=$4
printf "Argument install_root is: $install_root\n"

#
# Do not modify anything before this line!
#

# Enable ssh root login
sed -i "s:#PermitRootLogin prohibit-password:PermitRootLogin yes:g" "$install_root/etc/ssh/sshd_config"
