from pydantic import ConfigDict

from abstract_builders.linux_kernel_model import Linux_Kernel_Blocks_Model
from amd_versal_support.versal_base_model import Versal_Base_Model


class Versal_AMD_Kernel_Model(Versal_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: Linux_Kernel_Blocks_Model
