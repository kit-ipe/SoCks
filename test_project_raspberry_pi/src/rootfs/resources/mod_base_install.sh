#!/bin/bash

#
# This is used by SoCks to modify the base Debian RootFS
#
# $1: Target architecture
# $2: Release version
# $3: Install root directory
#

target_arch=$1
printf "Argument target_arch is: $target_arch\n"
release_ver=$2
printf "Argument release_ver is: $release_ver\n"
install_root=$3
printf "Argument install_root is: $install_root\n"

#
# Do not modify anything before this line!
#

# Add your commands here!
