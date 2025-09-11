from pydantic import ConfigDict

from abstract_builders.ubuntu_rootfs_model import Ubuntu_RootFS_Blocks_Model
from amd_zynqmp_support.zynqmp_base_model import ZynqMP_Base_Model


class ZynqMP_Ubuntu_RootFS_Model(ZynqMP_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: Ubuntu_RootFS_Blocks_Model
