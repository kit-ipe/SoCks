from pydantic import ConfigDict

from abstract_builders.almalinux_rootfs_model import AlmaLinux_RootFS_Blocks_Model
from amd_zynqmp_support.zynqmp_base_model import ZynqMP_Base_Model


class ZynqMP_AlmaLinux_RootFS_Model(ZynqMP_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: AlmaLinux_RootFS_Blocks_Model
