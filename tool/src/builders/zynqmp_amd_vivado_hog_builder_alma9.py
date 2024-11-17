import sys
import pathlib
import urllib

import socks.pretty_print as pretty_print
from builders.amd_builder import AMD_Builder
from builders.zynqmp_amd_vivado_hog_model import ZynqMP_AMD_Vivado_Hog_Model


class ZynqMP_AMD_Vivado_Hog_Builder_Alma9(AMD_Builder):
    """
    Builder class for AMD Vivado projects utilizing the Hog framework
    """

    def __init__(
        self,
        project_cfg: dict,
        project_cfg_files: list,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "vivado",
        block_description: str = "Build an AMD/Xilinx Vivado Project with HDL on git (Hog)",
    ):

        super().__init__(
            project_cfg=project_cfg,
            project_cfg_files=project_cfg_files,
            model_class=ZynqMP_AMD_Vivado_Hog_Model,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
        )

        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        self.block_cmds = {"prepare": [], "build": [], "clean": [], "start-container": [], "start-vivado-gui": []}
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
            self.block_cmds["prepare"].extend([self.build_container_image, self.init_repo, self.create_vivado_project])
            self.block_cmds["build"].extend(self.block_cmds["prepare"])
            self.block_cmds["build"].extend([self.build_vivado_project, self.export_block_package])
            self.block_cmds["start-container"].extend([self.build_container_image, self.start_container])
            self.block_cmds["start-vivado-gui"].extend([self.build_container_image, self.start_vivado_gui])
        elif self.block_cfg.source == "import":
            self.block_cmds["build"].extend([self.import_prebuilt])

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

        create_vivado_project_commands = (
            f"'export XILINXD_LICENSE_FILE={self._amd_license} && "
            f"source {self._amd_vivado_path}/settings64.sh && "
            f"git config --global --add safe.directory {self._source_repo_dir} && "
            f"git config --global --add safe.directory {self._source_repo_dir}/Hog && "
            f"{self._source_repo_dir}/Hog/Do CREATE {self.block_cfg.project.name}'"
        )

        self.run_containerizable_sh_command(
            command=create_vivado_project_commands,
            dirs_to_mount=[(pathlib.Path(self._amd_tools_path), "ro"), (self._repo_dir, "Z"), (self._output_dir, "Z")],
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
        if not ZynqMP_AMD_Vivado_Hog_Builder_Alma9._check_rebuild_required(
            src_search_list=self._project_cfg_files
            + [
                self._source_repo_dir / "Top",
                self._source_repo_dir / "Hog",
                self._source_repo_dir / f"lib_{self.block_cfg.project.name}",
            ],
            out_search_list=[self._source_repo_dir / "bin"],
        ):
            pretty_print.print_build("No need to rebuild the Vivado Project. No altered source files detected...")
            return

        self.check_amd_tools(required_tools=["vivado"])

        # Clean output directory
        self.clean_output()
        self._output_dir.mkdir(parents=True)

        pretty_print.print_build("Building the Vivado Project...")

        vivado_build_commands = (
            f"'rm -rf {self._source_repo_dir}/bin"
            f"export XILINXD_LICENSE_FILE={self._amd_license} && "
            f"source {self._amd_vivado_path}/settings64.sh && "
            f"git config --global --add safe.directory {self._source_repo_dir} && "
            f"git config --global --add safe.directory {self._source_repo_dir}/Hog && "
            f"{self._source_repo_dir}/Hog/Do WORKFLOW {self.block_cfg.project.name}'"
        )

        self.run_containerizable_sh_command(
            command=vivado_build_commands,
            dirs_to_mount=[(pathlib.Path(self._amd_tools_path), "ro"), (self._repo_dir, "Z"), (self._output_dir, "Z")],
        )

        # Create symlinks to the output files
        xsa_files = list(self._source_repo_dir.glob(f"bin/{self.block_cfg.project.name}-*/{self.block_cfg.project.name}-*.xsa"))
        if len(xsa_files) != 1:
            pretty_print.print_error(
                f"Unexpected number of {len(xsa_files)} *.xsa files in output direct. Expected was 1."
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

        start_vivado_gui_commands = (
            f"'export XILINXD_LICENSE_FILE={self._amd_license} && "
            f"source {self._amd_vivado_path}/settings64.sh && "
            f"vivado -nojournal -nolog {self._source_repo_dir}/Projects/{self.block_cfg.project.name}/{self.block_cfg.project.name}.xpr && "
            f"exit'"
        )

        self.start_gui_container(
            start_gui_command=start_vivado_gui_commands,
            potential_mounts=[
                (pathlib.Path(self._amd_tools_path), "ro"),
                (self._repo_dir, "Z"),
                (self._output_dir, "Z"),
            ],
        )
