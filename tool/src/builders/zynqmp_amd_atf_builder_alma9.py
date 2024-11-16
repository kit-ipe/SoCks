import sys
import pathlib
import urllib

import socks.pretty_print as pretty_print
from builders.builder import Builder
from builders.zynqmp_amd_atf_model import ZynqMP_AMD_ATF_Model


class ZynqMP_AMD_ATF_Builder_Alma9(Builder):
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
    ):

        super().__init__(
            project_cfg=project_cfg,
            project_cfg_files=project_cfg_files,
            model_class=ZynqMP_AMD_ATF_Model,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
        )

        # Project directories
        if self._local_source_dir is not None:
            # Local project sources are used for this block
            self._repo_dir = self._local_source_dir
            self._source_repo_dir = self._local_source_dir
        elif self._source_repo is not None:
            # Online project sources are used for this block
            self._source_repo_dir = (
                self._repo_dir
                / f"{pathlib.Path(urllib.parse.urlparse(url=self._source_repo['url']).path).stem}-{self._source_repo['branch']}"
            )
        else:
            raise ValueError(f"No project source for block '{self.block_id}'")

        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        self.block_cmds = {"prepare": [], "build": [], "clean": [], "create-patches": [], "start-container": []}
        self.block_cmds["clean"].extend(
            [
                self.build_container_image,
                self.clean_download,
                self.clean_work,
                self.clean_repo,
                self.clean_output,
                self.clean_block_temp,
            ]
        )
        if self.block_cfg.source == "build":
            self.block_cmds["prepare"].extend([self.build_container_image, self.init_repo, self.apply_patches])
            self.block_cmds["build"].extend(self.block_cmds["prepare"])
            self.block_cmds["build"].extend([self.build_atf, self.export_block_package])
            self.block_cmds["create-patches"].extend([self.create_patches])
            self.block_cmds["start-container"].extend([self.build_container_image, self.start_container])
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
        if not ZynqMP_AMD_ATF_Builder_Alma9._check_rebuild_required(
            src_search_list=[self._patch_dir, self._source_repo_dir],
            src_ignore_list=[self._source_repo_dir / "build"],
            out_search_list=[
                self._source_repo_dir / "build/zynqmp/release/bl31/bl31.elf",
                self._source_repo_dir / "build/zynqmp/release/bl31.bin",
            ],
        ):
            pretty_print.print_build("No need to rebuild the ATF. No altered source files detected...")
            return

        pretty_print.print_build("Building the ATF...")

        atf_build_commands = (
            f"'cd {self._source_repo_dir} && "
            "make distclean && "
            "make CROSS_COMPILE=aarch64-none-elf- PLAT=zynqmp RESET_TO_BL31=1 ZYNQMP_CONSOLE=cadence0'"
        )

        self.run_containerizable_sh_command(
            command=atf_build_commands, dirs_to_mount=[(self._repo_dir, "Z"), (self._output_dir, "Z")]
        )

        # Create symlinks to the output files
        (self._output_dir / "bl31.elf").unlink(missing_ok=True)
        (self._output_dir / "bl31.elf").symlink_to(self._source_repo_dir / "build/zynqmp/release/bl31/bl31.elf")
        (self._output_dir / "bl31.bin").unlink(missing_ok=True)
        (self._output_dir / "bl31.bin").symlink_to(self._source_repo_dir / "build/zynqmp/release/bl31.bin")
