FROM tianon/gosu AS gosu
FROM almalinux:9

# Build-time variables
ARG uboot_version=2024.01

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
    dnf -y install guestfs-tools
ENV LIBGUESTFS_BACKEND=direct

# Install goso as shown here: https://github.com/tianon/gosu/blob/master/INSTALL.md
COPY --from=gosu /gosu /usr/local/bin/

# Copy the entrypoint script into the container and make it executable
COPY --from=container_srcs entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set the entrypoint to the script
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Set the default command to run when the container starts
CMD ["/bin/bash"]
