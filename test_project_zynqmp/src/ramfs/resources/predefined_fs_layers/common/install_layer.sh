#!/bin/sh

#
# This script installs the predefined file system layer. It may need to be adjusted when new files are added to the layer.
#
# $1: Target rootfs to which the layer is to be added
#

# The directory of this script is used to find the predefined layer
source_dir=$(dirname "$0" | xargs realpath)

# Store target rootfs
target_dir=$1

# Copy predefined layer
rsync -rl --exclude "install_layer.sh" $source_dir/ $target_dir/

# Make init script executable
chmod a+x $target_dir/init
