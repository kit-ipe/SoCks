FROM almalinux:8

# Build-time variables
ARG uboot_version=2024.01

#
# General purpose stuff
#

# Enable Power Tools repo
RUN dnf -y install 'dnf-command(config-manager)'
RUN dnf config-manager --set-enabled powertools

# Enable EPEL repo
RUN dnf -y install epel-release

# Install development tools
RUN dnf -y group install "Development Tools"

# Install build system related tools
RUN dnf -y install git make

# Configure git
RUN git config --global user.email "container_user@example.com"
RUN git config --global user.name "container_user"
RUN mkdir /root/.ssh/ && chmod 700 /root/.ssh/
RUN ssh-keyscan -H -p 7999 gitlab.cern.ch >> /root/.ssh/known_hosts

#
# Additional packages for building the ATF
#

# Install cross compiler
RUN dnf -y install wget
RUN wget -P /app/tools/ https://developer.arm.com/-/media/Files/downloads/gnu/11.2-2022.02/binrel/gcc-arm-11.2-2022.02-x86_64-aarch64-none-elf.tar.xz
RUN tar -xJf /app/tools/gcc-arm-11.2-2022.02-x86_64-aarch64-none-elf.tar.xz -C /app/tools
ENV PATH="$PATH:/app/tools/gcc-arm-11.2-2022.02-x86_64-aarch64-none-elf/bin"

#
# Additional packages for building the Kernel
#

# Install packages officially required to build the kernel
RUN dnf -y install gcc make bash binutils flex bison dwarves util-linux kmod e2fsprogs xfsprogs squashfs-tools nfs-utils procps-ng mcelog iptables openssl bc cpio tar

# Install additionally required packages
RUN dnf -y install ncurses-devel openssl-devel

# Install cross compiler
RUN dnf -y install gcc-aarch64-linux-gnu

#
# Additional packages for building U-Boot
#

# Install Device Tree Compiler
RUN dnf -y install dtc

#
# Additional packages for building the Vivado Project
#

# Install additional packages required for xsct
RUN dnf -y install glibc-locale-source glibc-langpack-en
RUN dnf -y install ncurses-libs ncurses-compat-libs

# Install dependencies for the Vivado GUI
RUN dnf -y install libXtst

#
# Additional packages for building the Alma 8 RootFS
#

# Install required packages to build the base RootFS
RUN dnf -y install make wget sudo git python3 python3-devel gcc libffi-devel
RUN dnf -y install augeas epel-release
RUN pip3 install python-augeas

# Install required packages to modify the base RootFS
RUN dnf -y install rsync

# Install required packages to package the RootFS
RUN dnf -y install pigz pxz

#
# Additional packages for building the Boot Image
#

# Install U-Boot tools
RUN dnf -y install wget
RUN wget https://github.com/u-boot/u-boot/archive/v$uboot_version.tar.gz
RUN tar zxf v$uboot_version.tar.gz
RUN dnf -y install openssl-devel libuuid-devel gnutls-devel
RUN make -j8 -C u-boot-$uboot_version tools-only_defconfig tools-only
RUN install u-boot-$uboot_version/tools/mkenvimage /usr/bin/
RUN install u-boot-$uboot_version/tools/dumpimage /usr/bin/
RUN install u-boot-$uboot_version/tools/mkimage /usr/bin/
RUN install u-boot-$uboot_version/tools/fit_info /usr/bin/
RUN install u-boot-$uboot_version/tools/fit_check_sign /usr/bin/
RUN install u-boot-$uboot_version/tools/ifwitool /usr/bin/
RUN install u-boot-$uboot_version/tools/fdtgrep /usr/bin/
RUN rm -f v$uboot_version.tar.gz
RUN rm -rf u-boot-$uboot_version/

# Install tools to build SD card image
RUN dnf -y install libguestfs-tools
ENV LIBGUESTFS_BACKEND direct
