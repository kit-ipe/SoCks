from pydantic import Field, ConfigDict
from typing import Optional

from abstract_builders.block_model import Block_Project_Model_Default_Fields
from abstract_builders.debian_rootfs_model import (
    Debian_RootFS_Dependencies_Model,
    Debian_RootFS_Block_Project_Model,
    Debian_RootFS_Block_Model,
    Debian_RootFS_Blocks_Model,
)
from amd_versal_support.versal_base_model import Versal_Base_Model


class Versal_Debian_RootFS_Dependencies_Model(Debian_RootFS_Dependencies_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    devicetree: Optional[str] = None
    vivado: Optional[str] = None


class Versal_Debian_RootFS_Block_Project_Model(Debian_RootFS_Block_Project_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    dependencies: Versal_Debian_RootFS_Dependencies_Model = Block_Project_Model_Default_Fields.dependencies


class Versal_Debian_RootFS_Block_Model(Debian_RootFS_Block_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: Versal_Debian_RootFS_Block_Project_Model


class Versal_Debian_RootFS_Blocks_Model(Debian_RootFS_Blocks_Model):
    model_config = ConfigDict(extra="ignore")

    rootfs: Versal_Debian_RootFS_Block_Model = Field(
        default=..., description="Configuration of the Debian root file system block"
    )


class Versal_Debian_RootFS_Model(Versal_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: Versal_Debian_RootFS_Blocks_Model
