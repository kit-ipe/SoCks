import pathlib

from amd_zynqmp_support.zynqmp_amd_kernel_builder import ZynqMP_AMD_Kernel_Builder
from amd_versal_support.versal_amd_kernel_model import Versal_AMD_Kernel_Model


class Versal_AMD_Kernel_Builder(ZynqMP_AMD_Kernel_Builder):
    """
    AMD Kernel builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "kernel",
        block_description: str = "Build the official AMD/Xilinx version of the Linux Kernel for Versal devices",
        model_class: type[object] = Versal_AMD_Kernel_Model,
    ):

        super().__init__(
            project_cfg=project_cfg,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
            model_class=model_class,
        )

    def prep_clean_srcs(self):
        """
        This function is intended to create a new, clean Linux kernel or U-Boot project. After the creation of the project you should create a patch that includes .gitignore and .config.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        prep_srcs_commands = [
            f"cd {self._source_repo_dir}",
            "export CROSS_COMPILE=aarch64-linux-gnu-",
            "make ARCH=arm64 xilinx_versal_defconfig",
            'printf "\n# Do not ignore the config file\n!.config\n" >> .gitignore',
        ]

        super()._prep_clean_srcs(prep_srcs_commands=prep_srcs_commands)
