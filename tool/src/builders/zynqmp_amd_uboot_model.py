from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

from builders.block_model import Block_Model, Block_Project_Model, Build_Srcs_Model
from socks.zynqmp_base_model import ZynqMP_Base_Model


class AMD_UBoot_Dependencies_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    atf: str


class AMD_UBoot_Block_Project_Model(Block_Project_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    build_srcs: Build_Srcs_Model = Field(default=..., description="A single source object")
    patches: Optional[list[str]] = Field(
        default=None, description="A list of patches to be applied to the source files"
    )
    add_build_info: bool = Field(
        default=..., description="Switch to specify whether or not build information should be included in the block"
    )
    dependencies: AMD_UBoot_Dependencies_Model = Field(
        default=...,
        description="A dictionary mapping dependency names to paths of block packages, relative to the project directory.",
    )


class AMD_UBoot_Block_Model(Block_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: AMD_UBoot_Block_Project_Model


class AMD_UBoot_Blocks_Model(BaseModel):
    model_config = ConfigDict(extra="ignore")

    uboot: AMD_UBoot_Block_Model = Field(default=..., description="Configuration of the AMD U-Boot block")


class ZynqMP_AMD_UBoot_Model(ZynqMP_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: AMD_UBoot_Blocks_Model
