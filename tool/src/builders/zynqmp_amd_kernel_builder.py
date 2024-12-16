import sys
import pathlib
import urllib
import inspect

import socks.pretty_print as pretty_print
from builders.builder import Builder
from builders.zynqmp_amd_kernel_model import ZynqMP_AMD_Kernel_Model


class ZynqMP_AMD_Kernel_Builder(Builder):
    """
    AMD Kernel builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        project_cfg_files: list,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "kernel",
        block_description: str = "Build the official AMD/Xilinx version of the Linux Kernel for ZynqMP devices",
    ):

        super().__init__(
            project_cfg=project_cfg,
            project_cfg_files=project_cfg_files,
            model_class=ZynqMP_AMD_Kernel_Model,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
        )

        # Project files
        # File for version & build info tracking
        self._build_info_file = self._source_repo_dir / "include" / "build_info.h"
        # Kernel configuration file
        self._kernel_cfg_file = self._source_repo_dir / ".config"
        # Kernel modules output file
        self._modules_out_file = self._output_dir / "kernel_modules.tar.gz"

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
                self.clean_output,
                self.clean_block_temp,
            ]
        )
        if self.block_cfg.source == "build":
            self.block_cmds["prepare"].extend(
                [
                    self.container_executor.build_container_image,
                    self.init_repo,
                    self.apply_patches,
                    self.import_clean_srcs,
                ]
            )
            self.block_cmds["build"].extend(self.block_cmds["prepare"])
            self.block_cmds["build"].extend([self.build_kernel, self.export_modules, self.export_block_package])
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
            "make ARCH=arm64 menuconfig",
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
            "make ARCH=arm64 xilinx_zynqmp_defconfig",
            'printf "\n# Do not ignore the config file\n!.config\n" >> .gitignore',
        ]

        super()._prep_clean_srcs(prep_srcs_commands=prep_srcs_commands)

    def build_kernel(self):
        """
        Builds the Linux Kernel.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check whether the Kernel needs to be built
        if not ZynqMP_AMD_Kernel_Builder._check_rebuild_required(
            src_search_list=self._project_cfg_files + [self._source_repo_dir],
            src_ignore_list=[self._source_repo_dir / "arch/arm64/boot"],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ):
            pretty_print.print_build("No need to rebuild the Linux Kernel. No altered source files detected...")
            return

        # Remove old build artifacts
        (self._output_dir / "Image").unlink(missing_ok=True)
        (self._output_dir / "Image.gz").unlink(missing_ok=True)

        pretty_print.print_build("Building Linux Kernel...")

        if self.block_cfg.project.add_build_info == True:
            # Add build information file
            with self._build_info_file.open("w") as f:
                print('const char *build_info = "', file=f, end="")
                print(self._compose_build_info().replace("\n", "\\n"), file=f, end="")
                print('";', file=f, end="")
        else:
            # Remove existing build information file
            self._build_info_file.unlink(missing_ok=True)

        kernel_build_commands = [
            f"cd {self._source_repo_dir}",
            "export CROSS_COMPILE=aarch64-linux-gnu-",
            "make ARCH=arm64 olddefconfig",
            f"make ARCH=arm64 -j{self.project_cfg.external_tools.make.max_build_threads}",
        ]

        self.container_executor.exec_sh_commands(
            commands=kernel_build_commands,
            dirs_to_mount=[(self._repo_dir, "Z")],
            logfile=self._block_temp_dir / "build.log",
            output_scrolling=True,
        )

        # Create symlink to the output files
        (self._output_dir / "Image").symlink_to(self._source_repo_dir / "arch/arm64/boot/Image")
        (self._output_dir / "Image.gz").symlink_to(self._source_repo_dir / "arch/arm64/boot/Image.gz")

        # Log success of this function
        self._build_log.log_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")

    def export_modules(self):
        """
        Exports all built Kernel modules.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check if Kernel sources are available
        if not self._source_repo_dir.is_dir():
            pretty_print.print_build("No output files to extract Kernel modules...")
            return

        # Check if the Kernel was built with loadable module support
        with self._kernel_cfg_file.open("r") as f:
            kernel_cfg = f.readlines()
        if "CONFIG_MODULES=y\n" not in kernel_cfg:
            pretty_print.print_info(
                "Support for loadable modules is not activated in the Kernel configuration. Therefore, no Kernel modules are exported."
            )
            self._modules_out_file.unlink(missing_ok=True)
            return

        # Check whether the Kernel modules need to be exported
        if not ZynqMP_AMD_Kernel_Builder._check_rebuild_required(
            src_search_list=[self._source_repo_dir],
            src_ignore_list=[self._source_repo_dir / "arch/arm64/boot"],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ):
            pretty_print.print_build("No need to export Kernel modules. No altered source files detected...")
            return

        # Remove old build artifacts
        self._modules_out_file.unlink(missing_ok=True)

        pretty_print.print_build("Exporting Kernel Modules...")

        export_modules_commands = [
            f"cd {self._source_repo_dir}",
            "export CROSS_COMPILE=aarch64-linux-gnu-",
            f"make ARCH=arm64 modules_install INSTALL_MOD_PATH={self._output_dir}",
            f"find {self._output_dir}/lib -type l -delete",
            f"tar -P --xform='s:{self._output_dir}::' --numeric-owner -p -czf {self._modules_out_file} {self._output_dir}/lib",
            f"rm -rf {self._output_dir}/lib",
        ]

        self.container_executor.exec_sh_commands(
            commands=export_modules_commands, dirs_to_mount=[(self._repo_dir, "Z"), (self._output_dir, "Z")]
        )

        # Log success of this function
        self._build_log.log_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")
