from pydantic import ConfigDict

from abstract_builders.alpinelinux_ramfs_model import AlpineLinux_RAMFS_Blocks_Model
from amd_zynqmp_support.zynqmp_base_model import ZynqMP_Base_Model


class ZynqMP_AlpineLinux_RAMFS_Model(ZynqMP_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: AlpineLinux_RAMFS_Blocks_Model
