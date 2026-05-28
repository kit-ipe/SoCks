from pydantic import Field, ConfigDict
from typing import Optional

from abstract_builders.block_model import Block_Project_Model_Default_Fields
from abstract_builders.almalinux_rootfs_model import (
    AlmaLinux_RootFS_Dependencies_Model,
    AlmaLinux_RootFS_Block_Project_Model,
    AlmaLinux_RootFS_Block_Model,
    AlmaLinux_RootFS_Blocks_Model,
)
from amd_versal_support.versal_base_model import Versal_Base_Model


class Versal_AlmaLinux_RootFS_Dependencies_Model(AlmaLinux_RootFS_Dependencies_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    devicetree: Optional[str] = None
    vivado: Optional[str] = None


class Versal_AlmaLinux_RootFS_Block_Project_Model(AlmaLinux_RootFS_Block_Project_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    dependencies: Versal_AlmaLinux_RootFS_Dependencies_Model = Block_Project_Model_Default_Fields.dependencies


class Versal_AlmaLinux_RootFS_Block_Model(AlmaLinux_RootFS_Block_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: Versal_AlmaLinux_RootFS_Block_Project_Model


class Versal_AlmaLinux_RootFS_Blocks_Model(AlmaLinux_RootFS_Blocks_Model):
    model_config = ConfigDict(extra="ignore")

    rootfs: Versal_AlmaLinux_RootFS_Block_Model = Field(
        default=..., description="Configuration of the AlmaLinux root file system block"
    )


class Versal_AlmaLinux_RootFS_Model(Versal_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: Versal_AlmaLinux_RootFS_Blocks_Model
