from pydantic import BaseModel, Field, ConfigDict

from socks.block_model import Block_Model, Block_Project_Model
from socks.zynqmp_base_model import ZynqMP_Base_Model

class ZynqMP_Alma_RootFS_Dependencies_Model(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    kernel: str
    devicetree: str
    vivado: str

class ZynqMP_Alma_RootFS_Block_Project_Model(Block_Project_Model):
    model_config = ConfigDict(extra='forbid', strict=True)

    add_build_info: bool = Field(
        default=...,
        description="Switch to specify whether or not build information should be included in the block"
    )
    dependencies: ZynqMP_Alma_RootFS_Dependencies_Model = Field(
        default=...,
        description="A dictionary mapping dependency names to paths of block packages, relative to the project directory."
    )

class ZynqMP_Alma_RootFS_Block_Model(Block_Model):
    model_config = ConfigDict(extra='forbid', strict=True)

    release: str = Field(
        default=..., description="Release version of the OS to be built"
    )
    project: ZynqMP_Alma_RootFS_Block_Project_Model

class ZynqMP_Alma_RootFS_Blocks_Model(BaseModel):
        model_config = ConfigDict(extra='ignore')

        rootfs: ZynqMP_Alma_RootFS_Block_Model = Field(
            default=..., description="Configuration of the AlmaLinux root file system block for ZynqMP devices"
        )

class ZynqMP_Alma_RootFS_Model(ZynqMP_Base_Model):
    model_config = ConfigDict(extra='forbid', strict=True)

    blocks: ZynqMP_Alma_RootFS_Blocks_Model