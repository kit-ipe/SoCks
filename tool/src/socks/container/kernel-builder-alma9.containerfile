FROM tianon/gosu AS gosu
FROM almalinux:9

# Enable Power Tools repo
RUN dnf -y install 'dnf-command(config-manager)' && \
    dnf config-manager --set-enabled crb && \
# Enable EPEL repo
    dnf -y install epel-release && \
# Install development tools
    dnf -y group install "Development Tools"

# Install packages required to build U-Boot
RUN dnf -y install dtc

# Install packages officially required to build the kernel
RUN dnf -y install gcc make bash binutils flex bison dwarves util-linux kmod e2fsprogs xfsprogs squashfs-tools nfs-utils procps-ng iptables openssl bc cpio tar && \
# Install additionally required packages
    dnf -y install ncurses-devel openssl-devel && \
# Install cross compiler
    dnf -y install gcc-aarch64-linux-gnu

# Install goso as shown here: https://github.com/tianon/gosu/blob/master/INSTALL.md
COPY --from=gosu /gosu /usr/local/bin/

# Copy the entrypoint script into the container and make it executable
COPY --from=container_srcs entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set the entrypoint to the script
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Set the default command to run when the container starts
CMD ["/bin/bash"]
