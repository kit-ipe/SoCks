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

# Install logicc dependencies
RUN dnf -y install cmake libstdc++-static glibc-static

# Create a user with the same name and id as the user on the host system. This makes it easier to use the projets from the host without a docker container.
RUN getent group $user_name || groupadd --gid $user_id $user_name && \
    getent passwd $user_name || adduser --uid $user_id --gid $user_id --base-dir "/home" $user_name
USER $user_name
WORKDIR /home/$user_name

# Install logicc
RUN --mount=type=ssh,uid=$user_id \
    mkdir -p -m 0700 ~/.ssh && \
    ssh-keyscan gitlab.kit.edu >> ~/.ssh/known_hosts && \
    mkdir -p ~/tools && \
    git clone git@gitlab.kit.edu:kit/ipe-sdr/ipe-sdr-dev/hardware/logicc.git ~/tools/logicc && \
    mkdir -p ~/py_envs && \
    python3 -m venv ~/py_envs/logicc && \
    source ~/py_envs/logicc/bin/activate; cd ~/tools/logicc; pip install -U . && \
    cd ~/tools/logicc; ./install_toml_parser && \
# Configure logicc
    source ~/py_envs/logicc/bin/activate; logicc config set lib_dir ~/tools/logicc/lib