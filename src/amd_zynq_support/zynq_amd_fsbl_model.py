from pydantic import ConfigDict

from amd_zynqmp_support.zynqmp_amd_fsbl_model import ZynqMP_AMD_FSBL_Blocks_Model
from amd_zynq_support.zynq_base_model import Zynq_Base_Model


class Zynq_AMD_FSBL_Model(Zynq_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: ZynqMP_AMD_FSBL_Blocks_Model
