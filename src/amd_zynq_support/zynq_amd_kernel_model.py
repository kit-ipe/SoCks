from pydantic import ConfigDict

from abstract_builders.linux_kernel_model import Linux_Kernel_Blocks_Model
from amd_zynq_support.zynq_base_model import Zynq_Base_Model


class Zynq_AMD_Kernel_Model(Zynq_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: Linux_Kernel_Blocks_Model
