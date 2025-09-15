from pydantic import ConfigDict

from abstract_builders.debian_rootfs_model import Debian_RootFS_Blocks_Model
from raspberrypi_support.raspberrypi_base_model import RaspberryPi_Base_Model


class RaspberryPi_Debian_RootFS_Model(RaspberryPi_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: Debian_RootFS_Blocks_Model
