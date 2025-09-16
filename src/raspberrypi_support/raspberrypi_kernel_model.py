from pydantic import ConfigDict

from abstract_builders.linux_kernel_model import Linux_Kernel_Blocks_Model
from raspberrypi_support.raspberrypi_base_model import RaspberryPi_Base_Model


class RaspberryPi_Kernel_Model(RaspberryPi_Base_Model):
    model_config = ConfigDict(extra="forbid", strict=True)

    blocks: Linux_Kernel_Blocks_Model
