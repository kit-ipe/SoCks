FROM multiarch/qemu-user-static:x86_64-aarch64 AS qemu
FROM tianon/gosu AS gosu
FROM almalinux:8

# Install QEMU binary to run aarch64 binaries on an x86 architecture
COPY --from=qemu /usr/bin/qemu-aarch64-static /usr/bin

# Install required packages to build the base RootFS
RUN dnf -y install make wget sudo git python3 && \
    dnf -y install epel-release && \
# Install required packages to modify the base RootFS
    dnf -y install rsync && \
# Install required packages to package the RootFS
    dnf -y install pigz pxz && \
# Install sudo and allow all users to use sudo without a password
    dnf -y install sudo && \
    echo '%wheel ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

# Install GPG key for CERN repos
RUN curl -o "/etc/pki/rpm-gpg/RPM-GPG-KEY-kojiv2" "https://gitlab.cern.ch/api/v4/projects/141918/repository/files/src%2FRPM-GPG-KEY-kojiv2/raw?ref=main"

# Install goso as shown here: https://github.com/tianon/gosu/blob/master/INSTALL.md
COPY --from=gosu /gosu /usr/local/bin/

# Copy the entrypoint script into the container and make it executable
COPY --from=container_srcs entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set the entrypoint to the script
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Set the default command to run when the container starts
CMD ["/bin/bash"]
