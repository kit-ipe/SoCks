import pathlib

from abstract_builders.builder import Builder
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

    def init_repo(self):
        """
        Clones and initializes the git repo.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        Builder.init_repo(self)  # Skip init function of the direct parent (zynqmp builder)

        create_defconfig_commands = [
            f"cd {self._source_repo_dir}",
            "export CROSS_COMPILE=aarch64-linux-gnu-",
            "export ARCH=arm64",
            "make xilinx_versal_defconfig",
        ]

        self._prep_clean_cfg(prep_srcs_commands=create_defconfig_commands)

    def create_config_snippet(self):
        """
        Creates snippets from changes in .config.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        self._create_config_snippet(
            cross_comp_prefix="aarch64-linux-gnu-", arch="arm64", defconfig_target="xilinx_versal_defconfig"
        )

    def attach_config_snippets(self):
        """
        This function iterates over all snippets listed in the project configuration file and attaches them to .config.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        self._attach_config_snippets(cross_comp_prefix="aarch64-linux-gnu-", arch="arm64")
