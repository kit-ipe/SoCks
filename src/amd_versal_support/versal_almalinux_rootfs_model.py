from pydantic import ConfigDict

from abstract_builders.almalinux_rootfs_model import AlmaLinux_RootFS_Blocks_Model
from amd_versal_support.versal_base_model import Versal_Base_Model


class Versal_AlmaLinux_RootFS_Model(Versal_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: AlmaLinux_RootFS_Blocks_Model
