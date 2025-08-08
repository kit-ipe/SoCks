from pydantic import ConfigDict

from amd_zynqmp_support.zynqmp_debian_rootfs_model import ZynqMP_Debian_RootFS_Blocks_Model
from raspberrypi_support.raspberrypi_base_model import RaspberryPi_Base_Model


class RaspberryPi_Debian_RootFS_Model(RaspberryPi_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: ZynqMP_Debian_RootFS_Blocks_Model
