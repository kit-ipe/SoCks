FROM tianon/gosu AS gosu
FROM almalinux:9

# Build-time variables
ARG toolchain_user_name=ct-ng_user
ARG toolchain_user_id=9999

# Enable Power Tools repo
RUN dnf -y install 'dnf-command(config-manager)' && \
    dnf config-manager --set-enabled crb && \
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
RUN dnf -y install autoconf automake bison diffutils flex gawk gcc gcc-c++ git gperf help2man ncurses-devel make patch python3-devel texinfo wget xz

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
# Install required packages to modify the base RootFS
    dnf -y install rsync && \
# Install required packages to package the initramfs
    dnf -y install pigz pxz && \
# Install sudo and allow all users to use sudo without a password
    dnf -y install sudo && \
    echo '%wheel ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

# Create a user that can build the toolchain
#RUN getent group $toolchain_user_name || groupadd --gid $toolchain_user_id $toolchain_user_name && \
#    getent passwd $toolchain_user_name || adduser --uid $toolchain_user_id --gid $toolchain_user_id $toolchain_user_name
#USER $toolchain_user_name

# Build the cross-compilation toolchain (Should be done as non-root user)
# For glibc use: aarch64-unknown-linux-gnu
# For uClibc use: aarch64-unknown-linux-uclibc
#RUN mkdir /home/$toolchain_user_name/crosstool-ng-workspace && \
#    cd /home/$toolchain_user_name/crosstool-ng-workspace && \
#    ct-ng aarch64-unknown-linux-uclibc && \
#    ct-ng build

# Switch back to the root user
#USER root

# Install the toolchain in a location accessible to all users
#RUN mkdir /opt/crosstool-ng-toolchains && \
#    chmod 777 /opt/crosstool-ng-toolchains && \
#    mv /home/$toolchain_user_name/x-tools/* /opt/crosstool-ng-toolchains/ && \
#    rmdir /home/$toolchain_user_name/x-tools
#ENV PATH="$PATH:/opt/crosstool-ng-toolchains/aarch64-unknown-linux-uclibc/bin/"

# Build the cross-compilation toolchain
# (It is absolutely not recommended to use crosstool-ng as root user, but I think in the container it is fine.
#  The root user is used primarily because I have not found any other solution that works for podman.)
# For glibc use: aarch64-unknown-linux-gnu
# For uClibc use: aarch64-unknown-linux-uclibc
RUN mkdir /app/tools/crosstool-ng-workspace && \
    cd /app/tools/crosstool-ng-workspace && \
    ct-ng aarch64-unknown-linux-uclibc && \
    ct-ng oldconfig && \
    echo "CT_EXPERIMENTAL=y" >> .config && \
    echo "CT_ALLOW_BUILD_AS_ROOT=y" >> .config && \
    echo "CT_ALLOW_BUILD_AS_ROOT_SURE=y" >> .config && \
    ct-ng upgradeconfig && \
    ct-ng build

# Install the toolchain in a location accessible to all users
RUN mkdir /opt/crosstool-ng-toolchains && \
    chmod 777 /opt/crosstool-ng-toolchains && \
    mv /root/x-tools/* /opt/crosstool-ng-toolchains/ && \
    rmdir /root/x-tools
ENV PATH="$PATH:/opt/crosstool-ng-toolchains/aarch64-unknown-linux-uclibc/bin/"

# Install goso as shown here: https://github.com/tianon/gosu/blob/master/INSTALL.md
COPY --from=gosu /gosu /usr/local/bin/

# Copy the entrypoint script into the container and make it executable
COPY --from=container_srcs entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set the entrypoint to the script
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Set the default command to run when the container starts
CMD ["/bin/bash"]
