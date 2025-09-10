from pydantic import BaseModel, Field, ConfigDict, StringConstraints, model_validator
from typing import Optional, Literal
from typing_extensions import Annotated

import multiprocessing


class Project_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    socks_version: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9.]+$")] = Field(
        default=..., description="The appropriate SoCks version for this project"
    )
    type: Literal["RaspberryPi"] = Field(default=..., description="The unique identifier of the project type")
    name: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9-]+$")] = Field(
        default=..., description="The name of the project"
    )
    rpi_model: Literal["RPi_4B", "RPi_5"] = Field(
        description="The Raspberry Pi model for which the build is intended. "
        "If this setting is changed, the kernel and U-Boot configurations must be regenerated manually."
    )


class Make_Settings_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    max_build_threads: Annotated[int, Field(strict=True, gt=0)] = Field(
        default=multiprocessing.cpu_count(),
        description=(
            "Number of Makefile recipes to be executed simultaneously "
            "(If not specified, the number of CPU cores is used)"
        ),
    )


class External_Tools_Settings_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    container_tool: Literal["docker", "podman", "none"] = Field(
        default=..., description="Container management tool to be used"
    )
    make: Optional[Make_Settings_Model] = Make_Settings_Model()


class Dummy_Block_Model(BaseModel):
    model_config = ConfigDict(extra="ignore")

    builder: str = Field(default=..., description="Builder class to be used")


class Blocks_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    kernel: Dummy_Block_Model
    # ramfs: Optional[Dummy_Block_Model] = None
    rootfs: Optional[Dummy_Block_Model] = None
    ssbl: Optional[Dummy_Block_Model] = None
    image: Dummy_Block_Model


class RaspberryPi_Base_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: Project_Model
    external_tools: External_Tools_Settings_Model
    blocks: Blocks_Model
