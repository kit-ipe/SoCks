from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal, List, Union

class Build_Srcs_Model(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    source: str = Field(
        default=..., description="Git clone URL or path to the local project directory"
    )
    branch: Optional[str] = Field(
        default=None, description="Git repository branch"
    )

class Block_Project_Model(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    import_src: Optional[str] = Field(
        default=None, alias="import-src", description="URL or path to the pre-built files"
    )

class Container_Settings_Model(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    image: str = Field(
        default=..., description="Container image to build the block"
    )
    tag: str = Field(
        default=..., description="Container image tag"
    )

class Block_Model(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    source: Literal["build", "import"] = Field(
        default=..., description="Source for obtaining the block binaries"
    )
    builder: str = Field(
        default=..., description="Builder class to be used"
    )
    project: Block_Project_Model
    container: Container_Settings_Model