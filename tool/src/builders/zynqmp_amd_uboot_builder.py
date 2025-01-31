import sys
import pathlib
import shutil
import urllib
import hashlib
import inspect

import socks.pretty_print as pretty_print
from builders.builder import Builder
from builders.zynqmp_amd_uboot_model import ZynqMP_AMD_UBoot_Model


class ZynqMP_AMD_UBoot_Builder(Builder):
    """
    AMD U-Boot builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "uboot",
        block_description: str = "Build the official AMD/Xilinx version of U-Boot for ZynqMP devices",
        model_class: type[object] = ZynqMP_AMD_UBoot_Model,
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

        # Products of other blocks on which this block depends
        # This dict is used to check whether the imported block packages contain
        # all the required files. Regex can be used to describe the expected files.
        # Optional dependencies can also be listed here. They will be ignored if
        # they are not listed in the project configuration.
        self._block_deps = {"atf": ["bl31.bin"]}

        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        self.block_cmds = {
            "prepare": [],
            "build": [],
            "clean": [],
            "create-patches": [],
            "start-container": [],
            "menucfg": [],
            "prep-clean-srcs": [],
        }
        self.block_cmds["clean"].extend(
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
            self.block_cmds["prepare"].extend(
                [
                    self.container_executor.build_container_image,
                    self.import_dependencies,
                    self.init_repo,
                    self.apply_patches,
                    self.import_clean_srcs,
                    self.copy_atf,
                    self.save_project_cfg_prepare,
                ]
            )
            self.block_cmds["build"].extend(self.block_cmds["prepare"][:-1])  # Remove save_project_cfg when adding
            self.block_cmds["build"].extend([self.build_uboot, self.export_block_package, self.save_project_cfg_build])
            self.block_cmds["create-patches"].extend([self.create_patches])
            self.block_cmds["start-container"].extend(
                [self.container_executor.build_container_image, self.start_container]
            )
            self.block_cmds["menucfg"].extend([self.container_executor.build_container_image, self.run_menuconfig])
            self.block_cmds["prep-clean-srcs"].extend(self.block_cmds["clean"])
            self.block_cmds["prep-clean-srcs"].extend(
                [self.container_executor.build_container_image, self.init_repo, self.prep_clean_srcs]
            )
        elif self.block_cfg.source == "import":
            self.block_cmds["build"].extend([self.import_prebuilt])

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

        if not self._block_src_dir.is_dir():
            self.pre_action_warnings.append(
                "This block requires source files, but none were found. "
                "If you proceed, SoCks will automatically generate clean sources and add them to your project."
            )
            # Function 'import_clean_srcs' is called with block command 'prepare' at a suitable stage.
            # Calling it here would not make sense, because the  repo might not be ready yet.

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

        super()._run_menuconfig(menuconfig_commands=menuconfig_commands)

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
            "export ARCH=aarch64",
            "make xilinx_zynqmp_virt_defconfig",
            'printf "\n# Do not ignore the config file\n!.config\n" >> .gitignore',
        ]

        super()._prep_clean_srcs(prep_srcs_commands=prep_srcs_commands)

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
        if not ZynqMP_AMD_UBoot_Builder._check_rebuild_bc_timestamp(
            src_search_list=[self._source_repo_dir],
            src_ignore_list=[self._source_repo_dir / "u-boot.elf", self._source_repo_dir / "spl/.boot.bin.cmd"],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ) and not self._check_rebuild_bc_config(keys=[["blocks", self.block_id, "project", "add_build_info"]]):
            pretty_print.print_build("No need to rebuild U-Boot. No altered source files detected...")
            return

        # Reset function success log
        self._build_log.del_logged_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")

        # Remove old build artifacts
        (self._output_dir / "u-boot.elf").unlink(missing_ok=True)

        pretty_print.print_build("Building U-Boot...")

        if self.block_cfg.project.add_build_info == True:
            # Add build information file
            with self._build_info_file.open("w") as f:
                print('const char *build_info = "', file=f, end="")
                print(self._compose_build_info().replace("\n", "\\n"), file=f, end="")
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
            logfile=self._block_temp_dir / "build.log",
            output_scrolling=True,
        )

        # Create symlink to the output file
        (self._output_dir / "u-boot.elf").symlink_to(self._source_repo_dir / "u-boot.elf")

        # Log success of this function
        self._build_log.log_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")
