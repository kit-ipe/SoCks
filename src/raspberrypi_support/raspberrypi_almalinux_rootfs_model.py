from pydantic import ConfigDict

from abstract_builders.almalinux_rootfs_model import AlmaLinux_RootFS_Blocks_Model
from raspberrypi_support.raspberrypi_base_model import RaspberryPi_Base_Model


class RaspberryPi_AlmaLinux_RootFS_Model(RaspberryPi_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: AlmaLinux_RootFS_Blocks_Model
