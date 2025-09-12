FROM multiarch/qemu-user-static:x86_64-aarch64 AS qemu
FROM tianon/gosu AS gosu
FROM alpine:3.22

# Install QEMU binary to run aarch64 binaries on an x86 architecture
COPY --from=qemu /usr/bin/qemu-aarch64-static /usr/bin

# Update all packages
RUN apk --no-interactive upgrade && \
# Install required packages to make the image compatible with SoCks
    apk --no-interactive add bash && \
# Install required packages to modify the base RootFS
    apk --no-interactive add rsync && \
# Install required packages to package the RootFS
    apk --no-interactive add tar pigz pixz && \
# Install sudo and allow all users to use sudo without a password
    apk --no-interactive add sudo && \
    echo '%wheel ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

# Install goso as shown here: https://github.com/tianon/gosu/blob/master/INSTALL.md
COPY --from=gosu /gosu /usr/local/bin/

# Copy the entrypoint script into the container and make it executable
COPY --from=container_srcs entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set the entrypoint to the script
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Set the default command to run when the container starts
CMD ["/bin/bash"]
