FROM socks-local/socks-base-alma8:latest AS base

# Install cross compiler
RUN dnf -y install wget && \
    wget -P /app/tools/ https://developer.arm.com/-/media/Files/downloads/gnu/11.2-2022.02/binrel/gcc-arm-11.2-2022.02-x86_64-aarch64-none-elf.tar.xz && \
    tar -xJf /app/tools/gcc-arm-11.2-2022.02-x86_64-aarch64-none-elf.tar.xz -C /app/tools
ENV PATH="$PATH:/app/tools/gcc-arm-11.2-2022.02-x86_64-aarch64-none-elf/bin"