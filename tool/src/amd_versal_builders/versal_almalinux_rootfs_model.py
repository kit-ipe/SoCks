from pydantic import BaseModel, Field, ConfigDict, StringConstraints
from typing_extensions import Annotated
from typing import Optional

from abstract_builders.block_model import Block_Model, Block_Project_Model, Block_Project_Model_Default_Fields
from socks.versal_base_model import Versal_Base_Model


class Versal_AlmaLinux_RootFS_Dependencies_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    kernel: str


class Versal_AlmaLinux_RootFS_Installable_Item_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    src_block: str = Field(
        default=..., description="Name of the block in whose block package the source file is located"
    )
    src_name: str = Field(default=..., description="Path to the source item in the block package")
    dest_path: str = Field(
        default=..., description="Directory in the destination file system in which the item is to be placed"
    )
    dest_name: Optional[str] = Field(
        default="",
        description="Name of the item at the destination. If nothing is specified here, the name of the source file is used.",
    )
    dest_owner_group: Optional[str] = Field(
        default=None, description="A string to be passed to chown to set the file owner and group"
    )
    dest_permissions: Optional[str] = Field(
        default=None, description="A string to be passed to chmod to set the file permissions"
    )


class Versal_AlmaLinux_RootFS_User_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(default=..., description="Username")
    pw_hash: str = Field(default=..., description="Password hash generated with 'openssl passwd -1'")
    groups: Optional[list[str]] = Field(default=[], description="Groups to which the user is to be added")


class Versal_AlmaLinux_RootFS_Block_Project_Model(Block_Project_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    release: Annotated[str, StringConstraints(pattern=r"^[0-9.]+$")] = Field(
        default=..., description="Release version of the OS to be built"
    )
    addl_pkgs: Optional[list[str]] = Field(default=None, description="List of additional rpm packages to be installed")
    build_time_fs_layer: Optional[list[Versal_AlmaLinux_RootFS_Installable_Item_Model]] = Field(
        default=None, description="List of files to be installed that were generated at build time"
    )
    users: list[Versal_AlmaLinux_RootFS_User_Model] = Field(default=None, description="List of users to be added")
    add_build_info: bool = Block_Project_Model_Default_Fields.add_build_info
    dependencies: Versal_AlmaLinux_RootFS_Dependencies_Model = Block_Project_Model_Default_Fields.dependencies


class Versal_AlmaLinux_RootFS_Block_Model(Block_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: Versal_AlmaLinux_RootFS_Block_Project_Model


class Versal_AlmaLinux_RootFS_Blocks_Model(BaseModel):
    model_config = ConfigDict(extra="ignore")

    rootfs: Versal_AlmaLinux_RootFS_Block_Model = Field(
        default=..., description="Configuration of the AlmaLinux root file system block for Versal devices"
    )


class Versal_AlmaLinux_RootFS_Model(Versal_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: Versal_AlmaLinux_RootFS_Blocks_Model
