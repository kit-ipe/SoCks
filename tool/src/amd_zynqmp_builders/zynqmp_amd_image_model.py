from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional

from abstract_builders.block_model import Block_Model, Block_Project_Model, Block_Project_Model_Default_Fields
from socks.zynqmp_base_model import ZynqMP_Base_Model


class ZynqMP_AMD_Image_Dependencies_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    atf: str
    devicetree: str
    fsbl: str
    kernel: str
    pmu_fw: str
    ramfs: Optional[str] = None
    rootfs: Optional[str] = None
    uboot: str
    vivado: str

    @model_validator(mode="before")
    def any_file_system(cls, values):
        if not any((values.get("ramfs"), values.get("rootfs"))):
            raise ValueError("At least one file system is required. Specify 'ramfs' or 'rootfs'.")
        return values


class ZynqMP_AMD_Image_Block_Project_Model(Block_Project_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    size_boot_partition: int = Field(default=..., description="Size of the boot partition in MiB")
    size_rootfs_partition: int = Field(default=..., description="Size of the root file system partition in MiB")
    dependencies: ZynqMP_AMD_Image_Dependencies_Model = Block_Project_Model_Default_Fields.dependencies


class ZynqMP_AMD_Image_Block_Model(Block_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: ZynqMP_AMD_Image_Block_Project_Model


class ZynqMP_AMD_Image_Blocks_Model(BaseModel):
    model_config = ConfigDict(extra="ignore")

    image: ZynqMP_AMD_Image_Block_Model = Field(
        default=..., description="Configuration of the AMD boot image block for ZynqMP devices"
    )


class ZynqMP_AMD_Image_Model(ZynqMP_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: ZynqMP_AMD_Image_Blocks_Model
