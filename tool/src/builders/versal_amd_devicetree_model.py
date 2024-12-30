from pydantic import ConfigDict

from builders.zynqmp_amd_devicetree_model import AMD_Devicetree_Blocks_Model
from socks.versal_base_model import Versal_Base_Model


class Versal_AMD_Devicetree_Model(Versal_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: AMD_Devicetree_Blocks_Model
