FROM almalinux:9

# Build-time variables
ARG user_name=root
ARG user_id=0

# Switch to the root user to configure the image
USER root

# Enable Power Tools repo
RUN dnf -y install 'dnf-command(config-manager)'
RUN dnf config-manager --set-enabled crb

# Enable EPEL repo
RUN dnf -y install epel-release

# Install development tools
RUN dnf -y group install "Development Tools"

# Install cross compiler
RUN dnf -y install wget
RUN wget -P /app/tools/ https://developer.arm.com/-/media/Files/downloads/gnu/11.2-2022.02/binrel/gcc-arm-11.2-2022.02-x86_64-aarch64-none-elf.tar.xz
RUN tar -xJf /app/tools/gcc-arm-11.2-2022.02-x86_64-aarch64-none-elf.tar.xz -C /app/tools
ENV PATH="$PATH:/app/tools/gcc-arm-11.2-2022.02-x86_64-aarch64-none-elf/bin"

# Create a user with the same name and id as the user on the host system. This makes it easier to use the projets from the host without a docker container.
RUN getent group $user_name || groupadd --gid $user_id $user_name
RUN getent passwd $user_name || adduser --uid $user_id --gid $user_id --base-dir "/home" $user_name
USER $user_name
WORKDIR /home/$user_name
