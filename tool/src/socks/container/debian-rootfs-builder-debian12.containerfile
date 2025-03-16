FROM multiarch/qemu-user-static:x86_64-aarch64 AS qemu
FROM debian:bookworm

# Install QEMU binary to run aarch64 binaries on an x86 architecture
COPY --from=qemu /usr/bin/qemu-aarch64-static /usr/bin

# Build-time variables
ARG user_name=root
ARG user_id=0

# Switch to the root user to configure the image
USER root

# Update all packages
RUN apt update -y && apt upgrade -y

# Install required packages to build the base RootFS
RUN apt install -y debootstrap debian-archive-keyring

# Remove this package to disable the architecture check of debootstrap (https://github.com/RPi-Distro/pi-gen/issues/603)
RUN apt purge -y arch-test

# Install required packages to modify the base RootFS
RUN apt install -y rsync

# Install required packages to package the RootFS
RUN apt install -y tar pigz pixz

# Install sudo and allow all users to use sudo without a password
RUN apt install -y sudo
RUN echo '%sudo ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

# Create a user with the same name and id as the user on the host system. This makes it easier to use the projets from the host without a docker container.
RUN getent group $user_name || groupadd --gid $user_id $user_name
RUN getent passwd $user_name || adduser --uid $user_id --gid $user_id --home "/home" $user_name
RUN usermod -a -G sudo $user_name
USER $user_name
WORKDIR /home/$user_name
