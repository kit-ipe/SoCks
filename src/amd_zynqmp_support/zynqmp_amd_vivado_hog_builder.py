import sys
import pathlib
import urllib
import inspect

import socks.pretty_print as pretty_print
from socks.build_validator import Build_Validator
from abstract_builders.amd_builder import AMD_Builder
from amd_zynqmp_support.zynqmp_amd_vivado_hog_model import ZynqMP_AMD_Vivado_Hog_Model


class ZynqMP_AMD_Vivado_Hog_Builder(AMD_Builder):
    """
    Builder class for AMD Vivado projects utilizing the Hog framework
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "vivado",
        block_description: str = "Build an AMD/Xilinx Vivado Project with HDL on git (Hog)",
        model_class: type[object] = ZynqMP_AMD_Vivado_Hog_Model,
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
        block_cmds = {"prepare": [], "build": [], "clean": [], "start-container": [], "start-vivado-gui": []}
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
                    self.create_vivado_project,
                    self._build_validator.save_project_cfg_prepare,
                ]
            )
            block_cmds["build"].extend(block_cmds["prepare"])
            block_cmds["build"].extend(
                [self.build_vivado_project, self.export_block_package, self._build_validator.save_project_cfg_build]
            )
            block_cmds["start-container"].extend([self.container_executor.build_container_image, self.start_container])
            block_cmds["start-vivado-gui"].extend(
                [self.container_executor.build_container_image, self.start_vivado_gui]
            )
        elif self.block_cfg.source == "import":
            block_cmds["build"].extend([self.container_executor.build_container_image, self.import_prebuilt])
        return block_cmds

    def create_vivado_project(self):
        """
        Create the Vivado project utilizing the Hog framework.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check if the Vivado project needs to be created
        if (self._source_repo_dir / "Projects" / self.block_cfg.project.name).is_dir():
            pretty_print.print_build("The Vivado Project already exists. It will not be recreated...")
            return

        self.check_amd_tools(required_tools=["vivado"])

        pretty_print.print_build("Creating the Vivado Project...")

        create_vivado_project_commands = [
            f"export XILINXD_LICENSE_FILE={self._amd_license}",
            f"source {self._amd_vivado_path}/settings64.sh",
            f"git config --global --add safe.directory {self._source_repo_dir}",
            f"git config --global --add safe.directory {self._source_repo_dir}/Hog",
            f"{self._source_repo_dir}/Hog/Do CREATE {self.block_cfg.project.name}",
        ]

        self.container_executor.exec_sh_commands(
            commands=create_vivado_project_commands,
            dirs_to_mount=[(pathlib.Path(self._amd_tools_path), "ro"), (self._repo_dir, "Z")],
            print_commands=True,
            logfile=self._block_temp_dir / "build_project.log",
            output_scrolling=True,
        )

    def build_vivado_project(self):
        """
        Builds the Vivado Project.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check if the project needs to be build
        if not Build_Validator.check_rebuild_bc_timestamp(
            src_search_list=[
                self._source_repo_dir / "Top",
                self._source_repo_dir / "Hog",
                self._source_repo_dir / f"lib_{self.block_cfg.project.name}",
            ],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ) and not self._build_validator.check_rebuild_bc_config(
            keys=[["external_tools", "xilinx"], ["blocks", self.block_id, "project", "name"]]
        ):
            pretty_print.print_build("No need to rebuild the Vivado Project. No altered source files detected...")
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            self.check_amd_tools(required_tools=["vivado"])

            # Clean output directory
            self.clean_output()
            self._output_dir.mkdir(parents=True)

            pretty_print.print_build("Building the Vivado Project...")

            vivado_build_commands = [
                f"rm -rf {self._source_repo_dir}/bin",
                f"export XILINXD_LICENSE_FILE={self._amd_license}",
                f"source {self._amd_vivado_path}/settings64.sh",
                f"git config --global --add safe.directory {self._source_repo_dir}",
                f"git config --global --add safe.directory {self._source_repo_dir}/Hog",
                f"{self._source_repo_dir}/Hog/Do WORKFLOW {self.block_cfg.project.name}",
            ]

            self.container_executor.exec_sh_commands(
                commands=vivado_build_commands,
                dirs_to_mount=[(pathlib.Path(self._amd_tools_path), "ro"), (self._repo_dir, "Z")],
                print_commands=True,
                logfile=self._block_temp_dir / "build.log",
                output_scrolling=True,
            )

            # Create symlinks to the output files
            xsa_files = list(
                self._source_repo_dir.glob(f"bin/{self.block_cfg.project.name}-*/{self.block_cfg.project.name}-*.xsa")
            )
            if len(xsa_files) != 1:
                pretty_print.print_error(
                    f"Unexpected number of {len(xsa_files)} *.xsa files in output directory. Expected was 1."
                )
                sys.exit(1)
            (self._output_dir / xsa_files[0].name).symlink_to(xsa_files[0])

    def start_vivado_gui(self):
        """
        Starts Vivado in GUI mode in the container.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        self.check_amd_tools(required_tools=["vivado"])

        start_vivado_gui_commands = [
            f"export XILINXD_LICENSE_FILE={self._amd_license}",
            f"source {self._amd_vivado_path}/settings64.sh",
            f"vivado -nojournal -nolog {self._source_repo_dir}/Projects/{self.block_cfg.project.name}/{self.block_cfg.project.name}.xpr",
            f"exit",
        ]

        self.container_executor.start_gui_container(
            start_gui_commands=start_vivado_gui_commands,
            potential_mounts=[
                (pathlib.Path(self._amd_tools_path), "ro"),
                (self._repo_dir, "Z"),
                (self._output_dir, "Z"),
            ],
        )
