FROM almalinux:8

# Build-time variables
ARG user_name=root
ARG user_id=0

# Switch to the root user to configure the image
USER root

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

# Create a user with the same name and id as the user on the host system. This makes it easier to use the projets from the host without a docker container.
RUN getent group $user_name || groupadd --gid $user_id $user_name && \
    getent passwd $user_name || adduser --uid $user_id --gid $user_id --base-dir "/home" $user_name
USER $user_name
WORKDIR /home/$user_name

# Install IPBB
RUN mkdir -p /home/$user_name/tools && \
    cd /home/$user_name/tools; curl -L https://github.com/ipbus/ipbb/archive/dev/2024d.tar.gz | tar xvz && \
    cd /home/$user_name/tools; source ipbb-dev-2024d/env.sh && \
# Create SSH directory and add known hosts
    mkdir /home/$user_name/.ssh && \
    chmod 700 /home/$user_name/.ssh && \
    ssh-keyscan -p 7999 gitlab.cern.ch >> /home/$user_name/.ssh/known_hosts
