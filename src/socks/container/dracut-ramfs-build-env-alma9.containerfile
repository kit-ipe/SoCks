FROM socks-local/socks-base-alma9:${TARGETARCH}-latest

# Install dracut
RUN dnf -y install dracut && \
# Install dracut dependencies (e.g. e2fsprogs is required to mount the rootfs from an ext4 partition)
    dnf -y install NetworkManager e2fsprogs
