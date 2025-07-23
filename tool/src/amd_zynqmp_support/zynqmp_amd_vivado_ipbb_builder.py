import sys
import pathlib
import inspect
import re

import socks.pretty_print as pretty_print
from socks.build_validator import Build_Validator
from abstract_builders.amd_builder import AMD_Builder
from amd_zynqmp_support.zynqmp_amd_vivado_ipbb_model import ZynqMP_AMD_Vivado_IPBB_Model


class ZynqMP_AMD_Vivado_IPBB_Builder(AMD_Builder):
    """
    Builder class for AMD Vivado projects utilizing the IPbus Builder (IPBB) framework
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "vivado",
        block_description: str = "Build an AMD/Xilinx Vivado Project with IPbus Builder (IPBB)",
        model_class: type[object] = ZynqMP_AMD_Vivado_IPBB_Model,
    ):

        super().__init__(
            project_cfg=project_cfg,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
            model_class=model_class,
        )

        self._ipbb_work_dir_name = "ipbb-work"

        # Project directories
        self._ipbb_install_dir = self._repo_dir / "ipbb-tool"
        self._ipbb_work_dir = self._repo_dir / self._ipbb_work_dir_name

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

        def extract_domain(url):
            # Regular expression to find the domain in HTTP/HTTPS and SSH URLs
            pattern = r"(?:https?:\/\/|ssh:\/\/git@)([^:\/]+)"
            match = re.search(pattern, url)
            if match:
                return match.group(1)
            return None

        def extract_port(url):
            # Regular expression to find the port in the URL
            pattern = r":(\d+)"
            match = re.search(pattern, url)
            if match:
                return match.group(1)
            return None

        # Skip all operations if the repo config hasn't changed
        if not self._build_validator.check_rebuild_bc_config(
            keys=[["blocks", self.block_id, "project", "build_srcs"]], accept_prep=True
        ):
            pretty_print.print_build("No need to initialize the IPBB environment...")
            return

        self.clean_output()
        self._output_dir.mkdir(parents=True)
        self.clean_repo()
        self._repo_dir.mkdir(parents=True)

        pretty_print.print_build("Initializing the IPBB environment...")

        init_ipbb_env_commands = [
            # Create SSH directory to simplify subsequently adding known hosts
            "mkdir -p -m 0700 ~/.ssh",
            # Install IPBB
            f"mkdir {self._ipbb_install_dir}",
            f"cd {self._ipbb_install_dir}",
            f"curl -L https://github.com/ipbus/ipbb/archive/{self.block_cfg.project.ipbb_tag}.tar.gz | tar xvz",
            f"source {self._ipbb_install_dir}/ipbb-{self.block_cfg.project.ipbb_tag.replace('/', '-')}/env.sh",
            # Initialize IPBB
            f"cd {self._repo_dir}",
            f"ipbb init {self._ipbb_work_dir_name}",
            f"cd {self._ipbb_work_dir}",
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
            # Manually add Git hosts to list of known hosts to prevent being prompted for confirmation
            if self.project_cfg.external_tools.container_tool in ["docker", "podman"]:
                uri = self._source_repos[index]["url"]
                domain = extract_domain(uri)
                port = extract_port(uri)
                if domain is not None and port is not None:
                    init_ipbb_env_commands.append(f"ssh-keyscan -p {port} {domain} >> ~/.ssh/known_hosts")
                elif domain is not None:
                    init_ipbb_env_commands.append(f"ssh-keyscan {domain} >> ~/.ssh/known_hosts")
            init_ipbb_env_commands.append(
                f"ipbb add git {self._source_repos[index]['url']} {self._source_repos[index]['branch']}"
            )

        local_source_mounts = []
        for path in self._local_source_dirs:
            local_source_mounts.append((path, "Z"))

        self.container_executor.exec_sh_commands(
            commands=init_ipbb_env_commands,
            dirs_to_mount=[(self._repo_dir, "Z")] + local_source_mounts,
            custom_params=["-v", "$SSH_AUTH_SOCK:/ssh-auth-sock", "--env", "SSH_AUTH_SOCK=/ssh-auth-sock"],
            print_commands=True,
        )

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
            f"source {self._ipbb_install_dir}/ipbb-{self.block_cfg.project.ipbb_tag.replace('/', '-')}/env.sh",
            f"cd {self._ipbb_work_dir}",
            f"ipbb toolbox check-dep vivado {self.block_cfg.project.main_prj_src}:projects/{self.block_cfg.project.name} top.dep",
            f"ipbb proj create vivado {self.block_cfg.project.name} {self.block_cfg.project.main_prj_src}:projects/{self.block_cfg.project.name}",
            f"cd proj/{self.block_cfg.project.name}",
            "export LD_LIBRARY_PATH=/opt/cactus/lib:\$$LD_LIBRARY_PATH PATH=/opt/cactus/bin/uhal/tools:\$$PATH",
            "ipbb ipbus gendecoders -c",
            f"export XILINXD_LICENSE_FILE={self._amd_license}",
            f"source {self._amd_vivado_path}/settings64.sh",
            "ipbb vivado generate-project",
        ]

        local_source_mounts = []
        for path in self._local_source_dirs:
            local_source_mounts.append((path, "Z"))

        self.container_executor.exec_sh_commands(
            commands=create_vivado_project_commands,
            dirs_to_mount=[(pathlib.Path(self._amd_tools_path), "ro"), (self._repo_dir, "Z")] + local_source_mounts,
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
                self._ipbb_work_dir
                / "proj"
                / self.block_cfg.project.name
                / self.block_cfg.project.name
                / f"{self.block_cfg.project.name}.xpr",
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
                f"source {self._ipbb_install_dir}/ipbb-{self.block_cfg.project.ipbb_tag.replace('/', '-')}/env.sh",
                f"export XILINXD_LICENSE_FILE={self._amd_license}",
                f"source {self._amd_vivado_path}/settings64.sh",
                f"cd {self._ipbb_work_dir}/proj/{self.block_cfg.project.name}",
                "ipbb vivado check-syntax",
                f"ipbb vivado synth -j{self.project_cfg.external_tools.xilinx.max_threads_vivado} impl -j{self.project_cfg.external_tools.xilinx.max_threads_vivado}",
                "ipbb vivado bitfile package",
            ]

            local_source_mounts = []
            for path in self._local_source_dirs:
                local_source_mounts.append((path, "Z"))

            self.container_executor.exec_sh_commands(
                commands=vivado_build_commands,
                dirs_to_mount=[(pathlib.Path(self._amd_tools_path), "ro"), (self._repo_dir, "Z")] + local_source_mounts,
                print_commands=True,
                logfile=self._block_temp_dir / "build.log",
                output_scrolling=True,
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

        self.container_executor.start_container(potential_mounts=potential_mounts)

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
            f"exit",
        ]

        potential_mounts = [
            (self._xsa_dir, "Z"),
            (pathlib.Path(self._amd_tools_path), "ro"),
            (self._repo_dir, "Z"),
            (self._work_dir, "Z"),
            (self._output_dir, "Z"),
        ]

        for path in self._local_source_dirs:
            potential_mounts.append((path, "Z"))

        self.container_executor.start_gui_container(
            start_gui_commands=start_vivado_gui_commands,
            potential_mounts=potential_mounts,
        )
