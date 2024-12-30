import pathlib
import inspect

import socks.pretty_print as pretty_print
from builders.builder import Builder
from builders.zynqmp_amd_atf_model import ZynqMP_AMD_ATF_Model


class ZynqMP_AMD_ATF_Builder(Builder):
    """
    AMD ATF builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        project_cfg_files: list,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "atf",
        block_description: str = "Build the ARM Trusted Firmware for ZynqMP devices",
        model_class: type[object] = ZynqMP_AMD_ATF_Model,
    ):

        super().__init__(
            project_cfg=project_cfg,
            project_cfg_files=project_cfg_files,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
            model_class=model_class,
        )

        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        self.block_cmds = {"prepare": [], "build": [], "clean": [], "create-patches": [], "start-container": []}
        self.block_cmds["clean"].extend(
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
            self.block_cmds["prepare"].extend(
                [self.container_executor.build_container_image, self.init_repo, self.apply_patches]
            )
            self.block_cmds["build"].extend(self.block_cmds["prepare"])
            self.block_cmds["build"].extend([self.build_atf, self.export_block_package])
            self.block_cmds["create-patches"].extend([self.create_patches])
            self.block_cmds["start-container"].extend(
                [self.container_executor.build_container_image, self.start_container]
            )
        elif self.block_cfg.source == "import":
            self.block_cmds["build"].extend([self.import_prebuilt])

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
        if not ZynqMP_AMD_ATF_Builder._check_rebuild_required(
            src_search_list=[self._source_repo_dir],
            src_ignore_list=[self._source_repo_dir / "build"],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ):
            pretty_print.print_build("No need to rebuild the ATF. No altered source files detected...")
            return

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
            logfile=self._block_temp_dir / "build.log",
            output_scrolling=True,
        )

        # Create symlinks to the output files
        (self._output_dir / "bl31.elf").symlink_to(self._source_repo_dir / "build/zynqmp/release/bl31/bl31.elf")
        (self._output_dir / "bl31.bin").symlink_to(self._source_repo_dir / "build/zynqmp/release/bl31.bin")

        # Log success of this function
        self._build_log.log_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")
