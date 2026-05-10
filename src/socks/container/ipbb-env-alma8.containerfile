FROM socks-local/socks-base-alma8:latest AS base

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