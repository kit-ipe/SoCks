from pydantic import ConfigDict

from abstract_builders.alpinelinux_rootfs_model import AlpineLinux_RootFS_Blocks_Model
from amd_zynqmp_support.zynqmp_base_model import ZynqMP_Base_Model


class ZynqMP_AlpineLinux_RootFS_Model(ZynqMP_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: AlpineLinux_RootFS_Blocks_Model
