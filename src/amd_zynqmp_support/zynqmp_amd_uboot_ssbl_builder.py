import sys
import pathlib
import shutil
import urllib
import hashlib
import inspect

import socks.pretty_print as pretty_print
from socks.build_validator import Build_Validator
from abstract_builders.builder import Builder
from amd_zynqmp_support.zynqmp_amd_uboot_ssbl_model import ZynqMP_AMD_UBoot_SSBL_Model


class ZynqMP_AMD_UBoot_SSBL_Builder(Builder):
    """
    AMD U-Boot builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "ssbl",
        block_description: str = "Build the official AMD/Xilinx version of U-Boot for ZynqMP devices",
        model_class: type[object] = ZynqMP_AMD_UBoot_SSBL_Model,
    ):

        super().__init__(
            project_cfg=project_cfg,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
            model_class=model_class,
        )

        # Project files
        # File for version & build info tracking
        self._build_info_file = self._source_repo_dir / "include" / "build_info.h"

    @property
    def _block_deps(self):
        # Products of other blocks on which this block depends
        # This dict is used to check whether the imported block packages contain
        # all the required files. Regex can be used to describe the expected files.
        # Optional dependencies can also be listed here. They will be ignored if
        # they are not listed in the project configuration.
        block_deps = {"atf": ["bl31.bin"]}
        return block_deps

    @property
    def block_cmds(self):
        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        block_cmds = {
            "prepare": [],
            "build": [],
            "clean": [],
            "create-patches": [],
            "create-cfg-snippet": [],
            "start-container": [],
            "menucfg": [],
        }
        block_cmds["clean"].extend(
            [
                self.container_executor.build_container_image,
                self.clean_download,
                self.clean_work,
                self.clean_repo,
                self.clean_dependencies,
                self.clean_output,
                self.clean_block_temp,
            ]
        )
        if self.block_cfg.source == "build":
            block_cmds["prepare"].extend(
                [
                    self._build_validator.del_project_cfg,
                    self.container_executor.build_container_image,
                    self.import_dependencies,
                    self.init_repo,
                    self.apply_patches,
                    self.attach_config_snippets,
                    self.copy_atf,
                    self._build_validator.save_project_cfg_prepare,
                ]
            )
            block_cmds["build"].extend(block_cmds["prepare"])
            block_cmds["build"].extend(
                [self.build_uboot, self.export_block_package, self._build_validator.save_project_cfg_build]
            )
            block_cmds["create-patches"].extend([self.create_patches])
            block_cmds["create-cfg-snippet"].extend([self.create_config_snippet])
            block_cmds["start-container"].extend([self.container_executor.build_container_image, self.start_container])
            block_cmds["menucfg"].extend([self.container_executor.build_container_image, self.run_menuconfig])
        elif self.block_cfg.source == "import":
            block_cmds["build"].extend([self.container_executor.build_container_image, self.import_prebuilt])
        return block_cmds

    def validate_srcs(self):
        """
        Check whether all sources required to build this block are present.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        super().validate_srcs()

    def run_menuconfig(self):
        """
        Opens the menuconfig tool to enable interactive configuration of the project.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        menuconfig_commands = [
            f"cd {self._source_repo_dir}",
            "export CROSS_COMPILE=aarch64-linux-gnu-",
            "export ARCH=aarch64",
            "make menuconfig",
        ]

        self._run_menuconfig(menuconfig_commands=menuconfig_commands)

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

        super().init_repo()

        create_defconfig_commands = [
            f"cd {self._source_repo_dir}",
            "export CROSS_COMPILE=aarch64-linux-gnu-",
            "export ARCH=aarch64",
            "make xilinx_zynqmp_virt_defconfig",
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
            cross_comp_prefix="aarch64-linux-gnu-", arch="aarch64", defconfig_target="xilinx_zynqmp_virt_defconfig"
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

        self._attach_config_snippets(cross_comp_prefix="aarch64-linux-gnu-", arch="aarch64")

    def copy_atf(self):
        """
        Copy a ATF bl31.bin file into the U-Boot project. U-Boot will be built to run in exception
        level EL2 if bl31.bin is present in the root directory of the U-Boot project. Otherwise it
        will be built to run in exception level EL3.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        bl31_bin_path = self._dependencies_dir / "atf" / "bl31.bin"

        # Check whether the specified file exists
        if not bl31_bin_path.is_file():
            pretty_print.print_error(f"The following file was not found: {bl31_bin_path}")
            sys.exit(1)

        # Calculate md5 of the provided file
        md5_new_file = hashlib.md5(bl31_bin_path.read_bytes()).hexdigest()
        # Calculate md5 of the existing file, if it exists
        md5_existsing_file = 0
        if (self._source_repo_dir / "bl31.bin").is_file():
            md5_existsing_file = hashlib.md5((self._source_repo_dir / "bl31.bin").read_bytes()).hexdigest()
        # Copy the specified file if it is not identical to the existing file
        if md5_existsing_file != md5_new_file:
            shutil.copy(bl31_bin_path, self._source_repo_dir / bl31_bin_path.name)
        else:
            pretty_print.print_info(
                "No new 'bl31.bin' recognized. The file that already exists in the target directory will be used."
            )

    def build_uboot(self):
        """
        Builds das U-Boot.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check whether das U-Boot needs to be built
        if not Build_Validator.check_rebuild_bc_timestamp(
            src_search_list=[self._source_repo_dir],
            src_ignore_list=[self._source_repo_dir / "u-boot.elf", self._source_repo_dir / "spl/.boot.bin.cmd"],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ) and not self._build_validator.check_rebuild_bc_config(
            keys=[["blocks", self.block_id, "project", "add_build_info"]]
        ):
            pretty_print.print_build("No need to rebuild U-Boot. No altered source files detected...")
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            # Remove old build artifacts
            (self._output_dir / "u-boot.elf").unlink(missing_ok=True)

            pretty_print.print_build("Building U-Boot...")

            if self.block_cfg.project.add_build_info == True:
                # Add build information file
                with self._build_info_file.open("w") as f:
                    print('const char *build_info = "', file=f, end="")
                    c_compatible_build_info = self._compose_build_info().replace("\n", "\\n").replace('"', '\\"')
                    print(c_compatible_build_info, file=f, end="")
                    print('";', file=f, end="")
            else:
                # Remove existing build information file
                self._build_info_file.unlink(missing_ok=True)

            uboot_build_commands = [
                f"cd {self._source_repo_dir}",
                "export CROSS_COMPILE=aarch64-linux-gnu-",
                "export ARCH=aarch64",
                "make olddefconfig",
                f"make -j{self.project_cfg.external_tools.make.max_build_threads}",
            ]

            self.container_executor.exec_sh_commands(
                commands=uboot_build_commands,
                dirs_to_mount=[(self._repo_dir, "Z")],
                print_commands=True,
                logfile=self._block_temp_dir / "build.log",
                output_scrolling=True,
            )

            # Create symlink to the output file
            (self._output_dir / "u-boot.elf").symlink_to(self._source_repo_dir / "u-boot.elf")
