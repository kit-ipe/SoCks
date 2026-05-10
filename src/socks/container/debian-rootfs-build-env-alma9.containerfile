FROM socks-local/socks-base-alma9:latest AS base

FROM multiarch/qemu-user-static AS qemu
FROM base

# Install QEMU binaries to run binaries for the target architecture on an x86 system
COPY --from=qemu /usr/bin/qemu-*-static /usr/bin

# Install required packages to build the base RootFS
RUN dnf -y install debootstrap && \
# Install required packages to modify the base RootFS
    dnf -y install rsync && \
# Install required packages to package the RootFS
    dnf -y install tar pigz pxz && \
    # To be equivalent to the Debian container
    ln -s /usr/bin/pxz /usr/bin/pixz