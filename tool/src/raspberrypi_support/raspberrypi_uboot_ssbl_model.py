from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

from abstract_builders.block_model import (
    Block_Model,
    Block_Project_Model,
    Build_Srcs_Model,
    Block_Project_Model_Default_Fields,
)
from raspberrypi_support.raspberrypi_base_model import RaspberryPi_Base_Model


class RaspberryPi_UBoot_SSBL_Block_Project_Model(Block_Project_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    build_srcs: Build_Srcs_Model = Block_Project_Model_Default_Fields.build_srcs
    patches: Optional[list[str]] = Block_Project_Model_Default_Fields.patches
    config_snippets: Optional[list[str]] = Block_Project_Model_Default_Fields.config_snippets
    add_build_info: bool = Block_Project_Model_Default_Fields.add_build_info


class RaspberryPi_UBoot_SSBL_Block_Model(Block_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: RaspberryPi_UBoot_SSBL_Block_Project_Model


class RaspberryPi_UBoot_SSBL_Blocks_Model(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ssbl: RaspberryPi_UBoot_SSBL_Block_Model = Field(
        default=..., description="Configuration of the Raspberry Pi U-Boot SSBL block"
    )


class RaspberryPi_UBoot_SSBL_Model(RaspberryPi_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: RaspberryPi_UBoot_SSBL_Blocks_Model
