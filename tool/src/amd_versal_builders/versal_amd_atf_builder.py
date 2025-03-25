import pathlib
import inspect

import socks.pretty_print as pretty_print
from socks.build_validator import Build_Validator
from amd_zynqmp_builders.zynqmp_amd_atf_builder import ZynqMP_AMD_ATF_Builder
from amd_versal_builders.versal_amd_atf_model import Versal_AMD_ATF_Model


class Versal_AMD_ATF_Builder(ZynqMP_AMD_ATF_Builder):
    """
    AMD ATF builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "atf",
        block_description: str = "Build the ARM Trusted Firmware for Versal devices",
        model_class: type[object] = Versal_AMD_ATF_Model,
    ):

        super().__init__(
            project_cfg=project_cfg,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
            model_class=model_class,
        )

    def build_atf(self):
        """
        Builds the ATF.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check whether the ATF needs to be built
        if not Build_Validator.check_rebuild_bc_timestamp(
            src_search_list=[self._source_repo_dir],
            src_ignore_list=[self._source_repo_dir / "build"],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ):
            pretty_print.print_build("No need to rebuild the ATF. No altered source files detected...")
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            # Remove old build artifacts
            (self._output_dir / "bl31.elf").unlink(missing_ok=True)
            (self._output_dir / "bl31.bin").unlink(missing_ok=True)

            pretty_print.print_build("Building the ATF...")

            atf_build_commands = [
                f"cd {self._source_repo_dir}",
                "make distclean",
                "make CROSS_COMPILE=aarch64-none-elf- PLAT=versal RESET_TO_BL31=1 ZYNQMP_CONSOLE=pl011_0",
            ]

            self.container_executor.exec_sh_commands(
                commands=atf_build_commands,
                dirs_to_mount=[(self._repo_dir, "Z")],
                print_commands=True,
                logfile=self._block_temp_dir / "build.log",
                output_scrolling=True,
            )

            # Create symlinks to the output files
            (self._output_dir / "bl31.elf").symlink_to(self._source_repo_dir / "build/versal/release/bl31/bl31.elf")
            (self._output_dir / "bl31.bin").symlink_to(self._source_repo_dir / "build/versal/release/bl31.bin")
