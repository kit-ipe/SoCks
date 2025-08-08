from pydantic import ConfigDict

from amd_zynqmp_support.zynqmp_almalinux_rootfs_model import ZynqMP_AlmaLinux_RootFS_Blocks_Model
from raspberrypi_support.raspberrypi_base_model import RaspberryPi_Base_Model


class RaspberryPi_AlmaLinux_RootFS_Model(RaspberryPi_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: ZynqMP_AlmaLinux_RootFS_Blocks_Model
