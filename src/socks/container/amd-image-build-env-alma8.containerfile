FROM socks-local/socks-base-alma8:${TARGETARCH}-latest

# Build-time variables
ARG uboot_version=2024.01

# Install devicetree compiler
RUN dnf -y install dtc && \
# Install U-Boot tools
    dnf -y install wget && \
    wget https://github.com/u-boot/u-boot/archive/v${uboot_version}.tar.gz && \
    tar zxf v${uboot_version}.tar.gz && \
    dnf -y install openssl-devel libuuid-devel gnutls-devel && \
    make -j8 -C u-boot-${uboot_version} tools-only_defconfig tools-only && \
    install u-boot-${uboot_version}/tools/mkenvimage /usr/bin/ && \
    install u-boot-${uboot_version}/tools/dumpimage /usr/bin/ && \
    install u-boot-${uboot_version}/tools/mkimage /usr/bin/ && \
    install u-boot-${uboot_version}/tools/fit_info /usr/bin/ && \
    install u-boot-${uboot_version}/tools/fit_check_sign /usr/bin/ && \
    install u-boot-${uboot_version}/tools/ifwitool /usr/bin/ && \
    install u-boot-${uboot_version}/tools/fdtgrep /usr/bin/ && \
    rm -f v${uboot_version}.tar.gz && \
    rm -rf u-boot-${uboot_version}/ && \
# Install tools to build SD card image
    dnf -y install libguestfs-tools
ENV LIBGUESTFS_BACKEND=direct