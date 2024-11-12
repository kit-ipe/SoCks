from pydantic import BaseModel, Field, ConfigDict

from socks.block_model import Block_Model, Block_Project_Model, Build_Srcs_Model
from socks.zynqmp_project_model import ZynqMP_Base_Model

class ZynqMP_AMD_Devicetree_Dependencies_Model(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    vivado: str

class ZynqMP_AMD_Devicetree_Block_Project_Model(Block_Project_Model):
    model_config = ConfigDict(extra='forbid', strict=True)

    build_srcs: Build_Srcs_Model = Field(
        default=...,
        description="A single source object"
    )
    dependencies: ZynqMP_AMD_Devicetree_Dependencies_Model = Field(
        default=...,
        description="A dictionary mapping dependency names to paths of block packages, relative to the project directory."
    )

class ZynqMP_AMD_Devicetree_Block_Model(Block_Model):
    model_config = ConfigDict(extra='forbid', strict=True)

    project: ZynqMP_AMD_Devicetree_Block_Project_Model

class ZynqMP_AMD_Devicetree_Blocks_Model(BaseModel):
        model_config = ConfigDict(extra='ignore')

        devicetree: ZynqMP_AMD_Devicetree_Block_Model = Field(
            default=..., description="Configuration of the AMD devicetree block for ZynqMP devices"
        )

class ZynqMP_AMD_Devicetree_Model(ZynqMP_Base_Model):
    model_config = ConfigDict(extra='forbid', strict=True)

    blocks: ZynqMP_AMD_Devicetree_Blocks_Model