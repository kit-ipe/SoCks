import sys
import pathlib

import socks.pretty_print as pretty_print
from builders.amd_builder import AMD_Builder
from builders.zynqmp_amd_vivado_ipbb_model import ZynqMP_AMD_Vivado_IPBB_Model


class ZynqMP_AMD_Vivado_IPBB_Builder_Alma9(AMD_Builder):
    """
    Builder class for AMD Vivado projects utilizing the IPbus Builder (IPBB) framework
    """

    def __init__(
        self,
        project_cfg: dict,
        project_cfg_files: list,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "vivado",
        block_description: str = "Build an AMD/Xilinx Vivado Project with IPbus Builder (IPBB)",
    ):

        super().__init__(
            project_cfg=project_cfg,
            project_cfg_files=project_cfg_files,
            model_class=ZynqMP_AMD_Vivado_IPBB_Model,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
        )

        self._ipbb_work_dir_name = "ipbb-work"

        # Project directories
        self._ipbb_work_dir = self._repo_dir / self._ipbb_work_dir_name

        # Project files
        # Flag to remember if IPBB has already been initialized
        self._ipbb_init_done_flag = self._block_temp_dir / ".ipbbinitdone"

        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        self.block_cmds = {"prepare": [], "build": [], "clean": [], "start-container": [], "start-vivado-gui": []}
        self.block_cmds["clean"].extend(
            [self.build_container_image, self.clean_download, self.clean_repo, self.clean_output, self.clean_block_temp]
        )
        if self.block_cfg.source == "build":
            self.block_cmds["prepare"].extend([self.build_container_image, self.init_repo, self.create_vivado_project])
            self.block_cmds["build"].extend(self.block_cmds["prepare"])
            self.block_cmds["build"].extend([self.build_vivado_project, self.export_block_package])
            self.block_cmds["start-container"].extend([self.build_container_image, self.start_container])
            self.block_cmds["start-vivado-gui"].extend([self.build_container_image, self.start_vivado_gui])
        elif self.block_cfg.source == "import":
            self.block_cmds["build"].extend([self.import_prebuilt])

    def init_repo(self):
        """
        Initialize the IPBB environment.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Skip all operations if the IPBB environment is already initialized
        if self._ipbb_init_done_flag.exists():
            pretty_print.print_build("The IPBB environment has already been initialized. It is not reinitialized...")
            return

        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._repo_dir.mkdir(parents=True, exist_ok=True)

        pretty_print.print_build("Initializing the IPBB environment...")

        init_ipbb_env_commands = [
            "source ~/tools/ipbb-*/env.sh",
            f"cd {self._repo_dir}",
            f"ipbb init {self._ipbb_work_dir_name}",
            f"cd {self._ipbb_work_dir}"
        ]

        # Add local repositories
        for path in self._local_source_dirs:
            init_ipbb_env_commands.append(f"ipbb add symlink {path}")

        # Add online repositories
        for index in range(len(self._source_repos)):
            if not self._source_repos[index]["branch"].startswith(("-b ", "-r ")):
                pretty_print.print_error(
                    f"Entries in blocks/{self.block_id}/project/build_srcs[N]/branch have to start with '-b ' for branches and tags or with '-r ' for commit ids."
                )
                sys.exit(1)
            init_ipbb_env_commands.append(
                f"ipbb add git {self._source_repos[index]['url']} {self._source_repos[index]['branch']}"
            )

        local_source_mounts = []
        for path in self._local_source_dirs:
            local_source_mounts.append((path, "Z"))

        self.run_containerizable_sh_command(
            commands=init_ipbb_env_commands,
            dirs_to_mount=[(self._repo_dir, "Z")] + local_source_mounts,
            custom_params=["-v", "$SSH_AUTH_SOCK:/ssh-auth-sock", "--env", "SSH_AUTH_SOCK=/ssh-auth-sock"],
        )

        # Create the flag if it doesn't exist and update the timestamps
        self._ipbb_init_done_flag.touch()

    def create_vivado_project(self):
        """
        Create the Vivado project utilizing the IPbus Builder framework.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check if the Vivado project needs to be created
        if (self._ipbb_work_dir / "proj" / self.block_cfg.project.name).is_dir():
            pretty_print.print_build("The Vivado Project already exists. It will not be recreated...")
            return

        self.check_amd_tools(required_tools=["vivado"])

        pretty_print.print_build("Creating the Vivado Project...")

        create_vivado_project_commands = [
            "source ~/tools/ipbb-*/env.sh",
            f"cd {self._ipbb_work_dir}",
            f"ipbb toolbox check-dep vivado serenity-s1-k26c-fw:projects/{self.block_cfg.project.name} top.dep",
            f"ipbb proj create vivado {self.block_cfg.project.name} serenity-s1-k26c-fw:projects/{self.block_cfg.project.name}",
            f"cd proj/{self.block_cfg.project.name}",
            "export LD_LIBRARY_PATH=/opt/cactus/lib:\$$LD_LIBRARY_PATH PATH=/opt/cactus/bin/uhal/tools:\$$PATH",
            "ipbb ipbus gendecoders -c",
            f"export XILINXD_LICENSE_FILE={self._amd_license}",
            f"source {self._amd_vivado_path}/settings64.sh",
            "ipbb vivado generate-project"
        ]

        local_source_mounts = []
        for path in self._local_source_dirs:
            local_source_mounts.append((path, "Z"))

        self.run_containerizable_sh_command(
            commands=create_vivado_project_commands,
            dirs_to_mount=[(pathlib.Path(self._amd_tools_path), "ro"), (self._repo_dir, "Z")] + local_source_mounts,
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
        if not ZynqMP_AMD_Vivado_IPBB_Builder_Alma9._check_rebuild_required(
            src_search_list=self._project_cfg_files
            + [
                self._ipbb_work_dir / "src",
                self._ipbb_work_dir / "var",
                self._ipbb_work_dir / "proj" / self.block_cfg.project.name / "decoders",
                self._ipbb_work_dir / "proj" / self.block_cfg.project.name / self.block_cfg.project.name,
            ],
            src_ignore_list=[
                self._ipbb_work_dir
                / "proj"
                / self.block_cfg.project.name
                / self.block_cfg.project.name
                / f"{self.block_cfg.project.name}.runs",
                self._ipbb_work_dir
                / "proj"
                / self.block_cfg.project.name
                / self.block_cfg.project.name
                / f"{self.block_cfg.project.name}.cache",
            ],
            out_search_list=[self._ipbb_work_dir / "proj" / self.block_cfg.project.name / "package"],
        ):
            pretty_print.print_build("No need to rebuild the Vivado Project. No altered source files detected...")
            return

        self.check_amd_tools(required_tools=["vivado"])

        # Clean output directory
        self.clean_output()
        self._output_dir.mkdir(parents=True)

        pretty_print.print_build("Building the Vivado Project...")

        vivado_build_commands = [
            "source ~/tools/ipbb-*/env.sh",
            f"export XILINXD_LICENSE_FILE={self._amd_license}",
            f"source {self._amd_vivado_path}/settings64.sh",
            f"cd {self._ipbb_work_dir}/proj/{self.block_cfg.project.name}",
            "ipbb vivado check-syntax",
            f"ipbb vivado synth -j{self.project_cfg.external_tools.xilinx.max_threads_vivado} impl -j{self.project_cfg.external_tools.xilinx.max_threads_vivado}",
            "ipbb vivado bitfile package"
        ]

        local_source_mounts = []
        for path in self._local_source_dirs:
            local_source_mounts.append((path, "Z"))

        self.run_containerizable_sh_command(
            commands=vivado_build_commands,
            dirs_to_mount=[(pathlib.Path(self._amd_tools_path), "ro"), (self._repo_dir, "Z")] + local_source_mounts,
        )

        # Create symlinks to the output files
        for item in (self._ipbb_work_dir / "proj" / self.block_cfg.project.name / "package" / "src").glob("*"):
            (self._output_dir / item.name).symlink_to(item)

    def start_container(self):
        """
        Starts an interactive container with which the block can be built.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        self.check_amd_tools(required_tools=["vivado"])

        potential_mounts = [
            (self._xsa_dir, "Z"),
            (pathlib.Path(self._amd_tools_path), "ro"),
            (self._repo_dir, "Z"),
            (self._work_dir, "Z"),
            (self._output_dir, "Z"),
        ]

        for path in self._local_source_dirs:
            potential_mounts.append((path, "Z"))

        super(Builder, self).start_container(potential_mounts=potential_mounts)

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
            f"vivado -nojournal -nolog {self._ipbb_work_dir}/proj/{self.block_cfg.project.name}/{self.block_cfg.project.name}/{self.block_cfg.project.name}.xpr",
            f"exit"
        ]

        self.start_gui_container(
            start_gui_commands=start_vivado_gui_commands,
            potential_mounts=[
                (pathlib.Path(self._amd_tools_path), "ro"),
                (self._repo_dir, "Z"),
                (self._output_dir, "Z"),
            ],
        )
