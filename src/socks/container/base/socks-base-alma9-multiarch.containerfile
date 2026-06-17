FROM tianon/gosu AS gosu
FROM almalinux:9

# Enable CRB repo (Power Tools equivalent for AlmaLinux 9)
RUN dnf -y install 'dnf-command(config-manager)' && \
    dnf config-manager --set-enabled crb && \
# Enable EPEL repo
    dnf -y install epel-release && \
# Install Development Tools group
    dnf -y group install "Development Tools" && \
# Install sudo and allow all users to use sudo without a password
    dnf -y install sudo && \
    echo '%wheel ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

# Install gosu as shown here: https://github.com/tianon/gosu/blob/master/INSTALL.md
COPY --from=gosu /gosu /usr/local/bin/

# Copy the entrypoint script into the container and make it executable
COPY --from=container_srcs entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set the entrypoint to the script
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Set the default command to run when the container starts
CMD ["/bin/bash"]