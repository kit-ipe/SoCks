import sys
import pathlib
import inspect

import socks.pretty_print as pretty_print
from socks.build_validator import Build_Validator
from abstract_builders.builder import Builder
from amd_zynqmp_support.zynqmp_amd_uboot_ssbl_builder import ZynqMP_AMD_UBoot_SSBL_Builder
from raspberrypi_support.raspberrypi_uboot_ssbl_model import RaspberryPi_UBoot_SSBL_Model


class RaspberryPi_UBoot_SSBL_Builder(ZynqMP_AMD_UBoot_SSBL_Builder):
    """
    RaspberryPi U-Boot builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "ssbl",
        block_description: str = "Build the official AMD/Xilinx version of U-Boot for Versal devices",
        model_class: type[object] = RaspberryPi_UBoot_SSBL_Model,
    ):

        super().__init__(
            project_cfg=project_cfg,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
            model_class=model_class,
        )

        self.pre_action_warnings.append("This block is experimental, it should not be used for production.")

        # Project files
        # File for version & build info tracking
        self._rpi_model_file = self._block_temp_dir / "rpi_model.txt"

    @property
    def _block_deps(self):
        # Products of other blocks on which this block depends
        # This dict is used to check whether the imported block packages contain
        # all the required files. Regex can be used to describe the expected files.
        # Optional dependencies can also be listed here. They will be ignored if
        # they are not listed in the project configuration.
        block_deps = {}
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
                    self.attach_config_snippets,
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

        # Check whether this block is configured for the Raspberry Pi model specified in the project configuration
        try:
            with open(self._rpi_model_file, mode="r", newline="") as file:
                config_rpi_mode = file.readlines()[1].strip()

            if config_rpi_mode != self.project_cfg.project.rpi_model:
                pretty_print.print_error(
                    f"Configuration missmatch. Block '{self.block_id}' is configured for '{config_rpi_mode}', "
                    f"but the project cofiguration is for '{self.project_cfg.project.rpi_model}'.\n"
                    f"This is an unexpected state. Please clean and rebuild block '{self.block_id}'."
                )
                sys.exit(1)
        except FileNotFoundError:
            pass  # It is okay if the file does not exist

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
            "export ARCH=aarch64",
        ]

        if self.project_cfg.project.rpi_model == "RPi_4B":
            create_defconfig_commands.append("make rpi_4_defconfig")
        elif self.project_cfg.project.rpi_model == "RPi_5":
            create_defconfig_commands.append(
                "make rpi_arm64_defconfig"
            )  # Maybe there will be an update with newer releases
        else:
            raise ValueError(
                f"The following Raspberry Pi Model is not supported: '{self.project_cfg.project.rpi_model}'"
            )

        self._prep_clean_cfg(prep_srcs_commands=create_defconfig_commands)

        # Save the Raspberry Pi model for which the block is now configured to a file
        self._rpi_model_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._rpi_model_file, mode="w", newline="") as file:
            file.write(
                "# This file is autogenerated to validate the block configuration, "
                f"do not edit!\n{self.project_cfg.project.rpi_model}"
            )

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

        if self.project_cfg.project.rpi_model == "RPi_4B":
            self._create_config_snippet(
                cross_comp_prefix="aarch64-linux-gnu-", arch="arm64", defconfig_target="rpi_4_defconfig"
            )
        elif self.project_cfg.project.rpi_model == "RPi_5":
            self._create_config_snippet(
                cross_comp_prefix="aarch64-linux-gnu-", arch="arm64", defconfig_target="rpi_arm64_defconfig"
            )  # Maybe there will be an update with newer releases
        else:
            raise ValueError(
                f"The following Raspberry Pi Model is not supported: '{self.project_cfg.project.rpi_model}'"
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
            src_ignore_list=[self._source_repo_dir / "u-boot.bin", self._source_repo_dir / "spl/.boot.bin.cmd"],
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
            (self._output_dir / "u-boot.bin").unlink(missing_ok=True)

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
            (self._output_dir / "u-boot.bin").symlink_to(self._source_repo_dir / "u-boot.bin")
