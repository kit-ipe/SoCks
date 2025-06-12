from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional

from abstract_builders.block_model import Block_Model, Block_Project_Model, Block_Project_Model_Default_Fields
from amd_versal_support.versal_base_model import Versal_Base_Model


class Versal_AMD_Image_Dependencies_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    atf: str
    devicetree: str
    kernel: str
    plm: str
    psm_fw: str
    ramfs: Optional[str] = None
    rootfs: Optional[str] = None
    ssbl: str
    vivado: str

    @model_validator(mode="before")
    def any_file_system(cls, values):
        if not any((values.get("ramfs"), values.get("rootfs"))):
            raise ValueError("At least one file system is required. Specify 'ramfs' or 'rootfs'.")
        return values


class Versal_AMD_Image_Block_Project_Model(Block_Project_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    dependencies: Versal_AMD_Image_Dependencies_Model = Block_Project_Model_Default_Fields.dependencies


class Versal_AMD_Image_Block_Model(Block_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: Versal_AMD_Image_Block_Project_Model


class Versal_AMD_Image_Blocks_Model(BaseModel):
    model_config = ConfigDict(extra="ignore")

    image: Versal_AMD_Image_Block_Model = Field(
        default=..., description="Configuration of the AMD boot image block for Versal devices"
    )


class Versal_AMD_Image_Model(Versal_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: Versal_AMD_Image_Blocks_Model
