from pydantic import BaseModel, Field, ConfigDict
from typing import List

from socks.block_model import Block_Model, Block_Project_Model, Build_Srcs_Model
from socks.zynqmp_project_model import ZynqMP_Base_Model

class ZynqMP_AMD_Vivado_IPBB_Block_Project_Model(Block_Project_Model):
    model_config = ConfigDict(extra='forbid', strict=True)

    build_srcs: List[Build_Srcs_Model] = Field(
        default=...,
        alias="build-srcs",
        description="An array of source objects"
    )
    name: str = Field(
        default=...,
        description="Name of the project"
    )

class ZynqMP_AMD_Vivado_IPBB_Block_Model(Block_Model):
    model_config = ConfigDict(extra='forbid', strict=True)

    project: ZynqMP_AMD_Vivado_IPBB_Block_Project_Model

class ZynqMP_AMD_Vivado_IPBB_Blocks_Model(BaseModel):
        model_config = ConfigDict(extra='ignore')

        vivado: ZynqMP_AMD_Vivado_IPBB_Block_Model = Field(
            default=..., description="Configuration of the AMD Vivado with IPbus Builder (IPBB) block for ZynqMP devices"
        )

class ZynqMP_AMD_Vivado_IPBB_Model(ZynqMP_Base_Model):
    model_config = ConfigDict(extra='forbid', strict=True)

    blocks: ZynqMP_AMD_Vivado_IPBB_Blocks_Model