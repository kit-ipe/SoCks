import sys
import pathlib
import shutil
import hashlib
import inspect

import socks.pretty_print as pretty_print
from socks.shell_command_runners import Shell_Command_Runners
from builders.amd_builder import AMD_Builder
from builders.zynqmp_amd_pmufw_model import ZynqMP_AMD_PMUFW_Model


class ZynqMP_AMD_PMUFW_Builder(AMD_Builder):
    """
    AMD PMU firmware builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        project_cfg_files: list,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "pmu_fw",
        block_description: str = "Build the Platform Management Unit (PMU) Firmware for ZynqMP devices",
    ):

        super().__init__(
            project_cfg=project_cfg,
            project_cfg_files=project_cfg_files,
            model_class=ZynqMP_AMD_PMUFW_Model,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
        )

        # Products of other blocks on which this block depends
        # This dict is used to check whether the imported block packages contain
        # all the required files. Regex can be used to describe the expected files.
        # Optional dependencies can also be listed here. They will be ignored if
        # they are not listed in the project configuration.
        self._block_deps = {"vivado": [".*.xsa"]}

        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        self.block_cmds = {"prepare": [], "build": [], "clean": [], "create-patches": [], "start-container": []}
        self.block_cmds["clean"].extend(
            [
                self.build_container_image,
                self.clean_download,
                self.clean_work,
                self.clean_repo,
                self.clean_source_xsa,
                self.clean_dependencies,
                self.clean_output,
                self.clean_block_temp,
            ]
        )
        if self.block_cfg.source == "build":
            self.block_cmds["prepare"].extend(
                [
                    self.build_container_image,
                    self.import_dependencies,
                    self.import_xsa,
                    self.create_pmufw_project,
                    self.apply_patches,
                ]
            )
            self.block_cmds["build"].extend(self.block_cmds["prepare"])
            self.block_cmds["build"].extend([self.build_pmufw, self.export_block_package])
            self.block_cmds["create-patches"].extend([self.create_patches])
            self.block_cmds["start-container"].extend([self.build_container_image, self.start_container])
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

        self.import_src_tpl()

    def create_pmufw_project(self):
        """
        Creates the PMU firmware project.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        xsa_files = list(self._xsa_dir.glob("*.xsa"))

        # Check if there is more than one XSA file in the xsa directory
        if len(xsa_files) != 1:
            pretty_print.print_error(f"Not exactly one XSA archive in {self._xsa_dir}.")
            sys.exit(1)

        # Calculate md5 of the provided file
        md5_new_file = hashlib.md5(xsa_files[0].read_bytes()).hexdigest()
        # Read md5 of previously used XSA archive, if any
        md5_existsing_file = 0
        if self._source_xsa_md5_file.is_file():
            with self._source_xsa_md5_file.open("r") as f:
                md5_existsing_file = f.read()

        # Check if the project needs to be created
        if md5_existsing_file == md5_new_file:
            pretty_print.print_warning("No new XSA archive recognized. PMU Firmware project is not created.")
            return

        self.check_amd_tools(required_tools=["vitis"])

        self.clean_work()
        self.clean_repo()
        self._work_dir.mkdir(parents=True)
        self._repo_dir.mkdir(parents=True)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        pretty_print.print_build("Creating the PMU Firmware project...")

        create_pmufw_project_commands = [
            f"export XILINXD_LICENSE_FILE={self._amd_license}",
            f"source {self._amd_vitis_path}/settings64.sh",
            f"SOURCE_XSA_PATH=$(ls {self._xsa_dir}/*.xsa)",
            'printf "set hwdsgn [hsi open_hw_design ${SOURCE_XSA_PATH}]'
            f'    \r\nhsi generate_app -hw \$hwdsgn -os standalone -proc psu_pmu_0 -app zynqmp_pmufw -sw pmufw -dir {self._source_repo_dir}" > {self._work_dir}/generate_pmufw_prj.tcl',
            f"xsct -nodisp {self._work_dir}/generate_pmufw_prj.tcl",
            f"git -C {self._source_repo_dir} init --initial-branch=main",
            f"git -C {self._source_repo_dir} config user.email 'container-user@example.com'",
            f"git -C {self._source_repo_dir} config user.name 'container-user'",
            f"git -C {self._source_repo_dir} add {self._source_repo_dir}/.",
            f"git -C {self._source_repo_dir} commit --quiet -m 'Initial commit'",
        ]

        self.run_containerizable_sh_command(
            commands=create_pmufw_project_commands,
            dirs_to_mount=[
                (pathlib.Path(self._amd_tools_path), "ro"),
                (self._xsa_dir, "Z"),
                (self._repo_dir, "Z"),
                (self._work_dir, "Z"),
                (self._output_dir, "Z"),
            ],
        )

        # Create new branch self._git_local_ref_branch. This branch is used as a reference where all existing patches are applied to the git sources
        Shell_Command_Runners.run_sh_command(
            ["git", "-C", str(self._source_repo_dir), "switch", "-c", self._git_local_ref_branch]
        )
        # Create new branch self._git_local_dev_branch. This branch is used as the local development branch. New patches can be created from this branch.
        Shell_Command_Runners.run_sh_command(
            ["git", "-C", str(self._source_repo_dir), "switch", "-c", self._git_local_dev_branch]
        )

        # Save checksum in file
        with self._source_xsa_md5_file.open("w") as f:
            print(md5_new_file, file=f, end="")

    def build_pmufw(self):
        """
        Builds the PMU Firmware.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check whether the PMU Firmware needs to be built
        if not ZynqMP_AMD_PMUFW_Builder._check_rebuild_required(
            src_search_list=self._project_cfg_files + [self._source_repo_dir],
            src_ignore_list=[self._source_repo_dir / "executable.elf"],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ):
            pretty_print.print_build("No need to rebuild the PMU Firmware. No altered source files detected...")
            return

        self.check_amd_tools(required_tools=["vitis"])

        pretty_print.print_build("Building the PMU Firmware...")

        pmufw_build_commands = [
            f"export XILINXD_LICENSE_FILE={self._amd_license}",
            f"source {self._amd_vitis_path}/settings64.sh",
            f"cd {self._source_repo_dir}",
            "make clean",
            "make",
        ]

        self.run_containerizable_sh_command(
            commands=pmufw_build_commands,
            dirs_to_mount=[
                (pathlib.Path(self._amd_tools_path), "ro"),
                (self._xsa_dir, "Z"),
                (self._repo_dir, "Z"),
                (self._output_dir, "Z"),
            ],
        )

        # Create symlink to the output file
        (self._output_dir / "pmufw.elf").unlink(missing_ok=True)
        (self._output_dir / "pmufw.elf").symlink_to(self._source_repo_dir / "executable.elf")

        # Log success of this function
        self._build_log.log_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")
