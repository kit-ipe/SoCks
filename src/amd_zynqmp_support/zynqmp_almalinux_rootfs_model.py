from pydantic import Field, ConfigDict
from typing import Optional

from abstract_builders.block_model import Block_Project_Model_Default_Fields
from abstract_builders.almalinux_rootfs_model import (
    AlmaLinux_RootFS_Dependencies_Model,
    AlmaLinux_RootFS_Block_Project_Model,
    AlmaLinux_RootFS_Block_Model,
    AlmaLinux_RootFS_Blocks_Model,
)
from amd_zynqmp_support.zynqmp_base_model import ZynqMP_Base_Model


class ZynqMP_AlmaLinux_RootFS_Dependencies_Model(AlmaLinux_RootFS_Dependencies_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    devicetree: Optional[str] = None
    vivado: Optional[str] = None


class ZynqMP_AlmaLinux_RootFS_Block_Project_Model(AlmaLinux_RootFS_Block_Project_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    dependencies: ZynqMP_AlmaLinux_RootFS_Dependencies_Model = Block_Project_Model_Default_Fields.dependencies


class ZynqMP_AlmaLinux_RootFS_Block_Model(AlmaLinux_RootFS_Block_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: ZynqMP_AlmaLinux_RootFS_Block_Project_Model


class ZynqMP_AlmaLinux_RootFS_Blocks_Model(AlmaLinux_RootFS_Blocks_Model):
    model_config = ConfigDict(extra="ignore")

    rootfs: ZynqMP_AlmaLinux_RootFS_Block_Model = Field(
        default=..., description="Configuration of the AlmaLinux root file system block"
    )


class ZynqMP_AlmaLinux_RootFS_Model(ZynqMP_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: ZynqMP_AlmaLinux_RootFS_Blocks_Model
