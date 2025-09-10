from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

from abstract_builders.block_model import (
    Block_Model,
    Block_Project_Model,
    Build_Srcs_Model,
    Block_Project_Model_Default_Fields,
)
from amd_zynqmp_support.zynqmp_base_model import ZynqMP_Base_Model


class ZynqMP_AMD_PetaLinux_RootFS_Patch_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: str
    patch: str


class ZynqMP_AMD_PetaLinux_RootFS_Dependencies_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    kernel: str


class ZynqMP_AMD_PetaLinux_RootFS_Block_Project_Model(Block_Project_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    build_srcs: Build_Srcs_Model = Block_Project_Model_Default_Fields.build_srcs
    patches: Optional[list[ZynqMP_AMD_PetaLinux_RootFS_Patch_Model]] = Block_Project_Model_Default_Fields.patches
    add_build_info: bool = Block_Project_Model_Default_Fields.add_build_info
    dependencies: ZynqMP_AMD_PetaLinux_RootFS_Dependencies_Model = Block_Project_Model_Default_Fields.dependencies


class ZynqMP_AMD_PetaLinux_RootFS_Block_Model(Block_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: ZynqMP_AMD_PetaLinux_RootFS_Block_Project_Model


class ZynqMP_AMD_PetaLinux_RootFS_Blocks_Model(BaseModel):
    model_config = ConfigDict(extra="ignore")

    rootfs: ZynqMP_AMD_PetaLinux_RootFS_Block_Model = Field(
        default=..., description="Configuration of the AMD PetaLinux root file system block for ZynqMP devices"
    )


class ZynqMP_AMD_PetaLinux_RootFS_Model(ZynqMP_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: ZynqMP_AMD_PetaLinux_RootFS_Blocks_Model
