FROM almalinux:9

# Build-time variables
ARG user_name=root
ARG user_id=0
ARG uboot_version=2024.01

# Switch to the root user to configure the image
USER root

# Enable Power Tools repo
RUN dnf -y install 'dnf-command(config-manager)' && \
    dnf config-manager --set-enabled crb && \
# Enable EPEL repo
    dnf -y install epel-release && \
# Install development tools
    dnf -y group install "Development Tools"

# Install devicetree compiler
RUN dnf -y install dtc

# Install U-Boot tools
RUN dnf -y install wget && \
    wget https://github.com/u-boot/u-boot/archive/v$uboot_version.tar.gz && \
    tar zxf v$uboot_version.tar.gz && \
    dnf -y install openssl-devel libuuid-devel gnutls-devel && \
    make -j8 -C u-boot-$uboot_version tools-only_defconfig tools-only && \
    install u-boot-$uboot_version/tools/mkenvimage /usr/bin/ && \
    install u-boot-$uboot_version/tools/dumpimage /usr/bin/ && \
    install u-boot-$uboot_version/tools/mkimage /usr/bin/ && \
    install u-boot-$uboot_version/tools/fit_info /usr/bin/ && \
    install u-boot-$uboot_version/tools/fit_check_sign /usr/bin/ && \
    install u-boot-$uboot_version/tools/ifwitool /usr/bin/ && \
    install u-boot-$uboot_version/tools/fdtgrep /usr/bin/ && \
    rm -f v$uboot_version.tar.gz && \
    rm -rf u-boot-$uboot_version/ && \
# Install tools to build SD card image
    dnf -y install guestfs-tools
ENV LIBGUESTFS_BACKEND=direct

# Create a user with the same name and id as the user on the host system. This makes it easier to use the projets from the host without a docker container.
RUN getent group $user_name || groupadd --gid $user_id $user_name && \
    getent passwd $user_name || adduser --uid $user_id --gid $user_id --base-dir "/home" $user_name
USER $user_name
WORKDIR /home/$user_name
