FROM tianon/gosu AS gosu
FROM almalinux:8

# Enable Power Tools repo
RUN dnf -y install 'dnf-command(config-manager)' && \
    dnf config-manager --set-enabled powertools && \
# Enable EPEL repo
    dnf -y install epel-release && \
# Install development tools
    dnf -y group install "Development Tools"

# Install tools required by yocto
RUN dnf -y install glibc-locale-source glibc-langpack-en && \
    dnf -y install chrpath lz4 rpcgen wget && \
# Install tools required by the yocto recipe libxcrypt
    dnf -y install perl-open.noarch && \
# Install required packages to package the RootFS
    dnf -y install pigz pxz && \
# Install Google repo script
    curl https://storage.googleapis.com/git-repo-downloads/repo > /usr/local/bin/repo && \
    chmod a+x /usr/local/bin/repo && \
# Install sudo and allow all users to use sudo without a password
    dnf -y install sudo && \
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
