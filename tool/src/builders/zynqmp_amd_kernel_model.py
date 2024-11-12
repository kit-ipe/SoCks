from pydantic import BaseModel, Field, ConfigDict

from socks.block_model import Block_Model, Block_Project_Model, Build_Srcs_Model
from socks.zynqmp_project_model import ZynqMP_Base_Model

class ZynqMP_AMD_Kernel_Block_Project_Model(Block_Project_Model):
    model_config = ConfigDict(extra='forbid', strict=True)

    build_srcs: Build_Srcs_Model = Field(
        default=...,
        description="A single source object"
    )
    add_build_info: bool = Field(
        default=...,
        description="Switch to specify whether or not build information should be included in the block"
    )

class ZynqMP_AMD_Kernel_Block_Model(Block_Model):
    model_config = ConfigDict(extra='forbid', strict=True)

    project: ZynqMP_AMD_Kernel_Block_Project_Model

class ZynqMP_AMD_Kernel_Blocks_Model(BaseModel):
        model_config = ConfigDict(extra='ignore')

        kernel: ZynqMP_AMD_Kernel_Block_Model = Field(
            default=..., description="Configuration of the AMD Linux Kernel block for ZynqMP devices"
        )

class ZynqMP_AMD_Kernel_Model(ZynqMP_Base_Model):
    model_config = ConfigDict(extra='forbid', strict=True)

    blocks: ZynqMP_AMD_Kernel_Blocks_Model