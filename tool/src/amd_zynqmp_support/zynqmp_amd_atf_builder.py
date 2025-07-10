import pathlib
import inspect

import socks.pretty_print as pretty_print
from socks.build_validator import Build_Validator
from abstract_builders.builder import Builder
from amd_zynqmp_support.zynqmp_amd_atf_model import ZynqMP_AMD_ATF_Model


class ZynqMP_AMD_ATF_Builder(Builder):
    """
    AMD ATF builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "atf",
        block_description: str = "Build the ARM Trusted Firmware for ZynqMP devices",
        model_class: type[object] = ZynqMP_AMD_ATF_Model,
    ):

        super().__init__(
            project_cfg=project_cfg,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
            model_class=model_class,
        )

    @property
    def _block_deps(self):
        # Products of other blocks on which this block depends
        # This dict is used to check whether the imported block packages contain
        # all the required files. Regex can be used to describe the expected files.
        # Optional dependencies can also be listed here. They will be ignored if
        # they are not listed in the project configuration.
        block_deps = None
        return block_deps

    @property
    def block_cmds(self):
        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        block_cmds = {"prepare": [], "build": [], "clean": [], "create-patches": [], "start-container": []}
        block_cmds["clean"].extend(
            [
                self.container_executor.build_container_image,
                self.clean_download,
                self.clean_work,
                self.clean_repo,
                self.clean_output,
                self.clean_block_temp,
            ]
        )
        if self.block_cfg.source == "build":
            block_cmds["prepare"].extend(
                [
                    self._build_validator.del_project_cfg,
                    self.container_executor.build_container_image,
                    self.init_repo,
                    self.apply_patches,
                    self._build_validator.save_project_cfg_prepare,
                ]
            )
            block_cmds["build"].extend(block_cmds["prepare"])
            block_cmds["build"].extend(
                [self.build_atf, self.export_block_package, self._build_validator.save_project_cfg_build]
            )
            block_cmds["create-patches"].extend([self.create_patches])
            block_cmds["start-container"].extend([self.container_executor.build_container_image, self.start_container])
        elif self.block_cfg.source == "import":
            block_cmds["build"].extend([self.container_executor.build_container_image, self.import_prebuilt])
        return block_cmds

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
                "make CROSS_COMPILE=aarch64-none-elf- PLAT=zynqmp RESET_TO_BL31=1 ZYNQMP_CONSOLE=cadence0",
            ]

            self.container_executor.exec_sh_commands(
                commands=atf_build_commands,
                dirs_to_mount=[(self._repo_dir, "Z")],
                print_commands=True,
                logfile=self._block_temp_dir / "build.log",
                output_scrolling=True,
            )

            # Create symlinks to the output files
            (self._output_dir / "bl31.elf").symlink_to(self._source_repo_dir / "build/zynqmp/release/bl31/bl31.elf")
            (self._output_dir / "bl31.bin").symlink_to(self._source_repo_dir / "build/zynqmp/release/bl31.bin")
