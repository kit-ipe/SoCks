from pydantic import BaseModel, Field, ConfigDict, StringConstraints
from typing_extensions import Annotated
from typing import Optional

from abstract_builders.block_model import (
    Block_Model,
    Block_Project_Model,
    Build_Srcs_Model,
    Block_Project_Model_Default_Fields,
)


class Linux_Kernel_Block_Project_Model(Block_Project_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    build_srcs: Build_Srcs_Model = Block_Project_Model_Default_Fields.build_srcs
    patches: Optional[list[str]] = Block_Project_Model_Default_Fields.patches
    config_snippets: Optional[list[str]] = Block_Project_Model_Default_Fields.config_snippets
    add_build_info: bool = Block_Project_Model_Default_Fields.add_build_info
    defconfig_target: Annotated[str, StringConstraints(pattern=r".*defconfig$")] = Field(
        default=..., description="The defconfig Makefile target to be used for the kernel"
    )


class Linux_Kernel_Block_Model(Block_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: Linux_Kernel_Block_Project_Model


class Linux_Kernel_Blocks_Model(BaseModel):
    model_config = ConfigDict(extra="ignore")

    kernel: Linux_Kernel_Block_Model = Field(default=..., description="Configuration of the Linux kernel block")
