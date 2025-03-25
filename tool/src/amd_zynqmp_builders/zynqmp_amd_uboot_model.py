from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

from abstract_builders.block_model import (
    Block_Model,
    Block_Project_Model,
    Build_Srcs_Model,
    Block_Project_Model_Default_Fields,
)
from socks.zynqmp_base_model import ZynqMP_Base_Model


class AMD_UBoot_Dependencies_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    atf: str


class AMD_UBoot_Block_Project_Model(Block_Project_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    build_srcs: Build_Srcs_Model = Block_Project_Model_Default_Fields.build_srcs
    patches: Optional[list[str]] = Block_Project_Model_Default_Fields.patches
    add_build_info: bool = Block_Project_Model_Default_Fields.add_build_info
    dependencies: AMD_UBoot_Dependencies_Model = Block_Project_Model_Default_Fields.dependencies


class AMD_UBoot_Block_Model(Block_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: AMD_UBoot_Block_Project_Model


class AMD_UBoot_Blocks_Model(BaseModel):
    model_config = ConfigDict(extra="ignore")

    uboot: AMD_UBoot_Block_Model = Field(default=..., description="Configuration of the AMD U-Boot block")


class ZynqMP_AMD_UBoot_Model(ZynqMP_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: AMD_UBoot_Blocks_Model
