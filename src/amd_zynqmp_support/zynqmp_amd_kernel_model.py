from pydantic import ConfigDict

from abstract_builders.linux_kernel_model import Linux_Kernel_Blocks_Model
from amd_zynqmp_support.zynqmp_base_model import ZynqMP_Base_Model


class ZynqMP_AMD_Kernel_Model(ZynqMP_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: Linux_Kernel_Blocks_Model
