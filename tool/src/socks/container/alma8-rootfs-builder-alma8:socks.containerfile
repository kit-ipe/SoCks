FROM almalinux:8

# Build-time variables
ARG user_name=root
ARG user_id=0

# Switch to the root user to configure the image
USER root

# Install GPG key for CERN repos
RUN curl -o "/etc/pki/rpm-gpg/RPM-GPG-KEY-kojiv2" "https://gitlab.cern.ch/api/v4/projects/141918/repository/files/src%2FRPM-GPG-KEY-kojiv2/raw?ref=main"

# Install required packages to build the base RootFS
RUN dnf -y install make wget sudo git python3 python3-devel gcc libffi-devel
RUN dnf -y install epel-release

# Install required packages to modify the base RootFS
RUN dnf -y install rsync

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
