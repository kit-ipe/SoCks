import sys
import pathlib
import hashlib
import inspect

import socks.pretty_print as pretty_print
from socks.build_validator import Build_Validator
from abstract_builders.amd_builder import AMD_Builder
from amd_versal_support.versal_amd_psmfw_model import Versal_AMD_PSMFW_Model


class Versal_AMD_PSMFW_Builder(AMD_Builder):
    """
    AMD PSM firmware builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "psm_fw",
        block_description: str = "Build the Processing System Manager (PSM) Firmware for Versal devices",
    ):

        super().__init__(
            project_cfg=project_cfg,
            model_class=Versal_AMD_PSMFW_Model,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
        )

        self.pre_action_warnings.append(
            "This block is experimental, it should not be used for production. "
            "Versal blocks should use the Vitis SDT flow instead of the XSCT flow, as soon as it is stable."
        )

        # Project directories
        self._vitis_workspace_dir = self._work_dir / "vitis_workspace"

    @property
    def _block_deps(self):
        # Products of other blocks on which this block depends
        # This dict is used to check whether the imported block packages contain
        # all the required files. Regex can be used to describe the expected files.
        # Optional dependencies can also be listed here. They will be ignored if
        # they are not listed in the project configuration.
        block_deps = {"vivado": [".*.xsa"]}
        return block_deps

    @property
    def block_cmds(self):
        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        block_cmds = {"prepare": [], "build": [], "clean": [], "start-container": []}
        block_cmds["clean"].extend(
            [
                self.container_executor.build_container_image,
                self.clean_download,
                self.clean_work,
                self.clean_source_xsa,
                self.clean_dependencies,
                self.clean_output,
                self.clean_block_temp,
            ]
        )
        if self.block_cfg.source == "build":
            block_cmds["prepare"].extend(
                [
                    self._build_validator.del_project_cfg,
                    self.container_executor.build_container_image,
                    self.import_dependencies,
                    self.import_xsa,
                    self.create_psmfw_project,
                    self._build_validator.save_project_cfg_prepare,
                ]
            )
            block_cmds["build"].extend(block_cmds["prepare"])
            block_cmds["build"].extend(
                [self.build_psmfw, self.export_block_package, self._build_validator.save_project_cfg_build]
            )
            block_cmds["start-container"].extend([self.container_executor.build_container_image, self.start_container])
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
        # self.import_req_src_tpl()

    def create_psmfw_project(self):
        """
        Creates the PSM firmware project.

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
            pretty_print.print_info("No new XSA archive recognized. PSM Firmware project is not created.")
            return

        self.check_amd_tools(required_tools=["vitis"])

        self.clean_work()
        self._work_dir.mkdir(parents=True)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        pretty_print.print_build("Creating the PSM Firmware project...")

        create_psmfw_project_commands = [
            f"export XILINXD_LICENSE_FILE={self._amd_license}",
            f"source {self._amd_vitis_path}/settings64.sh",
            f"mkdir -p {self._vitis_workspace_dir}",
            f"SOURCE_XSA_PATH=$(ls {self._xsa_dir}/*.xsa)",
            'printf "import vitis'
            "\r\n\r\nclient = vitis.create_client()"
            f'\r\n\r\nclient.update_workspace(path=\\"{self._vitis_workspace_dir}\\")'
            f'    \r\nclient.set_workspace(path=\\"{self._vitis_workspace_dir}\\")'
            '\r\n\r\nplatform = client.create_platform_component(name = \\"platform\\", hw_design = \\"${SOURCE_XSA_PATH}\\", os = \\"standalone\\", cpu = \\"psv_psm_0\\", domain_name = \\"standalone_psv_psm_0\\")'
            '    \r\ncomp = client.create_app_component(name = \\"versal_psmfw\\", platform = \\"\$COMPONENT_LOCATION/../platform/export/platform/platform.xpfm\\", domain = \\"standalone_psv_psm_0\\", template = \\"versal_psmfw\\")'
            f'\r\n\r\nvitis.dispose()" > {self._work_dir}/generate_psmfw_prj.py',
            f"vitis -s {self._work_dir}/generate_psmfw_prj.py",
        ]

        self.container_executor.exec_sh_commands(
            commands=create_psmfw_project_commands,
            dirs_to_mount=[
                (pathlib.Path(self._amd_tools_path), "ro"),
                (self._xsa_dir, "Z"),
                (self._work_dir, "Z"),
            ],
            print_commands=True,
        )

        # Save checksum in file
        with self._source_xsa_md5_file.open("w") as f:
            print(md5_new_file, file=f, end="")

    def build_psmfw(self):
        """
        Builds the PSM Firmware.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check whether the PSM Firmware needs to be built
        if not Build_Validator.check_rebuild_bc_timestamp(
            src_search_list=[self._vitis_workspace_dir],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ) and not self._build_validator.check_rebuild_bc_config(keys=[["external_tools", "xilinx"]]):
            pretty_print.print_build("No need to rebuild the PSM Firmware. No altered source files detected...")
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            self.check_amd_tools(required_tools=["vitis"])

            # Remove old build artifacts
            (self._output_dir / "psmfw.elf").unlink(missing_ok=True)

            pretty_print.print_build("Building the PSM Firmware...")

            psmfw_build_commands = [
                f"export XILINXD_LICENSE_FILE={self._amd_license}",
                f"source {self._amd_vitis_path}/settings64.sh",
                'printf "import vitis'
                "\r\n\r\nclient = vitis.create_client()"
                f'    \r\nclient.set_workspace(path=\\"{self._vitis_workspace_dir}\\")'
                '\r\n\r\nplatform = client.get_component(name=\\"platform\\")'
                '    \r\ncomp = client.get_component(name=\\"versal_psmfw\\")'
                "\r\n\r\nplatform.build()"
                "    \r\ncomp.build()"
                f'\r\n\r\nvitis.dispose()" > {self._work_dir}/build_psmfw_prj.py',
                f"vitis -s {self._work_dir}/build_psmfw_prj.py",
            ]

            self.container_executor.exec_sh_commands(
                commands=psmfw_build_commands,
                dirs_to_mount=[
                    (pathlib.Path(self._amd_tools_path), "ro"),
                    (self._work_dir, "Z"),
                ],
                print_commands=True,
                logfile=self._block_temp_dir / "build.log",
                output_scrolling=True,
            )

            # Create symlink to the output file
            (self._output_dir / "psmfw.elf").symlink_to(
                self._vitis_workspace_dir / "versal_psmfw" / "build" / "versal_psmfw.elf"
            )
