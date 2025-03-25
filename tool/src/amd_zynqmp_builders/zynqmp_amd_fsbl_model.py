from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

from abstract_builders.block_model import Block_Model, Block_Project_Model, Block_Project_Model_Default_Fields
from socks.zynqmp_base_model import ZynqMP_Base_Model


class ZynqMP_AMD_FSBL_Dependencies_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    vivado: str


class ZynqMP_AMD_FSBL_Block_Project_Model(Block_Project_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    patches: Optional[list[str]] = Block_Project_Model_Default_Fields.patches
    dependencies: ZynqMP_AMD_FSBL_Dependencies_Model = Block_Project_Model_Default_Fields.dependencies


class ZynqMP_AMD_FSBL_Block_Model(Block_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: ZynqMP_AMD_FSBL_Block_Project_Model


class ZynqMP_AMD_FSBL_Blocks_Model(BaseModel):
    model_config = ConfigDict(extra="ignore")

    fsbl: ZynqMP_AMD_FSBL_Block_Model = Field(
        default=..., description="Configuration of the AMD First Stage Boot Loader (FSBL) block for ZynqMP devices"
    )


class ZynqMP_AMD_FSBL_Model(ZynqMP_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: ZynqMP_AMD_FSBL_Blocks_Model
