FROM multiarch/qemu-user-static AS qemu
FROM socks-local/socks-base-alpine:${TARGETARCH}-latest

# Install QEMU binaries to run binaries for the target architecture on an x86 system
COPY --from=qemu /usr/bin/qemu-*-static /usr/bin

# Install required packages to modify the base RootFS
RUN apk --no-interactive add rsync && \
# Install required packages to package the RootFS
    apk --no-interactive add tar pigz pixz