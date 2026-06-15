FROM socks-local/socks-base-alma8:latest

# Install devicetree compiler
RUN dnf -y install dtc && \
# Install additional packages required for xsct
    dnf -y install glibc-locale-source glibc-langpack-en && \
    dnf -y install ncurses-libs ncurses-compat-libs && \
# Install dependencies for the Vivado GUI
    dnf -y install libXtst && \
# Install logicc dependencies
    dnf -y install cmake libstdc++-static glibc-static