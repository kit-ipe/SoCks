from pydantic import ConfigDict

from abstract_builders.debian_rootfs_model import Debian_RootFS_Blocks_Model
from amd_zynq_support.zynq_base_model import Zynq_Base_Model


class Zynq_Debian_RootFS_Model(Zynq_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: Debian_RootFS_Blocks_Model
