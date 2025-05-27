from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

from abstract_builders.block_model import (
    Block_Model,
    Block_Project_Model,
    Build_Srcs_Model,
    Block_Project_Model_Default_Fields,
)
from amd_zynqmp_support.zynqmp_base_model import ZynqMP_Base_Model


class ZynqMP_BusyBox_RAMFS_Dependencies_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    kernel: str


class File_System_Installable_Source_Repo_Item_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

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


class ZynqMP_BusyBox_RAMFS_Block_Project_Model(Block_Project_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    build_srcs: Build_Srcs_Model = Block_Project_Model_Default_Fields.build_srcs
    patches: Optional[list[str]] = Block_Project_Model_Default_Fields.patches
    source_repo_fs_layer: Optional[list[File_System_Installable_Source_Repo_Item_Model]] = Field(
        default=None, description="List of files and directories to be installed from the source repo"
    )
    add_build_info: bool = Block_Project_Model_Default_Fields.add_build_info
    dependencies: ZynqMP_BusyBox_RAMFS_Dependencies_Model = Block_Project_Model_Default_Fields.dependencies


class ZynqMP_BusyBox_RAMFS_Block_Model(Block_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: ZynqMP_BusyBox_RAMFS_Block_Project_Model


class ZynqMP_BusyBox_RAMFS_Blocks_Model(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ramfs: ZynqMP_BusyBox_RAMFS_Block_Model = Field(
        default=..., description="Configuration of the AMD U-Boot block for ZynqMP devices"
    )


class ZynqMP_BusyBox_RAMFS_Model(ZynqMP_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: ZynqMP_BusyBox_RAMFS_Blocks_Model
