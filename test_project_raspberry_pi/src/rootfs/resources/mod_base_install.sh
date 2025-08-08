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

dnf_default_parameters="-y --nodocs --verbose -c $dnf_conf_file --releasever=$release_ver --forcearch=$target_arch --installroot=$install_root"

#
# Do not modify anything before this line!
#

# Remove packages that we do not need
printf "\nRemoving unneeded packages...\n\n"
dnf $dnf_default_parameters autoremove

# Enable additional repos
printf "\nEnabling additional repos...\n\n"
major_version="${release_ver%%.*}"

key_path="/etc/pki/rpm-gpg/"
if [ ! -e "$key_path/RPM-GPG-KEY-EPEL-${major_version}" ]; then
    echo "EPEL key not found. EPEL needs to be enabled in the host system ('dnf install epel-release')"
    exit 1
fi

dnf $dnf_default_parameters install epel-release
dnf -y --nodocs --verbose --releasever=$release_ver --forcearch=$target_arch --installroot=$install_root config-manager --set-enabled epel
dnf -y --nodocs --verbose --releasever=$release_ver --forcearch=$target_arch --installroot=$install_root config-manager --set-enabled epel-testing
dnf -y --nodocs --verbose --releasever=$release_ver --forcearch=$target_arch --installroot=$install_root config-manager --set-enabled crb
dnf -y --nodocs --verbose --releasever=$release_ver --forcearch=$target_arch --installroot=$install_root config-manager --set-enabled plus

# Disable SELinux
printf "\nDisabling SELinux...\n\n"
sed -i 's/^SELINUX=.*$/SELINUX=disabled/' "$install_root/etc/sysconfig/selinux"
