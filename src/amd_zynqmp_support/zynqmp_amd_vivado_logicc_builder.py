import sys
import pathlib
import inspect
import shutil

import socks.pretty_print as pretty_print
from socks.build_validator import Build_Validator
from abstract_builders.builder import Builder
from abstract_builders.amd_builder import AMD_Builder
from amd_zynqmp_support.zynqmp_amd_vivado_logicc_model import ZynqMP_AMD_Vivado_logicc_Model


class ZynqMP_AMD_Vivado_logicc_Builder(AMD_Builder):
    """
    Builder class for AMD Vivado projects utilizing the logicc framework
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "vivado",
        block_description: str = "Build an AMD/Xilinx Vivado Project with logicc",
        model_class: type[object] = ZynqMP_AMD_Vivado_logicc_Model,
    ):

        super().__init__(
            project_cfg=project_cfg,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
            model_class=model_class,
        )

        # Project directories
        self._logicc_install_dir = self._work_dir / "logicc-tool"
        self._logicc_work_dir = self._work_dir / "logicc-work"
        self._logicc_build_dir = self._logicc_work_dir / "build"
        self._logicc_image_dir = self._logicc_work_dir / "image"

        self._logicc_cfg_cmds = [
            f"logicc config set lib_dir {self._logicc_install_dir}/logicc/lib",
            f"logicc config set work_dir {self._source_repo_dir}",
            f"logicc config set build_dir {self._logicc_build_dir}",
            f"logicc config set image_dir {self._logicc_image_dir}",
        ]

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
                    self.init_logicc,
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

    def init_logicc(self):
        """
        Installs and initializes logicc.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Skip all operations if the repo config hasn't changed
        if not self._build_validator.check_rebuild_bc_config(
            keys=[["blocks", self.block_id, "project", "logicc_branch"]], accept_prep=True
        ):
            pretty_print.print_build("No need to install logicc. It is already installed...")
            return

        # Clean install directory
        try:
            shutil.rmtree(self._logicc_install_dir)
        except FileNotFoundError:
            pass  # Ignore if the directory does not exist

        self._logicc_install_dir.mkdir(parents=True)

        pretty_print.print_build("Installing logicc...")

        install_logicc_commands = [
            # Create SSH directory to simplify subsequently adding known hosts
            "mkdir -p -m 0700 ~/.ssh",
            # Manually add Git host to list of known hosts to prevent being prompted for confirmation
            "ssh-keyscan gitlab.kit.edu >> ~/.ssh/known_hosts",
            f"git clone --depth 1 --branch {self.block_cfg.project.logicc_branch} "  # Intentionally no comma here
            f"git@gitlab.kit.edu:kit/ipe-sdr/ipe-sdr-dev/hardware/logicc.git {self._logicc_install_dir}/logicc",
            f"mkdir -p {self._logicc_install_dir}/py_envs",
            f"python3 -m venv {self._logicc_install_dir}/py_envs/logicc",
            f"source {self._logicc_install_dir}/py_envs/logicc/bin/activate",
            # Install logicc
            f"cd {self._logicc_install_dir}/logicc",
            "pip install -U .",
            "./install_toml_parser",
        ]

        self.container_executor.exec_sh_commands(
            commands=install_logicc_commands,
            dirs_to_mount=[(self._work_dir, "Z")],
            custom_params=["-v", "$SSH_AUTH_SOCK:/ssh-auth-sock", "--env", "SSH_AUTH_SOCK=/ssh-auth-sock"],
            print_commands=True,
        )

    def create_vivado_project(self):
        """
        Create the Vivado project utilizing the logicc framework.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check if the Vivado project needs to be created
        if (
            self._logicc_build_dir.is_dir()
            and self._logicc_image_dir.is_dir()
            and not Build_Validator.check_rebuild_bc_timestamp(
                src_search_list=[self._source_repo_dir],
                out_timestamp=self._build_log.get_logged_timestamp(
                    identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
                ),
            )
        ) and not self._build_validator.check_rebuild_bc_config(
            keys=[["external_tools", "xilinx"], ["blocks", self.block_id, "project", "name"]], accept_prep=True
        ):
            pretty_print.print_build("No need to recreated the Vivado Project. No altered source files detected...")
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            self.check_amd_tools(required_tools=["vivado"])

            # Clean work directory
            try:
                shutil.rmtree(self._logicc_work_dir)
            except FileNotFoundError:
                pass  # Ignore if the directory does not exist

            self._logicc_build_dir.mkdir(parents=True)
            self._logicc_image_dir.mkdir(parents=True)

            pretty_print.print_build("Creating the Vivado Project...")

            create_vivado_project_commands = (
                [
                    f"export XILINXD_LICENSE_FILE={self._amd_license}",
                    f"export SDR_BUILD_NUMBER_OF_CPUS={self.project_cfg.external_tools.xilinx.max_threads_vivado}",
                    f"source {self._amd_vivado_path}/settings64.sh",
                    f"source {self._logicc_install_dir}/py_envs/logicc/bin/activate",
                ]
                + self._logicc_cfg_cmds
                + [
                    f"cd {self._logicc_build_dir}",  # This is done to create the logicc logfiles in this dir
                    f"logicc create {self.block_cfg.project.name}",
                ]
            )

            self.container_executor.exec_sh_commands(
                commands=create_vivado_project_commands,
                dirs_to_mount=[
                    (pathlib.Path(self._amd_tools_path), "ro"),
                    (self._repo_dir, "Z"),
                    (self._work_dir, "Z"),
                ],
                print_commands=True,
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

        # Find vivado build directory
        vivado_build_dir = self._logicc_build_dir
        for substr in self.block_cfg.project.name.split(":", 1):
            vivado_build_dir = vivado_build_dir / substr

        # Check if the project needs to be build
        if not Build_Validator.check_rebuild_bc_timestamp(
            src_search_list=[self._source_repo_dir, self._logicc_build_dir],
            src_ignore_list=[
                vivado_build_dir / f"{self.block_cfg.project.name.split(':', 1)[0]}.runs",
                vivado_build_dir / f"{self.block_cfg.project.name.split(':', 1)[0]}.cache",
                vivado_build_dir / f"{self.block_cfg.project.name.split(':', 1)[0]}.xpr",
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

            vivado_build_commands = (
                [
                    f"export XILINXD_LICENSE_FILE={self._amd_license}",
                    f"export SDR_BUILD_NUMBER_OF_CPUS={self.project_cfg.external_tools.xilinx.max_threads_vivado}",
                    f"source {self._amd_vivado_path}/settings64.sh",
                    f"source {self._logicc_install_dir}/py_envs/logicc/bin/activate",
                ]
                + self._logicc_cfg_cmds
                + [
                    f"cd {self._logicc_build_dir}",  # This is done to create the logicc logfiles in this dir
                    f"logicc run {self.block_cfg.project.name}",
                    "true",  # This is an ugly fix, but without it logicc sometimes gets stuck after synthesis (I think the issue is not really in logicc. It looks like Vivado simply does not return after finishing the job.)
                ]
            )

            self.container_executor.exec_sh_commands(
                commands=vivado_build_commands,
                dirs_to_mount=[
                    (pathlib.Path(self._amd_tools_path), "ro"),
                    (self._repo_dir, "Z"),
                    (self._work_dir, "Z"),
                ],
                print_commands=True,
                logfile=self._block_temp_dir / "build.log",
                output_scrolling=True,
            )

            # Find output directory (This is required to handle abstract logicc projects)
            logicc_output_dir = self._logicc_image_dir
            for substr in self.block_cfg.project.name.split(":", 1):
                logicc_output_dir = logicc_output_dir / substr

            # Create symlinks to the output files
            for file in logicc_output_dir.glob("*"):
                (self._output_dir / file.name).symlink_to(file)

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
            [
                f"export XILINXD_LICENSE_FILE={self._amd_license}",
                f"export SDR_BUILD_NUMBER_OF_CPUS={self.project_cfg.external_tools.xilinx.max_threads_vivado}",
                f"source {self._amd_vivado_path}/settings64.sh",
                f"source {self._logicc_install_dir}/py_envs/logicc/bin/activate",
            ]
            + self._logicc_cfg_cmds
            + [f"logicc start {self.block_cfg.project.name}", "exit"]
        )

        self.container_executor.start_gui_container(
            start_gui_commands=start_vivado_gui_commands,
            potential_mounts=[
                (pathlib.Path(self._amd_tools_path), "ro"),
                (self._repo_dir, "Z"),
                (self._work_dir, "Z"),
                (self._output_dir, "Z"),
            ],
        )

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

        init_commands = [
            f"export XILINXD_LICENSE_FILE={self._amd_license}",
            f"export SDR_BUILD_NUMBER_OF_CPUS={self.project_cfg.external_tools.xilinx.max_threads_vivado}",
            f"source {self._amd_vivado_path}/settings64.sh",
            f"source {self._logicc_install_dir}/py_envs/logicc/bin/activate",
            'export PS1="${VIRTUAL_ENV_PROMPT}[\\u@\\h \\W]\\$ "',  # This is an ugly hack to fix the prompt in the container. It is needed because if the activated Python environment in the container.
        ] + self._logicc_cfg_cmds

        self.container_executor.start_container(potential_mounts=potential_mounts, init_commands=init_commands)
