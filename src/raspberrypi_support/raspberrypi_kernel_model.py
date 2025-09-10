from pydantic import ConfigDict

from amd_zynqmp_support.zynqmp_amd_kernel_model import AMD_Kernel_Blocks_Model
from raspberrypi_support.raspberrypi_base_model import RaspberryPi_Base_Model


class RaspberryPi_Kernel_Model(RaspberryPi_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: AMD_Kernel_Blocks_Model
