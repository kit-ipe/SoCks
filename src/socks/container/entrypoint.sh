#!/bin/bash

# If the root user is to be used, there is not much to do
if [ "$CONTAINER_USER" = "root" ] || [ "$CONTAINER_USER_ID" = "0" ]; then
    exec "$@"
fi

# Source the file to get the OS information
source /etc/os-release

# Create the user and the associated home directory
if [ "$ID" = "debian" ]; then
    # Create a user with the same name and id as the user on the host system. This makes it easier to use the projets from the host without a docker container.
    getent group $CONTAINER_USER || groupadd --gid $CONTAINER_USER_ID $CONTAINER_USER
    if [ -d "/home/$CONTAINER_USER" ]; then
        # If the home directory does already exist, e.g. because something is mounted here, it must be initialized manually
        getent passwd $CONTAINER_USER || adduser --uid $CONTAINER_USER_ID --gid $CONTAINER_USER_ID --no-create-home --comment "" --disabled-password --quiet $CONTAINER_USER
        usermod -a -G sudo $CONTAINER_USER
        chown $CONTAINER_USER:$CONTAINER_USER /home/$CONTAINER_USER
        mkdir /home/$CONTAINER_USER/skel
        cp -r /etc/skel/. /home/$CONTAINER_USER/skel/
        chown $CONTAINER_USER:$CONTAINER_USER /home/$CONTAINER_USER/skel/.*
        mv /home/$CONTAINER_USER/skel/.[!.]* /home/$CONTAINER_USER
        rmdir /home/$CONTAINER_USER/skel
    else
        # If the home directory does not yet exist, adduser can create it
        getent passwd $CONTAINER_USER || adduser --uid $CONTAINER_USER_ID --gid $CONTAINER_USER_ID --comment "" --disabled-password --quiet $CONTAINER_USER
        usermod -a -G sudo $CONTAINER_USER
    fi
elif [ "$ID" = "almalinux" ]; then
    # Create a user with the same name and id as the user on the host system. This makes it easier to use the projets from the host without a docker container.
    getent group $CONTAINER_USER || groupadd --gid $CONTAINER_USER_ID $CONTAINER_USER
    if [ -d "/home/$CONTAINER_USER" ]; then
        # If the home directory does already exist, e.g. because something is mounted here, it must be initialized manually
        getent passwd $CONTAINER_USER || adduser --uid $CONTAINER_USER_ID --gid $CONTAINER_USER_ID --no-create-home -G wheel $CONTAINER_USER
        chown $CONTAINER_USER:$CONTAINER_USER /home/$CONTAINER_USER
        mkdir /home/$CONTAINER_USER/skel
        cp -r /etc/skel/. /home/$CONTAINER_USER/skel/
        chown $CONTAINER_USER:$CONTAINER_USER /home/$CONTAINER_USER/skel/.*
        mv /home/$CONTAINER_USER/skel/.[!.]* /home/$CONTAINER_USER
        rmdir /home/$CONTAINER_USER/skel
    else
        # If the home directory does not yet exist, adduser can create it
        getent passwd $CONTAINER_USER || adduser --uid $CONTAINER_USER_ID --gid $CONTAINER_USER_ID --base-dir "/home" -G wheel $CONTAINER_USER
    fi
elif [ "$ID" = "alpine" ]; then
    # Create a user with the same name and id as the user on the host system. This makes it easier to use the projets from the host without a docker container.
    getent group $CONTAINER_USER || addgroup -g $CONTAINER_USER_ID $CONTAINER_USER
    if [ -d "/home/$CONTAINER_USER" ]; then
        # If the home directory does already exist, e.g. because something is mounted here, it must be initialized manually
        getent passwd $CONTAINER_USER || adduser -u $CONTAINER_USER_ID -G $CONTAINER_USER -H -D $CONTAINER_USER
        addgroup $CONTAINER_USER wheel
        chown $CONTAINER_USER:$CONTAINER_USER /home/$CONTAINER_USER
    else
        # If the home directory does not yet exist, adduser can create it
        getent passwd $CONTAINER_USER || adduser -u $CONTAINER_USER_ID -G $CONTAINER_USER -D $CONTAINER_USER
        addgroup $CONTAINER_USER wheel
    fi
else
    echo "Error in entrypoint.sh. This is neither a Debian nor an AlmaLinux system. It is $ID."
    exit 1
fi

# Set the home directory as the working directory
cd /home/$CONTAINER_USER

# Execute the command as the specified user
exec /usr/local/bin/gosu $CONTAINER_USER "$@"