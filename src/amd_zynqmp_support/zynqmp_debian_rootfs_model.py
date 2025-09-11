from pydantic import ConfigDict

from abstract_builders.debian_rootfs_model import Debian_RootFS_Blocks_Model
from amd_zynqmp_support.zynqmp_base_model import ZynqMP_Base_Model


class ZynqMP_Debian_RootFS_Model(ZynqMP_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: Debian_RootFS_Blocks_Model
