FROM multiarch/qemu-user-static:x86_64-aarch64 AS qemu
FROM tianon/gosu AS gosu
FROM almalinux:9

# Install QEMU binary to run aarch64 binaries on an x86 architecture
COPY --from=qemu /usr/bin/qemu-aarch64-static /usr/bin

# Enable EPEL repo
RUN dnf -y install epel-release && \
# Install required packages to build the base RootFS
    dnf -y install debootstrap && \
# Install required packages to modify the base RootFS
    dnf -y install rsync && \
# Install required packages to package the RootFS
    dnf -y install tar pigz pxz && \
    # To be equivalent to the Debian container
    ln -s /usr/bin/pxz /usr/bin/pixz && \
# Install sudo and allow all users to use sudo without a password
    dnf -y install sudo && \
    echo '%wheel ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

# Install goso as shown here: https://github.com/tianon/gosu/blob/master/INSTALL.md
COPY --from=gosu /gosu /usr/local/bin/

# Copy the entrypoint script into the container and make it executable
COPY --from=container_srcs entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set the entrypoint to the script
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Set the default command to run when the container starts
CMD ["/bin/bash"]
