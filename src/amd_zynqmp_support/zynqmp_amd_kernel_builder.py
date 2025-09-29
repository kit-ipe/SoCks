import pathlib

from abstract_builders.linux_kernel_builder import Linux_Kernel_Builder
from amd_zynqmp_support.zynqmp_amd_kernel_model import ZynqMP_AMD_Kernel_Model


class ZynqMP_AMD_Kernel_Builder(Linux_Kernel_Builder):
    """
    AMD Linux kernel builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "kernel",
        block_description: str = "Build the official AMD/Xilinx version of the Linux kernel for ZynqMP devices",
        model_class: type[object] = ZynqMP_AMD_Kernel_Model,
    ):

        super().__init__(
            project_cfg=project_cfg,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
            model_class=model_class,
        )
