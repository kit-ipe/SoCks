from pydantic import BaseModel, Field, ConfigDict

from abstract_builders.block_model import Block_Model, Block_Project_Model_Default_Fields
from amd_zynqmp_support.zynqmp_alpinelinux_rootfs_model import ZynqMP_AlpineLinux_RootFS_Block_Project_Model
from amd_zynqmp_support.zynqmp_base_model import ZynqMP_Base_Model


class ZynqMP_AlpineLinux_RAMFS_Dependencies_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    kernel: str


class ZynqMP_AlpineLinux_RAMFS_Block_Project_Model(ZynqMP_AlpineLinux_RootFS_Block_Project_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    dependencies: ZynqMP_AlpineLinux_RAMFS_Dependencies_Model = Block_Project_Model_Default_Fields.dependencies


class ZynqMP_AlpineLinux_RAMFS_Block_Model(Block_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: ZynqMP_AlpineLinux_RAMFS_Block_Project_Model


class ZynqMP_AlpineLinux_RAMFS_Blocks_Model(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ramfs: ZynqMP_AlpineLinux_RAMFS_Block_Model = Field(
        default=..., description="Configuration of the Alpine Linux RAM file system block for ZynqMP devices"
    )


class ZynqMP_AlpineLinux_RAMFS_Model(ZynqMP_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: ZynqMP_AlpineLinux_RAMFS_Blocks_Model
