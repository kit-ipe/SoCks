from pydantic import ConfigDict

from amd_zynqmp_builders.zynqmp_amd_atf_model import AMD_ATF_Blocks_Model
from socks.versal_base_model import Versal_Base_Model


class Versal_AMD_ATF_Model(Versal_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: AMD_ATF_Blocks_Model
