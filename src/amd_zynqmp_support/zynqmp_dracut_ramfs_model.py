from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

from abstract_builders.block_model import (
    Block_Model,
    Block_Project_Model,
    Build_Srcs_Model,
    Block_Project_Model_Default_Fields,
)
from amd_zynqmp_support.zynqmp_base_model import ZynqMP_Base_Model


class ZynqMP_Dracut_RAMFS_Dependencies_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    kernel: str
    rootfs: str


class ZynqMP_Dracut_RAMFS_Block_Project_Model(Block_Project_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    dependencies: ZynqMP_Dracut_RAMFS_Dependencies_Model = Block_Project_Model_Default_Fields.dependencies


class ZynqMP_Dracut_RAMFS_Block_Model(Block_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: ZynqMP_Dracut_RAMFS_Block_Project_Model


class ZynqMP_Dracut_RAMFS_Blocks_Model(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ramfs: ZynqMP_Dracut_RAMFS_Block_Model = Field(
        default=..., description="Configuration of the Dracut RAM file system block"
    )


class ZynqMP_Dracut_RAMFS_Model(ZynqMP_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: ZynqMP_Dracut_RAMFS_Blocks_Model
