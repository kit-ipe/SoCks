FROM socks-local/socks-base-alma9:${TARGETARCH}-latest

# Install packages required to build U-Boot
RUN dnf -y install dtc

# Install packages officially required to build the kernel
RUN dnf -y install gcc make bash binutils flex bison dwarves util-linux kmod e2fsprogs xfsprogs squashfs-tools nfs-utils procps-ng mcelog iptables openssl bc cpio tar && \
# Install additionally required packages
    dnf -y install ncurses-devel openssl-devel rsync && \
# Install aarch64 cross compiler
    dnf -y install gcc-aarch64-linux-gnu

# Install armhf cross compiler
RUN dnf -y install wget && \
    wget -P /app/tools/ https://developer.arm.com/-/media/Files/downloads/gnu/15.2.rel1/binrel/arm-gnu-toolchain-15.2.rel1-x86_64-arm-none-linux-gnueabihf.tar.xz && \
    tar -xJf /app/tools/arm-gnu-toolchain-15.2.rel1-x86_64-arm-none-linux-gnueabihf.tar.xz -C /app/tools
ENV PATH="$PATH:/app/tools/arm-gnu-toolchain-15.2.rel1-x86_64-arm-none-linux-gnueabihf/bin"