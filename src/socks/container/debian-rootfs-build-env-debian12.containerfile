FROM multiarch/qemu-user-static AS qemu
FROM socks-local/socks-base-debian12:latest

# Install QEMU binaries to run binaries for the target architecture on an x86 system
COPY --from=qemu /usr/bin/qemu-*-static /usr/bin

# Install required packages to build the base RootFS
RUN apt install -y debootstrap debian-archive-keyring fakeroot && \
# Remove this package to disable the architecture check of debootstrap (https://github.com/RPi-Distro/pi-gen/issues/603)
    apt purge -y arch-test && \
# Install required packages to modify the base RootFS
    apt install -y rsync && \
# Install required packages to package the RootFS
    apt install -y tar pigz pixz

# Create an 'alias' for 'debootstrap', because it must be run in a fakeroot environment when using rootless Podman
# and a Debian 12 container, even if the user inside the container has root privileges.
# (https://github.com/podman-container-tools/podman/issues/4619)
RUN printf '%s\n' \
    '#!/bin/sh' \
    'echo "Info: debootstrap is wrapped so that it runs in a fakeroot environment (required only for Debian 12 containers)"' \
    'exec fakeroot /usr/sbin/debootstrap "$@"' > /usr/local/bin/debootstrap && \
    chmod +x /usr/local/bin/debootstrap
