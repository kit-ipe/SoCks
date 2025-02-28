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
RUN dnf -y install dtc

# Install additional packages required for xsct
RUN dnf -y install glibc-locale-source glibc-langpack-en
RUN dnf -y install ncurses-libs ncurses-compat-libs

# Install dependencies for the Vivado GUI
RUN dnf -y install libXtst

# Install logicc dependencies
RUN dnf -y install cmake libstdc++-static glibc-static

# Create a user with the same name and id as the user on the host system. This makes it easier to use the projets from the host without a docker container.
RUN getent group $user_name || groupadd --gid $user_id $user_name
RUN getent passwd $user_name || adduser --uid $user_id --gid $user_id --base-dir "/home" $user_name
USER $user_name
WORKDIR /home/$user_name

# Install logicc
RUN mkdir -p ~/tools
RUN mkdir -p -m 0700 ~/.ssh && ssh-keyscan gitlab.kit.edu >> ~/.ssh/known_hosts
RUN --mount=type=ssh,uid=$user_id cd ~/tools; git clone git@gitlab.kit.edu:kit/ipe-sdr/ipe-sdr-dev/hardware/logicc.git --branch vivado-2022-2-migration
RUN mkdir -p ~/py_envs
RUN python3 -m venv ~/py_envs/logicc
RUN source ~/py_envs/logicc/bin/activate; cd ~/tools/logicc; pip install -U .
RUN --mount=type=ssh,uid=$user_id cd ~/tools/logicc; ./install_toml_parser

# Configure logicc
RUN source ~/py_envs/logicc/bin/activate; logicc config set lib_dir ~/tools/logicc/lib