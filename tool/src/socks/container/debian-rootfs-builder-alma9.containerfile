FROM multiarch/qemu-user-static:x86_64-aarch64 AS qemu
FROM almalinux:9

# Install QEMU binary to run aarch64 binaries on an x86 architecture
COPY --from=qemu /usr/bin/qemu-aarch64-static /usr/bin

# Build-time variables
ARG user_name=root
ARG user_id=0

# Switch to the root user to configure the image
USER root

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

# Create a user with the same name and id as the user on the host system. This makes it easier to use the projets from the host without a docker container.
RUN getent group $user_name || groupadd --gid $user_id $user_name && \
    getent passwd $user_name || adduser --uid $user_id --gid $user_id --base-dir "/home" -G wheel $user_name
USER $user_name
WORKDIR /home/$user_name