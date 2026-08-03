ARG TARGETARCH

FROM socks-local/socks-base-alma9-multiarch:socks-${TARGETARCH}-latest

# Redeclare ARG after FROM to make it available in RUN commands
ARG TARGETARCH

# Prepare build-time-generated entrypoint script
ARG INITSCRIPT="/usr/local/bin/entrypoint.d/init_toolchains.sh"
RUN mkdir -p $(dirname ${INITSCRIPT}) && \
    echo -e "#!/bin/bash\n" >> ${INITSCRIPT}

# Install cross compiler
RUN dnf -y install wget && \
    if [ "$TARGETARCH" = "amd64" ]; then \
        TOOLCHAIN_NAME="gcc-arm-11.2-2022.02-x86_64-aarch64-none-elf"; \
    elif [ "$TARGETARCH" = "arm64" ]; then \
        TOOLCHAIN_NAME="gcc-arm-11.2-2022.02-aarch64-aarch64-none-elf"; \
    else \
        echo "Unsupported architecture: $TARGETARCH" >&2; \
        exit 1; \
    fi && \
    mkdir -p /app/tools && \
    wget -P /app/tools "https://gitlab.arm.com/api/v4/projects/tooling%2Fgnu-toolchains-for-arm/packages/generic/gnu-toolchain/11.2-2022.02/${TOOLCHAIN_NAME}.tar.xz" && \
    tar -xJf "/app/tools/${TOOLCHAIN_NAME}.tar.xz" -C /app/tools && \
    rm "/app/tools/${TOOLCHAIN_NAME}.tar.xz" && \
    echo "export PATH=\"\$PATH:/app/tools/${TOOLCHAIN_NAME}/bin\"" >> ${INITSCRIPT} && \
    echo "export SOCKS_AARCH64_CROSS_COMPILE=aarch64-none-elf-" >> ${INITSCRIPT}