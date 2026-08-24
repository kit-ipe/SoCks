import pathlib

from abstract_builders.builder import Builder
from amd_zynqmp_support.zynqmp_amd_uboot_ssbl_builder import ZynqMP_AMD_UBoot_SSBL_Builder
from amd_versal_support.versal_amd_uboot_ssbl_model import Versal_AMD_UBoot_SSBL_Model


class Versal_AMD_UBoot_SSBL_Builder(ZynqMP_AMD_UBoot_SSBL_Builder):
    """
    AMD U-Boot builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "ssbl",
        block_description: str = "Build the official AMD/Xilinx version of U-Boot for Versal devices",
        model_class: type[object] = Versal_AMD_UBoot_SSBL_Model,
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
            # Environment variable SOCKS_AARCH64_CROSS_COMPILE can be empty, but it must be defined in the build environment
            'if [ ! -n "${SOCKS_AARCH64_CROSS_COMPILE+x}" ]; then '
            '    echo "ERROR: Environment variable SOCKS_AARCH64_CROSS_COMPILE not defined"; '
            "    exit 1; "
            "fi",
            "export CROSS_COMPILE=$SOCKS_AARCH64_CROSS_COMPILE",
            "export ARCH=aarch64",
            "make xilinx_versal_virt_defconfig",
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
            prep_env_commands=[
                # Environment variable SOCKS_AARCH64_CROSS_COMPILE can be empty, but it must be defined in the build environment
                'if [ ! -n "${SOCKS_AARCH64_CROSS_COMPILE+x}" ]; then '
                '    echo "ERROR: Environment variable SOCKS_AARCH64_CROSS_COMPILE not defined"; '
                "    exit 1; "
                "fi",
                "export CROSS_COMPILE=$SOCKS_AARCH64_CROSS_COMPILE",
                "export ARCH=aarch64",
            ],
            defconfig_target="xilinx_versal_virt_defconfig",
        )

    def attach_config_snippets(self):
        """
        Iterates over all snippets listed in the project configuration file and attaches them to .config.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        self._attach_config_snippets(
            prep_env_commands=[
                # Environment variable SOCKS_AARCH64_CROSS_COMPILE can be empty, but it must be defined in the build environment
                'if [ ! -n "${SOCKS_AARCH64_CROSS_COMPILE+x}" ]; then '
                '    echo "ERROR: Environment variable SOCKS_AARCH64_CROSS_COMPILE not defined"; '
                "    exit 1; "
                "fi",
                "export CROSS_COMPILE=$SOCKS_AARCH64_CROSS_COMPILE",
                "export ARCH=aarch64",
            ]
        )
