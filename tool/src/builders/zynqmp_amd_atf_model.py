from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

from builders.block_model import Block_Model, Block_Project_Model, Build_Srcs_Model
from socks.zynqmp_base_model import ZynqMP_Base_Model


class AMD_ATF_Block_Project_Model(Block_Project_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    build_srcs: Build_Srcs_Model = Field(default=..., description="A single source object")
    patches: Optional[list[str]] = Field(
        default=None, description="A list of patches to be applied to the source files"
    )


class AMD_ATF_Block_Model(Block_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: AMD_ATF_Block_Project_Model


class AMD_ATF_Blocks_Model(BaseModel):
    model_config = ConfigDict(extra="ignore")

    atf: AMD_ATF_Block_Model = Field(
        default=..., description="Configuration of the AMD ARM Trusted Firmware (ATF) block"
    )


class ZynqMP_AMD_ATF_Model(ZynqMP_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: AMD_ATF_Blocks_Model
