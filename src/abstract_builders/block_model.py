from pydantic import BaseModel, Field, ConfigDict, StringConstraints, field_validator, model_validator
from typing_extensions import Annotated
from typing import Optional, Literal

import os
import re

class Build_Srcs_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: str = Field(default=..., description="Git clone URL or path to the local project directory")
    branch: Optional[str] = Field(default=None, description="Git repository branch")


class Block_Project_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    import_src: Optional[str] = Field(default=None, description="URL or path to the pre-built files")


class Container_Settings_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    namespace: str = Field(default="socks-local", description="Namespace of the container image.")
    image: Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9-]+-(alma8|alma9|debian12|debian13|alpine3\.22)-(amd64|arm64|multiarch)$")] = Field(
        default=..., description="Container image to build the block"
    )
    tag: Optional[Annotated[str, StringConstraints(pattern=r"^socks-(amd64|arm64)-[a-zA-Z0-9\.-]+$")]] = Field(
        default=None, description="Container image tag"
    )
    registry: Literal["local", "docker.io"] = Field(
        default=...,
        description="Registry that provides the container image. It is also possible to build the image locally.",
    )

    @model_validator(mode="before")
    def set_default_tag(cls, data):
        if data.get("tag") is None:
            if data.get("registry") == "local":
                # Find the default architecture to be used in the tag
                image_arch_match = re.search(r"-(amd64|arm64|multiarch)$", data.get("image"))
                if not image_arch_match:
                    # If the regex search finds no match, the image parameter is invalid and will fail the subsequent
                    # 'StringConstraints' check. Therefore, we can simply return the unmodified data here, since it
                    # will not be used anyway.
                    return data
                image_arch = image_arch_match.group(1)
                if image_arch != "multiarch":
                    # If the image supports only one architecture, use that one
                    container_arch = image_arch
                else:
                    # If the image supports multiple architectures, use that of the build system
                    build_system_arch = os.uname().machine
                    if build_system_arch in ("x86_64", "x64"):
                        container_arch = "amd64"
                    elif build_system_arch in ("aarch64", "arm64"):
                        container_arch = "arm64"
                    else:
                        raise ValueError(f"Unexpected build system architecture: {build_system_arch}")
                data["tag"] = f"socks-{container_arch}-latest"
            else:
                raise ValueError("tag must be specified when registry is not 'local'")
        return data

    @model_validator(mode="after")
    def check_architecture_match(self):
        image_arch = re.search(r"-(amd64|arm64|multiarch)$", self.image).group(1)
        tag_arch = re.search(r"^socks-(amd64|arm64)-", self.tag).group(1)
        # Check for conflict
        if image_arch != tag_arch and image_arch != "multiarch":
            raise ValueError(
                f"architecture conflict: the image only supports '{image_arch}', but the architecture to be used, as "
                f"specified in the tag, is '{tag_arch}'. These architectures must match, unless the image is 'multiarch'."
            )
        return self

class Block_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: Literal["build", "import"] = Field(default=..., description="Source for obtaining the block binaries")
    builder: str = Field(default=..., description="Builder class to be used")
    project: Block_Project_Model
    container: Container_Settings_Model


class Block_Project_Model_Default_Fields:
    # The following are default fields that can be used in child classes
    dependencies = Field(
        default=...,
        description="A dictionary mapping dependency names to paths of block packages, relative to the project directory",
    )
    build_srcs = Field(default=..., description="A single source object")
    patches = Field(default=None, description="A list of patches to be applied to the source files")
    config_snippets = Field(default=None, description="A list of configuration snippets to be applied to .config")
    add_build_info = Field(
        default=..., description="Switch to specify whether or not build information should be included in the block"
    )
