FROM tianon/gosu AS gosu
FROM debian:bookworm

# Update all packages
RUN apt update -y && apt upgrade -y && \
# Install sudo and allow all users to use sudo without a password
    apt install -y sudo && \
    echo '%sudo ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

# Install gosu as shown here: https://github.com/tianon/gosu/blob/master/INSTALL.md
COPY --from=gosu /gosu /usr/local/bin/

# Copy the entrypoint script into the container and make it executable
COPY --from=container_srcs entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set the entrypoint to the script
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Set the default command to run when the container starts
CMD ["/bin/bash"]