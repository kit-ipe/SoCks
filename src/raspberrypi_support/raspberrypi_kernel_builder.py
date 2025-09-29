import sys
import pathlib
import inspect

import socks.pretty_print as pretty_print
from socks.build_validator import Build_Validator
from abstract_builders.builder import Builder
from amd_zynqmp_support.zynqmp_amd_kernel_builder import ZynqMP_AMD_Kernel_Builder
from raspberrypi_support.raspberrypi_kernel_model import RaspberryPi_Kernel_Model


class RaspberryPi_Kernel_Builder(ZynqMP_AMD_Kernel_Builder):
    """
    Raspberry Pi Kernel builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "kernel",
        block_description: str = "Build the official Raspberry Pi version of the Linux Kernel",
        model_class: type[object] = RaspberryPi_Kernel_Model,
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
        if not Build_Validator.check_rebuild_bc_timestamp(
            src_search_list=[self._source_repo_dir],
            src_ignore_list=[self._source_repo_dir / "arch/arm64/boot"],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ) and not self._build_validator.check_rebuild_bc_config(
            keys=[["blocks", self.block_id, "project", "add_build_info"]]
        ):
            pretty_print.print_build("No need to rebuild the Linux Kernel. No altered source files detected...")
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            # Remove old build artifacts
            (self._output_dir / "Image").unlink(missing_ok=True)
            (self._output_dir / "Image.gz").unlink(missing_ok=True)
            if self.project_cfg.project.rpi_model == "RPi_4B":
                (self._output_dir / "bcm2711-rpi-4-b.dtb").unlink(missing_ok=True)
            elif self.project_cfg.project.rpi_model == "RPi_5":
                (self._output_dir / "bcm2712d0-rpi-5-b.dtb").unlink(missing_ok=True)
                (self._output_dir / "bcm2712-d-rpi-5-b.dtb").unlink(missing_ok=True)
                (self._output_dir / "bcm2712-rpi-5-b.dtb").unlink(missing_ok=True)
            else:
                raise ValueError(
                    f"The following Raspberry Pi Model is not supported: '{self.project_cfg.project.rpi_model}'"
                )

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
                "export ARCH=arm64",
                "make olddefconfig",
                f"make -j{self.project_cfg.external_tools.make.max_build_threads}",
            ]

            self.container_executor.exec_sh_commands(
                commands=kernel_build_commands,
                dirs_to_mount=[(self._repo_dir, "Z")],
                print_commands=True,
                logfile=self._block_temp_dir / "build.log",
                output_scrolling=True,
            )

            # Create symlink to the output files
            (self._output_dir / "Image").symlink_to(self._source_repo_dir / "arch/arm64/boot/Image")
            (self._output_dir / "Image.gz").symlink_to(self._source_repo_dir / "arch/arm64/boot/Image.gz")
            if self.project_cfg.project.rpi_model == "RPi_4B":
                (self._output_dir / "bcm2711-rpi-4-b.dtb").symlink_to(
                    self._source_repo_dir / "arch/arm64/boot/dts/broadcom/bcm2711-rpi-4-b.dtb"
                )
            elif self.project_cfg.project.rpi_model == "RPi_5":
                (self._output_dir / "bcm2712d0-rpi-5-b.dtb").symlink_to(
                    self._source_repo_dir / "arch/arm64/boot/dts/broadcom/bcm2712d0-rpi-5-b.dtb"
                )
                (self._output_dir / "bcm2712-d-rpi-5-b.dtb").symlink_to(
                    self._source_repo_dir / "arch/arm64/boot/dts/broadcom/bcm2712-d-rpi-5-b.dtb"
                )
                (self._output_dir / "bcm2712-rpi-5-b.dtb").symlink_to(
                    self._source_repo_dir / "arch/arm64/boot/dts/broadcom/bcm2712-rpi-5-b.dtb"
                )
            else:
                raise ValueError(
                    f"The following Raspberry Pi Model is not supported: '{self.project_cfg.project.rpi_model}'"
                )
