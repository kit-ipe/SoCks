FROM socks-local/socks-base-alma8:${TARGETARCH}-latest

# Install tools required by yocto
RUN dnf -y install glibc-locale-source glibc-langpack-en && \
    dnf -y install chrpath lz4 rpcgen wget && \
# Install tools required by the yocto recipe libxcrypt
    dnf -y install perl-open.noarch && \
# Install required packages to package the RootFS
    dnf -y install pigz pxz && \
# Install Google repo script
    curl https://storage.googleapis.com/git-repo-downloads/repo > /usr/local/bin/repo && \
    chmod a+x /usr/local/bin/repo