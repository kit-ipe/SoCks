FROM almalinux:8

# Build-time variables
ARG user_name=root
ARG user_id=0

# Switch to the root user to configure the image
USER root

# Enable Power Tools repo
RUN dnf -y install 'dnf-command(config-manager)'
RUN dnf config-manager --set-enabled powertools

# Enable EPEL repo
RUN dnf -y install epel-release

# Install development tools
RUN dnf -y group install "Development Tools"

# Install packages officially required to build the kernel
RUN dnf -y install gcc make bash binutils flex bison dwarves util-linux kmod e2fsprogs xfsprogs squashfs-tools nfs-utils procps-ng mcelog iptables openssl bc cpio tar

# Install additionally required packages
RUN dnf -y install ncurses-devel openssl-devel

# Install packages required to build U-Boot
RUN dnf -y install dtc

# Install cross compiler
RUN dnf -y install gcc-aarch64-linux-gnu

# Create a user with the same name and id as the user on the host system. This makes it easier to use the projets from the host without a docker container.
RUN getent group $user_name || groupadd --gid $user_id $user_name
RUN getent passwd $user_name || adduser --uid $user_id --gid $user_id --base-dir "/home" $user_name
USER $user_name
WORKDIR /home/$user_name
