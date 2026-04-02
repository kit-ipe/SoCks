from pydantic import ConfigDict

from amd_zynqmp_support.zynqmp_amd_devicetree_model import AMD_Devicetree_Blocks_Model
from amd_zynq_support.zynq_base_model import Zynq_Base_Model


class Zynq_AMD_Devicetree_Model(Zynq_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: AMD_Devicetree_Blocks_Model
