from pydantic import ConfigDict

from abstract_builders.debian_rootfs_model import Debian_RootFS_Blocks_Model
from amd_versal_support.versal_base_model import Versal_Base_Model


class Versal_Debian_RootFS_Model(Versal_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: Debian_RootFS_Blocks_Model
