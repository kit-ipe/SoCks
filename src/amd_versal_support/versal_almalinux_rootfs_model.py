from pydantic import ConfigDict

from amd_zynqmp_support.zynqmp_almalinux_rootfs_model import ZynqMP_AlmaLinux_RootFS_Blocks_Model
from amd_versal_support.versal_base_model import Versal_Base_Model


class Versal_AlmaLinux_RootFS_Model(Versal_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: ZynqMP_AlmaLinux_RootFS_Blocks_Model
