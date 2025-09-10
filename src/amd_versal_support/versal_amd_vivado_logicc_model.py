from pydantic import ConfigDict

from amd_zynqmp_support.zynqmp_amd_vivado_logicc_model import ZynqMP_AMD_Vivado_logicc_Blocks_Model
from amd_versal_support.versal_base_model import Versal_Base_Model


class Versal_AMD_Vivado_logicc_Model(Versal_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: ZynqMP_AMD_Vivado_logicc_Blocks_Model
