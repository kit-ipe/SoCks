ARG TARGETARCH

FROM socks-local/socks-base-alma8-multiarch:socks-${TARGETARCH}-latest AS busybox-toolchain

# Prepare build-time-generated entrypoint script
ARG INITSCRIPT="/usr/local/bin/entrypoint.d/init_toolchains.sh"
RUN mkdir -p $(dirname ${INITSCRIPT}) && \
    echo -e "#!/bin/bash\n" >> ${INITSCRIPT}

# Install cross-compilation toolchain (The toolchains included in the distribution cannot be used because they do not contain "byteswap.h")
RUN dnf -y install wget && \
    TOOLCHAIN_NAME="gcc-arm-11.2-2022.02-x86_64-aarch64-none-linux-gnu" && \
    wget -P /app/tools/ "https://gitlab.arm.com/api/v4/projects/tooling%2Fgnu-toolchains-for-arm/packages/generic/gnu-toolchain/11.2-2022.02/${TOOLCHAIN_NAME}.tar.xz" && \
    tar -xJf "/app/tools/${TOOLCHAIN_NAME}.tar.xz" -C /app/tools && \
    rm "/app/tools/${TOOLCHAIN_NAME}.tar.xz" && \
    echo "export PATH=\"\$PATH:/app/tools/${TOOLCHAIN_NAME}/bin\"" >> ${INITSCRIPT} && \
    echo "export SOCKS_AARCH64_CROSS_COMPILE=aarch64-none-linux-gnu-" >> ${INITSCRIPT}

# Install busybox dependencies
RUN dnf -y install perl-Pod-Html ncurses-devel && \
# Install required packages to modify the base file system
    dnf -y install rsync && \
# Install required packages to package the initramfs
    dnf -y install pigz pxz