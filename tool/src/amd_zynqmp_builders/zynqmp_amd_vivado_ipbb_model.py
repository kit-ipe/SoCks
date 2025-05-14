from pydantic import BaseModel, Field, ConfigDict

from abstract_builders.block_model import (
    Block_Model,
    Block_Project_Model,
    Build_Srcs_Model,
    Block_Project_Model_Default_Fields,
)
from socks.zynqmp_base_model import ZynqMP_Base_Model


class ZynqMP_AMD_Vivado_IPBB_Block_Project_Model(Block_Project_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    build_srcs: list[Build_Srcs_Model] = Block_Project_Model_Default_Fields.build_srcs
    main_prj_src: str = Field(
        default=..., description="The main project source (repo/folder) that contains the actual IPBB project"
    )
    name: str = Field(default=..., description="Name of the project")


class ZynqMP_AMD_Vivado_IPBB_Block_Model(Block_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    project: ZynqMP_AMD_Vivado_IPBB_Block_Project_Model


class ZynqMP_AMD_Vivado_IPBB_Blocks_Model(BaseModel):
    model_config = ConfigDict(extra="ignore")

    vivado: ZynqMP_AMD_Vivado_IPBB_Block_Model = Field(
        default=..., description="Configuration of the AMD Vivado with IPbus Builder (IPBB) block for ZynqMP devices"
    )


class ZynqMP_AMD_Vivado_IPBB_Model(ZynqMP_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: ZynqMP_AMD_Vivado_IPBB_Blocks_Model
