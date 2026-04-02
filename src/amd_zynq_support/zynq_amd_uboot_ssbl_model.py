from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

from abstract_builders.block_model import (
    Block_Model,
    Block_Project_Model,
    Build_Srcs_Model,
    Block_Project_Model_Default_Fields,
)
from amd_zynq_support.zynq_base_model import Zynq_Base_Model


class AMD_UBoot_SSBL_Block_Project_Model(Block_Project_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    build_srcs: Build_Srcs_Model = Block_Project_Model_Default_Fields.build_srcs
    patches: Optional[list[str]] = Block_Project_Model_Default_Fields.patches
    config_snippets: Optional[list[str]] = Block_Project_Model_Default_Fields.config_snippets
    add_build_info: bool = Block_Project_Model_Default_Fields.add_build_info


class AMD_UBoot_SSBL_Block_Model(Block_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: AMD_UBoot_SSBL_Block_Project_Model


class AMD_UBoot_SSBL_Blocks_Model(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ssbl: AMD_UBoot_SSBL_Block_Model = Field(default=..., description="Configuration of the AMD U-Boot SSBL block")


class Zynq_AMD_UBoot_SSBL_Model(Zynq_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: AMD_UBoot_SSBL_Blocks_Model