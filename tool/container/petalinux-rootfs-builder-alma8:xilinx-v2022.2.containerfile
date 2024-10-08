FROM almalinux:8

# Build-time variables
ARG user_name=root
ARG user_id=0

# Switch to the root user to configure the image
USER root

# Enable Power Tools repo
RUN dnf -y install 'dnf-command(config-manager)'
RUN dnf config-manager --set-enabled powertools

# Enable EPEL repo
RUN dnf -y install epel-release

# Install development tools
RUN dnf -y group install "Development Tools"

# Install tools required by yocto
RUN dnf -y install glibc-locale-source glibc-langpack-en
RUN dnf -y install chrpath lz4 rpcgen wget

# Install tools required by the yocto recipe libxcrypt
RUN dnf -y install perl-open.noarch

# Install Google repo script
RUN curl https://storage.googleapis.com/git-repo-downloads/repo > /usr/local/bin/repo
RUN chmod a+x /usr/local/bin/repo

# Install required packages to package the RootFS
RUN dnf -y install pigz pxz

# Install sudo and allow all users to use sudo without a password
RUN dnf -y install sudo
RUN echo '%wheel ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

# Create a user with the same name and id as the user on the host system. This makes it easier to use the projets from the host without a docker container.
RUN getent group $user_name || groupadd --gid $user_id $user_name
RUN getent passwd $user_name || adduser --uid $user_id --gid $user_id --base-dir "/home" -G wheel $user_name
USER $user_name
WORKDIR /home/$user_name
