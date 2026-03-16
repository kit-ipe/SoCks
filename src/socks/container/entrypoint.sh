#!/bin/bash

# If the root user is to be used, there is not much to do
if [ "$CONTAINER_USER" = "root" ] || [ "$CONTAINER_UID" = "0" ]; then
    exec "$@"
fi

# Source the file to get the OS information
source /etc/os-release

# Create the user and the associated home directory
if [ "$ID" = "debian" ]; then
    # Take care of large user and group IDs common in large organizations like DESY and CERN
    uid_max=$(grep "^UID_MAX" /etc/login.defs | awk '{print $2}')
    if [ -n "$uid_max" ] && [ "$CONTAINER_UID" -ge "$uid_max" ]; then
        new_uid_max=$(("$CONTAINER_UID" + 1000))
        sed -i "s/^UID_MAX.*/UID_MAX          $new_uid_max/g" /etc/login.defs
    fi
    gid_max=$(grep "^GID_MAX" /etc/login.defs | awk '{print $2}')
    if [ -n "$gid_max" ] && [ "$CONTAINER_GID" -ge "$gid_max" ]; then
        new_gid_max=$(("$CONTAINER_GID" + 1000))
        sed -i "s/^GID_MAX.*/GID_MAX          $new_uid_max/g" /etc/login.defs
    fi
    # Create a user with the same name and id as the user on the host system. This makes it easier to use the projets from the host without a docker container.
    getent group $CONTAINER_USER || groupadd --gid $CONTAINER_GID $CONTAINER_USER
    if [ -d "/home/$CONTAINER_USER" ]; then
        # If the home directory does already exist, e.g. because something is mounted here, it must be initialized manually
        getent passwd $CONTAINER_USER || adduser --uid $CONTAINER_UID --gid $CONTAINER_GID --no-create-home --comment "" --disabled-password --quiet $CONTAINER_USER
        usermod -a -G sudo $CONTAINER_USER
        chown $CONTAINER_USER:$CONTAINER_USER /home/$CONTAINER_USER
        mkdir /home/$CONTAINER_USER/skel
        cp -r /etc/skel/. /home/$CONTAINER_USER/skel/
        chown $CONTAINER_USER:$CONTAINER_USER /home/$CONTAINER_USER/skel/.*
        mv /home/$CONTAINER_USER/skel/.[!.]* /home/$CONTAINER_USER
        rmdir /home/$CONTAINER_USER/skel
    else
        # If the home directory does not yet exist, adduser can create it
        getent passwd $CONTAINER_USER || adduser --uid $CONTAINER_UID --gid $CONTAINER_GID --comment "" --disabled-password --quiet $CONTAINER_USER
        usermod -a -G sudo $CONTAINER_USER
    fi
elif [ "$ID" = "almalinux" ]; then
    # Take care of large user and group IDs common in large organizations like DESY and CERN
    uid_max=$(grep "^UID_MAX" /etc/login.defs | awk '{print $2}')
    if [ -n "$uid_max" ] && [ "$CONTAINER_UID" -ge "$uid_max" ]; then
        new_uid_max=$(("$CONTAINER_UID" + 1000))
        sed -i "s/^UID_MAX.*/UID_MAX          $new_uid_max/g" /etc/login.defs
    fi
    gid_max=$(grep "^GID_MAX" /etc/login.defs | awk '{print $2}')
    if [ -n "$gid_max" ] && [ "$CONTAINER_GID" -ge "$gid_max" ]; then
        new_gid_max=$(("$CONTAINER_GID" + 1000))
        sed -i "s/^GID_MAX.*/GID_MAX          $new_uid_max/g" /etc/login.defs
    fi
    # Create a user with the same name and id as the user on the host system. This makes it easier to use the projets from the host without a docker container.
    getent group $CONTAINER_USER || groupadd --gid $CONTAINER_GID $CONTAINER_USER
    if [ -d "/home/$CONTAINER_USER" ]; then
        # If the home directory does already exist, e.g. because something is mounted here, it must be initialized manually
        getent passwd $CONTAINER_USER || adduser --uid $CONTAINER_UID --gid $CONTAINER_GID --no-create-home -G wheel $CONTAINER_USER
        chown $CONTAINER_USER:$CONTAINER_USER /home/$CONTAINER_USER
        mkdir /home/$CONTAINER_USER/skel
        cp -r /etc/skel/. /home/$CONTAINER_USER/skel/
        chown $CONTAINER_USER:$CONTAINER_USER /home/$CONTAINER_USER/skel/.*
        mv /home/$CONTAINER_USER/skel/.[!.]* /home/$CONTAINER_USER
        rmdir /home/$CONTAINER_USER/skel
    else
        # If the home directory does not yet exist, adduser can create it
        getent passwd $CONTAINER_USER || adduser --uid $CONTAINER_UID --gid $CONTAINER_GID --base-dir "/home" -G wheel $CONTAINER_USER
    fi
elif [ "$ID" = "alpine" ]; then
    # As far as I know, large user and group IDs are not a problem in Alpine Linux
    # Create a user with the same name and id as the user on the host system. This makes it easier to use the projets from the host without a docker container.
    getent group $CONTAINER_USER || addgroup -g $CONTAINER_GID $CONTAINER_USER
    if [ -d "/home/$CONTAINER_USER" ]; then
        # If the home directory does already exist, e.g. because something is mounted here, it must be initialized manually
        getent passwd $CONTAINER_USER || adduser -u $CONTAINER_UID -G $CONTAINER_USER -H -D $CONTAINER_USER
        addgroup $CONTAINER_USER wheel
        chown $CONTAINER_USER:$CONTAINER_USER /home/$CONTAINER_USER
    else
        # If the home directory does not yet exist, adduser can create it
        getent passwd $CONTAINER_USER || adduser -u $CONTAINER_UID -G $CONTAINER_USER -D $CONTAINER_USER
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