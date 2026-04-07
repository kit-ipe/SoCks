from pydantic import ConfigDict

from abstract_builders.alpinelinux_rootfs_model import AlpineLinux_RootFS_Blocks_Model
from amd_zynq_support.zynq_base_model import Zynq_Base_Model


class Zynq_AlpineLinux_RootFS_Model(Zynq_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: AlpineLinux_RootFS_Blocks_Model
