FROM almalinux:8

# Build-time variables
ARG user_name=root
ARG user_id=0

# Switch to the root user to configure the image
USER root

# Enable Power Tools repo
RUN dnf -y install 'dnf-command(config-manager)' && \
    dnf config-manager --set-enabled powertools && \
# Enable EPEL repo
    dnf -y install epel-release && \
# Install development tools
    dnf -y group install "Development Tools"

# Install cross compiler
#RUN dnf -y install wget
#RUN wget -P /app/tools/ https://developer.arm.com/-/media/Files/downloads/gnu/11.2-2022.02/binrel/gcc-arm-11.2-2022.02-x86_64-aarch64-none-linux-gnu.tar.xz
#RUN tar -xJf /app/tools/gcc-arm-11.2-2022.02-x86_64-aarch64-none-linux-gnu.tar.xz -C /app/tools
#ENV PATH="$PATH:/app/tools/gcc-arm-11.2-2022.02-x86_64-aarch64-none-linux-gnu/bin"

# Install crosstool-NG dependencies (https://crosstool-ng.github.io/docs/os-setup/)
RUN dnf -y install autoconf automake bison diffutils flex gawk gcc gcc-c++ git gperf help2man ncurses-devel make patch texinfo wget xz python3.11 python3.11-devel

# Install crosstool-NG
RUN mkdir -p /app/repo && \
    cd /app/repo && \
    git clone https://github.com/crosstool-ng/crosstool-ng && \
    cd /app/repo/crosstool-ng && \
    git checkout crosstool-ng-1.26.0 && \
    ./bootstrap && \
    mkdir -p /app/tools/crosstool-ng && \
    ./configure --prefix=/app/tools/crosstool-ng && \
    make && \
    make install && \
    rm -rf /app/repo
ENV PATH="$PATH:/app/tools/crosstool-ng/bin"

# Install busybox dependencies
RUN dnf -y install perl-Pod-Html ncurses-devel && \
# Install required packages to package the initramfs
    dnf -y install pigz pxz && \
# Install sudo and allow all users to use sudo without a password
    dnf -y install sudo && \
    echo '%wheel ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

# Create a user with the same name and id as the user on the host system. This makes it easier to use the projets from the host without a docker container.
RUN getent group $user_name || groupadd --gid $user_id $user_name && \
    getent passwd $user_name || adduser --uid $user_id --gid $user_id --base-dir "/home" -G wheel $user_name
USER $user_name
WORKDIR /home/$user_name

# Build the cross-compilation toolchain (Must be done as non-root user)
# For glibc use: aarch64-unknown-linux-gnu
# For uClibc use: aarch64-unknown-linux-uclibc
RUN mkdir /home/$user_name/crosstool-ng-workspace && \
    cd /home/$user_name/crosstool-ng-workspace && \
    ct-ng aarch64-unknown-linux-uclibc && \
    ct-ng build
ENV PATH="$PATH:/home/$user_name/x-tools/aarch64-unknown-linux-uclibc/bin/"

# Set default user and workdir
USER $user_name
WORKDIR /home/$user_name
