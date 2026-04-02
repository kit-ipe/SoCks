from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional, Literal

from abstract_builders.block_model import Block_Model, Block_Project_Model, Block_Project_Model_Default_Fields
from amd_zynq_support.zynq_base_model import Zynq_Base_Model


class Zynq_AMD_Image_Dependencies_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    devicetree: str
    fsbl: str
    kernel: str
    ramfs: Optional[str] = None
    rootfs: Optional[str] = None
    ssbl: str
    vivado: str

    @model_validator(mode="before")
    def any_file_system(cls, values):
        if not any((values.get("ramfs"), values.get("rootfs"))):
            raise ValueError("At least one file system is required. Specify 'ramfs' or 'rootfs'.")
        return values


class Zynq_AMD_Image_Block_Project_Model(Block_Project_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    uboot_image_kernel: Literal["Image", "zImage"] = Field(
        default=..., description="Kernel image to be integrated into image.ub"
    )
    boot_image_kernel: Literal["Image", "zImage", "image.ub"] = Field(
        default=..., description="Kernel image to be integrated into BOOT.BIN or copied to the SD card image"
    )
    size_boot_partition: int = Field(default=..., description="Size of the boot partition in MiB")
    size_rootfs_partition: int = Field(default=..., description="Size of the root file system partition in MiB")
    dependencies: Zynq_AMD_Image_Dependencies_Model = Block_Project_Model_Default_Fields.dependencies


class Zynq_AMD_Image_Block_Model(Block_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: Zynq_AMD_Image_Block_Project_Model


class Zynq_AMD_Image_Blocks_Model(BaseModel):
    model_config = ConfigDict(extra="ignore")

    image: Zynq_AMD_Image_Block_Model = Field(
        default=..., description="Configuration of the AMD boot image block for Zynq devices"
    )


class Zynq_AMD_Image_Model(Zynq_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: Zynq_AMD_Image_Blocks_Model
