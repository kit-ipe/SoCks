ARG TARGETARCH

FROM socks-local/socks-base-alma9-multiarch:socks-${TARGETARCH}-latest

# Redeclare ARG after FROM to make it available in RUN commands
ARG TARGETARCH

# Prepare build-time-generated entrypoint script
ARG INITSCRIPT="/usr/local/bin/entrypoint.d/init_toolchains.sh"
RUN mkdir -p $(dirname ${INITSCRIPT}) && \
    echo -e "#!/bin/bash\n" >> ${INITSCRIPT}

# Install packages required to build U-Boot
RUN dnf -y install dtc

# Install packages officially required to build the kernel
RUN dnf -y install make bash binutils flex bison dwarves util-linux kmod e2fsprogs xfsprogs squashfs-tools nfs-utils procps-ng mcelog iptables openssl bc cpio tar && \
# Install additionally required packages
    dnf -y install ncurses-devel openssl-devel rsync && \
# Install aarch64 (cross) compiler toolchain
    if [ "$TARGETARCH" = "amd64" ]; then \
        dnf -y install gcc-aarch64-linux-gnu; \
        echo "export SOCKS_AARCH64_CROSS_COMPILE=aarch64-linux-gnu-" >> ${INITSCRIPT}; \
    elif [ "$TARGETARCH" = "arm64" ]; then \
        dnf -y install gcc; \
        echo "export SOCKS_AARCH64_CROSS_COMPILE=" >> ${INITSCRIPT}; \
    else \
        echo "Unsupported architecture: $TARGETARCH" >&2; \
        exit 1; \
    fi

# Install armhf cross compiler
RUN dnf -y install wget && \
    if [ "$TARGETARCH" = "amd64" ]; then \
        TOOLCHAIN_NAME="arm-gnu-toolchain-15.2.rel1-x86_64-arm-none-linux-gnueabihf"; \
    elif [ "$TARGETARCH" = "arm64" ]; then \
        TOOLCHAIN_NAME="arm-gnu-toolchain-15.2.rel1-aarch64-arm-none-linux-gnueabihf"; \
    else \
        echo "Unsupported architecture: $TARGETARCH" >&2; \
        exit 1; \
    fi && \
    mkdir -p /app/tools && \
    wget -P /app/tools "https://gitlab.arm.com/api/v4/projects/tooling%2Fgnu-toolchains-for-arm/packages/generic/gnu-toolchain/15.2.rel1/${TOOLCHAIN_NAME}.tar.xz" && \
    tar -xJf "/app/tools/${TOOLCHAIN_NAME}.tar.xz" -C /app/tools && \
    rm "/app/tools/${TOOLCHAIN_NAME}.tar.xz" && \
    echo "export PATH=\"\$PATH:/app/tools/${TOOLCHAIN_NAME}/bin\"" >> ${INITSCRIPT} && \
    echo "export SOCKS_ARM_CROSS_COMPILE=arm-none-linux-gnueabihf-" >> ${INITSCRIPT}