import sys
import pathlib
import hashlib
import inspect

import socks.pretty_print as pretty_print
from socks.build_validator import Build_Validator
from amd_zynqmp_support.zynqmp_amd_fsbl_builder import ZynqMP_AMD_FSBL_Builder
from amd_zynq_support.zynq_amd_fsbl_model import Zynq_AMD_FSBL_Model


class Zynq_AMD_FSBL_Builder(ZynqMP_AMD_FSBL_Builder):
    """
    AMD FSBL builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "fsbl",
        block_description: str = "Build the First Stage Boot Loader (FSBL) for Zynq devices",
        model_class: type[object] = Zynq_AMD_FSBL_Model,
    ):

        super().__init__(
            project_cfg=project_cfg,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
            model_class=model_class,
        )

        self.pre_action_warnings.append(
            f"Builder {self.__class__.__name__} is experimental and should not be used for production."
        )

    def create_fsbl_project(self):
        """
        Creates the FSBL project.

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
            pretty_print.print_error(f"Not exactly one XSA archive in {self._xsa_dir}/")
            sys.exit(1)

        # Calculate md5 of the provided file
        md5_new_file = hashlib.md5(xsa_files[0].read_bytes()).hexdigest()
        # Read md5 of previously used XSA archive, if any
        md5_existsing_file = 0
        if self._source_xsa_md5_file.is_file():
            with self._source_xsa_md5_file.open("r") as f:
                md5_existsing_file = f.read()

        # Check if the project needs to be created
        if (md5_existsing_file == md5_new_file) and not self._build_validator.check_rebuild_bc_config(
            keys=[["external_tools", "xilinx"]], accept_prep=True
        ):
            pretty_print.print_info("No new XSA archive recognized. FSBL project is not created.")
            return

        self.check_amd_tools(required_tools=["vitis"])

        self.clean_work()
        self.clean_repo()
        self._work_dir.mkdir(parents=True)
        self._repo_dir.mkdir(parents=True)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        pretty_print.print_build("Creating the FSBL project...")

        create_fsbl_project_commands = [
            f"export XILINXD_LICENSE_FILE={self._amd_license}",
            f"source {self._amd_vitis_path}/settings64.sh",
            f"SOURCE_XSA_PATH=$(ls {self._xsa_dir}/*.xsa)",
            'printf "set hwdsgn [hsi open_hw_design ${SOURCE_XSA_PATH}]'
            f'    \r\nhsi generate_app -hw \$hwdsgn -os standalone -proc ps7_cortexa9_0 -app zynq_fsbl -sw fsbl -dir {self._source_repo_dir}" > {self._work_dir}/generate_fsbl_prj.tcl',
            f"xsct -nodisp {self._work_dir}/generate_fsbl_prj.tcl",
            f"git -C {self._source_repo_dir} init --initial-branch=main",
            f"git -C {self._source_repo_dir} config user.email 'container-user@example.com'",
            f"git -C {self._source_repo_dir} config user.name 'container-user'",
            f"git -C {self._source_repo_dir} add {self._source_repo_dir}/.",
            #f"git -C {self._source_repo_dir} reset -- {self._source_repo_dir}/zynqmp_fsbl_bsp/psu_cortexa53_0/libsrc/libmetal_*/build_libmetal/",  # If this directory exists, it changes during build time and should therefore not be tracked by Git. Libmetal is the only library with this behavior that I have discovered so far.
            f"git -C {self._source_repo_dir} commit --quiet -m 'Initial commit'",
        ]

        self.container_executor.exec_sh_commands(
            commands=create_fsbl_project_commands,
            dirs_to_mount=[
                (pathlib.Path(self._amd_tools_path), "ro"),
                (self._xsa_dir, "Z"),
                (self._repo_dir, "Z"),
                (self._work_dir, "Z"),
            ],
            print_commands=True,
        )

        # Create new branch self._git_local_ref_branch. This branch is used as a reference where all existing patches are applied to the git sources
        self.shell_executor.exec_sh_command(
            ["git", "-C", str(self._source_repo_dir), "switch", "-c", self._git_local_ref_branch]
        )
        # Create new branch self._git_local_dev_branch. This branch is used as the local development branch. New patches can be created from this branch.
        self.shell_executor.exec_sh_command(
            ["git", "-C", str(self._source_repo_dir), "switch", "-c", self._git_local_dev_branch]
        )

        # Save checksum in file
        with self._source_xsa_md5_file.open("w") as f:
            print(md5_new_file, file=f, end="")
