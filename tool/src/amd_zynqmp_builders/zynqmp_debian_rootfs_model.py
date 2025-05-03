from pydantic import BaseModel, Field, ConfigDict, StringConstraints
from typing_extensions import Annotated
from typing import Optional

from abstract_builders.block_model import Block_Model, Block_Project_Model, Block_Project_Model_Default_Fields
from abstract_builders.aarch64_rootfs_model import File_System_Installable_Item_Model, File_System_User_Model
from socks.zynqmp_base_model import ZynqMP_Base_Model


class ZynqMP_Debian_RootFS_Dependencies_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    kernel: str
    devicetree: str
    vivado: str


class ZynqMP_Debian_RootFS_Block_Project_Model(Block_Project_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    release: Annotated[str, StringConstraints(pattern=r"^[a-z]+$")] = Field(
        default=..., description="Release version of the OS to be built"
    )
    mirror: Annotated[str, StringConstraints(pattern=r"^http:\/\/.*debian.*")] = Field(
        default="http://ftp.de.debian.org/debian/", description="Debian mirror to be used"
    )
    extra_debs: Optional[list[str]] = Field(default=None, description="List of additional deb packages to be installed")
    build_time_fs_layer: Optional[list[File_System_Installable_Item_Model]] = Field(
        default=None, description="List of files to be installed that were generated at build time"
    )
    users: list[File_System_User_Model] = Field(default=None, description="List of users to be added")
    add_build_info: bool = Block_Project_Model_Default_Fields.add_build_info
    dependencies: ZynqMP_Debian_RootFS_Dependencies_Model = Block_Project_Model_Default_Fields.dependencies


class ZynqMP_Debian_RootFS_Block_Model(Block_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: ZynqMP_Debian_RootFS_Block_Project_Model


class ZynqMP_Debian_RootFS_Blocks_Model(BaseModel):
    model_config = ConfigDict(extra="ignore")

    rootfs: ZynqMP_Debian_RootFS_Block_Model = Field(
        default=..., description="Configuration of the Debian root file system block for ZynqMP devices"
    )


class ZynqMP_Debian_RootFS_Model(ZynqMP_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: ZynqMP_Debian_RootFS_Blocks_Model
