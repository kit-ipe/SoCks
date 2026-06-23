ARG TARGETARCH

FROM multiarch/qemu-user-static AS qemu
FROM socks-local/socks-base-alma9-multiarch:socks-${TARGETARCH}-latest

# Install QEMU binaries to run binaries for the target architecture on an x86 system
COPY --from=qemu /usr/bin/qemu-*-static /usr/bin

# Install required packages to build the base RootFS
RUN dnf -y install make wget git python3 && \
# Install required packages to modify the base RootFS
    dnf -y install rsync && \
# Install required packages to package the RootFS
    dnf -y install pigz pxz