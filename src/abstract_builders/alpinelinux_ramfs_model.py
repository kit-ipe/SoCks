from pydantic import BaseModel, Field, ConfigDict

from abstract_builders.block_model import Block_Model, Block_Project_Model_Default_Fields
from abstract_builders.alpinelinux_rootfs_model import AlpineLinux_RootFS_Block_Project_Model


class AlpineLinux_RAMFS_Dependencies_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    kernel: str


class AlpineLinux_RAMFS_Block_Project_Model(AlpineLinux_RootFS_Block_Project_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    dependencies: AlpineLinux_RAMFS_Dependencies_Model = Block_Project_Model_Default_Fields.dependencies


class AlpineLinux_RAMFS_Block_Model(Block_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: AlpineLinux_RAMFS_Block_Project_Model


class AlpineLinux_RAMFS_Blocks_Model(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ramfs: AlpineLinux_RAMFS_Block_Model = Field(
        default=..., description="Configuration of the Alpine Linux RAM file system block"
    )
