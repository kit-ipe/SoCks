FROM socks-local/socks-base-alma9:latest

# Install devicetree compiler
RUN dnf -y install dtc

# Install additional packages required for xsct
RUN dnf -y install glibc-locale-source glibc-langpack-en && \
    dnf -y install ncurses-libs ncurses-compat-libs && \
    dnf -y install libxcrypt-compat && \
# Install dependencies for the Vivado GUI
    dnf -y install libXtst && \
# Install dependencies for Vitis (2024.2)
    dnf -y install xorg-x11-utils xorg-x11-server-Xvfb

# Install uhal
RUN curl https://ipbus.web.cern.ch/doc/user/html/_downloads/ipbus-sw.repo -o /etc/yum.repos.d/ipbus-sw.repo && \
    dnf -y groupinstall uhal