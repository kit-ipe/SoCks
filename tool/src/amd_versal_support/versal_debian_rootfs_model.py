from pydantic import ConfigDict

from amd_zynqmp_support.zynqmp_debian_rootfs_model import ZynqMP_Debian_RootFS_Blocks_Model
from amd_versal_support.versal_base_model import Versal_Base_Model


class Versal_Debian_RootFS_Model(Versal_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: ZynqMP_Debian_RootFS_Blocks_Model

