from pydantic import BaseModel, Field, ConfigDict

from builders.block_model import Block_Model, Block_Project_Model, Build_Srcs_Model
from builders.zynqmp_amd_petalinux_rootfs_model import ZynqMP_AMD_PetaLinux_RootFS_Block_Project_Model
from socks.zynqmp_base_model import ZynqMP_Base_Model


class ZynqMP_AMD_PetaLinux_RAMFS_Block_Model(Block_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: ZynqMP_AMD_PetaLinux_RootFS_Block_Project_Model


class ZynqMP_AMD_PetaLinux_RAMFS_Blocks_Model(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ramfs: ZynqMP_AMD_PetaLinux_RAMFS_Block_Model = Field(
        default=..., description="Configuration of the AMD PetaLinux RAM file system block for ZynqMP devices"
    )


class ZynqMP_AMD_PetaLinux_RAMFS_Model(ZynqMP_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: ZynqMP_AMD_PetaLinux_RAMFS_Blocks_Model
