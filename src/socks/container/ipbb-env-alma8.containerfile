FROM tianon/gosu AS gosu
FROM almalinux:8

# Enable Power Tools repo
RUN dnf -y install 'dnf-command(config-manager)' && \
    dnf config-manager --set-enabled powertools && \
# Enable EPEL repo
    dnf -y install epel-release && \
# Install development tools
    dnf -y group install "Development Tools"

# Install devicetree compiler
RUN dnf -y install dtc

# Install additional packages required for xsct
RUN dnf -y install glibc-locale-source glibc-langpack-en && \
    dnf -y install ncurses-libs ncurses-compat-libs && \
# Install dependencies for the Vivado GUI
    dnf -y install libXtst

# Install uhal
RUN curl https://ipbus.web.cern.ch/doc/user/html/_downloads/ipbus-sw.repo -o /etc/yum.repos.d/ipbus-sw.repo && \
    dnf -y groupinstall uhal

# Install goso as shown here: https://github.com/tianon/gosu/blob/master/INSTALL.md
COPY --from=gosu /gosu /usr/local/bin/

# Copy the entrypoint script into the container and make it executable
COPY --from=container_srcs entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set the entrypoint to the script
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Set the default command to run when the container starts
CMD ["/bin/bash"]
