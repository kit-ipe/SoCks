from pydantic import BaseModel, Field, ConfigDict

from builders.block_model import Block_Model, Block_Project_Model
from socks.versal_base_model import Versal_Base_Model


class Versal_AMD_PLM_Dependencies_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    vivado: str


class Versal_AMD_PLM_Block_Project_Model(Block_Project_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    dependencies: Versal_AMD_PLM_Dependencies_Model = Field(
        default=...,
        description="A dictionary mapping dependency names to paths of block packages, relative to the project directory.",
    )


class Versal_AMD_PLM_Block_Model(Block_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: Versal_AMD_PLM_Block_Project_Model


class Versal_AMD_PLM_Blocks_Model(BaseModel):
    model_config = ConfigDict(extra="ignore")

    plm: Versal_AMD_PLM_Block_Model = Field(
        default=..., description="Configuration of the AMD Platform Loader and Manager (PLM) block for Versal devices"
    )


class Versal_AMD_PLM_Model(Versal_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: Versal_AMD_PLM_Blocks_Model
