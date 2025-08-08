from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional

from abstract_builders.block_model import Block_Model, Block_Project_Model, Block_Project_Model_Default_Fields
from raspberrypi_support.raspberrypi_base_model import RaspberryPi_Base_Model


class RaspberryPi_Image_Dependencies_Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    kernel: str
    # ramfs: Optional[str] = None
    rootfs: Optional[str] = None
    ssbl: Optional[str] = None

    @model_validator(mode="before")
    def any_file_system(cls, values):
        if not any((values.get("ramfs"), values.get("rootfs"))):
            raise ValueError("At least one file system is required. Specify 'ramfs' or 'rootfs'.")
        return values


class RaspberryPi_Image_Block_Project_Model(Block_Project_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    size_boot_partition: int = Field(default=..., description="Size of the boot partition in MiB")
    size_rootfs_partition: int = Field(default=..., description="Size of the root file system partition in MiB")
    dependencies: RaspberryPi_Image_Dependencies_Model = Block_Project_Model_Default_Fields.dependencies


class RaspberryPi_Image_Block_Model(Block_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: RaspberryPi_Image_Block_Project_Model


class RaspberryPi_Image_Blocks_Model(BaseModel):
    model_config = ConfigDict(extra="ignore")

    image: RaspberryPi_Image_Block_Model = Field(
        default=..., description="Configuration of the boot image block for Raspberry Pi devices"
    )


class RaspberryPi_Image_Model(RaspberryPi_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: RaspberryPi_Image_Blocks_Model
