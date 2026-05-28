from pydantic import Field, ConfigDict
from typing import Optional

from abstract_builders.block_model import Block_Project_Model_Default_Fields
from abstract_builders.debian_rootfs_model import (
    Debian_RootFS_Dependencies_Model,
    Debian_RootFS_Block_Project_Model,
    Debian_RootFS_Block_Model,
    Debian_RootFS_Blocks_Model,
)
from amd_zynq_support.zynq_base_model import Zynq_Base_Model


class Zynq_Debian_RootFS_Dependencies_Model(Debian_RootFS_Dependencies_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    devicetree: Optional[str] = None
    vivado: Optional[str] = None


class Zynq_Debian_RootFS_Block_Project_Model(Debian_RootFS_Block_Project_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    dependencies: Zynq_Debian_RootFS_Dependencies_Model = Block_Project_Model_Default_Fields.dependencies


class Zynq_Debian_RootFS_Block_Model(Debian_RootFS_Block_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: Zynq_Debian_RootFS_Block_Project_Model


class Zynq_Debian_RootFS_Blocks_Model(Debian_RootFS_Blocks_Model):
    model_config = ConfigDict(extra="ignore")

    rootfs: Zynq_Debian_RootFS_Block_Model = Field(
        default=..., description="Configuration of the Debian root file system block"
    )


class Zynq_Debian_RootFS_Model(Zynq_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: Zynq_Debian_RootFS_Blocks_Model
