FROM multiarch/qemu-user-static:x86_64-aarch64 AS qemu
FROM tianon/gosu AS gosu
FROM debian:bookworm

# Install QEMU binary to run aarch64 binaries on an x86 architecture
COPY --from=qemu /usr/bin/qemu-aarch64-static /usr/bin

# Update all packages
RUN apt update -y && apt upgrade -y && \
# Install required packages to build the base RootFS
    apt install -y debootstrap debian-archive-keyring && \
# Remove this package to disable the architecture check of debootstrap (https://github.com/RPi-Distro/pi-gen/issues/603)
    apt purge -y arch-test && \
# Install required packages to modify the base RootFS
    apt install -y rsync && \
# Install required packages to package the RootFS
    apt install -y tar pigz pixz && \
# Install sudo and allow all users to use sudo without a password
    apt install -y sudo && \
    echo '%sudo ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

# Install goso as shown here: https://github.com/tianon/gosu/blob/master/INSTALL.md
COPY --from=gosu /gosu /usr/local/bin/

# Copy the entrypoint script into the container and make it executable
COPY --from=container_srcs entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set the entrypoint to the script
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Set the default command to run when the container starts
CMD ["/bin/bash"]
