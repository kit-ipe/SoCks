from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal

from abstract_builders.block_model import (
    Block_Model,
    Block_Project_Model,
    Build_Srcs_Model,
    Block_Project_Model_Default_Fields,
)
from amd_zynqmp_support.zynqmp_base_model import ZynqMP_Base_Model


class AMD_Devicetree_Dependencies_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    vivado: str


class AMD_Devicetree_Block_Project_Model(Block_Project_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    build_srcs: Build_Srcs_Model = Block_Project_Model_Default_Fields.build_srcs
    patches: Optional[list[str]] = Block_Project_Model_Default_Fields.patches
    dt_includes: Optional[list[str]] = Field(
        default=None, description="A list of dtsi files to be included into the devicetree (system-top.dts)"
    )
    board: Literal[
        "custom",
        "ultra96",
        "zcu102",
        "zcu104",
        "zcu106",
        "zc1254",
        "zcu1275",
        "zcu1285",
        "zcu111",
        "zcu208",
        "zcu216",
        "sm-k26",
    ] = Field(
        description="AMD offers pre-defined devicetree sections for widely used evaluation cards. "
        "To include such a section, the evaluation card must be specified here."
    )
    dependencies: AMD_Devicetree_Dependencies_Model = Block_Project_Model_Default_Fields.dependencies


class AMD_Devicetree_Block_Model(Block_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: AMD_Devicetree_Block_Project_Model


class AMD_Devicetree_Blocks_Model(BaseModel):
    model_config = ConfigDict(extra="ignore")

    devicetree: AMD_Devicetree_Block_Model = Field(default=..., description="Configuration of the AMD devicetree block")


class ZynqMP_AMD_Devicetree_Model(ZynqMP_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: AMD_Devicetree_Blocks_Model
