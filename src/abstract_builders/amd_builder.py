import os
import pathlib
import shutil
import sys
import hashlib
import inspect

import socks.pretty_print as pretty_print
from socks.build_validator import Build_Validator
from abstract_builders.builder import Builder


class AMD_Builder(Builder):
    """
    Base class for all builder classes that use AMD Xilinx tools
    """

    def __init__(
        self,
        project_cfg: dict,
        model_class,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str,
        block_description: str,
    ):

        super().__init__(
            project_cfg=project_cfg,
            model_class=model_class,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
        )

        # Project directories
        self._xsa_dir = self._block_temp_dir / "source_xsa"

        # Project files
        # File for saving the checksum of the XSA-file on which the project is based
        self._source_xsa_md5_file = self._work_dir / "source_xsa.md5"

    # These static variables are initialized dynamically via function check_amd_tools(). This allows people to use all
    # features of socks that do not require AMD Xilinx tools also when they do not have the AMD Xilinx tools installed.
    _amd_vivado_path = None
    _amd_vitis_path = None
    _amd_tools_path = None
    _amd_license = None

    def check_amd_tools(self, required_tools: list[str], pre_action_check: bool = False):
        """
        Retrieves and verifies AMD Xilinx tools setup information from the host environment.
        Parameter 'pre_action_check' should be set to 'True' when this function is called in the constructor of a
        builder class. This allows all SoCks functions that do not require AMD Xilinx tools to be used, even if
        those tools are not installed. With parameter 'pre_action_check' set to 'False', this function should only
        be called immediately before one of the AMD Xilinx tools is used in a builder.

        Args:
            required_tools:
                A list of all AMD Xilinx tools (vivado, vitis) that are required.
            pre_action_check:
                Perform just a pre-action check that creates pre-action warnings instead of issuing serious errors
                that cause the program to terminate.

        Returns:
            None

        Raises:
            ValueError: If an unsupported tool is requested.
        """

        supported_amd_tools = ("vivado", "vitis")

        for tool in required_tools:
            if tool not in supported_amd_tools:
                raise ValueError(f"The following AMD Xilinx tool is not supported {tool}.")

        # Skip if the requested AMD Xilinx tools have already been checked
        if (
            all(getattr(AMD_Builder, f"_amd_{tool}_path") is not None for tool in required_tools)
            and AMD_Builder._amd_license is not None
        ):
            return

        # Read values from environment
        for tool in required_tools:
            setattr(
                AMD_Builder,
                f"_amd_{tool}_path",
                pathlib.Path(os.getenv(f"XILINX_{tool.upper()}")) if os.getenv(f"XILINX_{tool.upper()}") else None,
            )
        AMD_Builder._amd_license = os.getenv("XILINXD_LICENSE_FILE")

        def _report_failure(pre_action_warning_msg: str, error_msg: str):
            if pre_action_check:
                self.pre_action_warnings.append(pre_action_warning_msg)
                return
            else:
                pretty_print.print_error(error_msg)
                sys.exit(1)

        # Check if the requested tools are available and if the version matches the project
        for tool in required_tools:
            if getattr(AMD_Builder, f"_amd_{tool}_path") is None:
                _report_failure(
                    pre_action_warning_msg=f"{tool.capitalize()} could not be found. This may cause errors "
                    f"during execution. If possible, source {tool.capitalize()} to avoid such issues.",
                    error_msg=f"{tool.capitalize()} could not be found. "
                    f"Please source {tool.capitalize()} {self.project_cfg.external_tools.xilinx.version}.",
                )
            else:
                if getattr(AMD_Builder, f"_amd_{tool}_path").name != self.project_cfg.external_tools.xilinx.version:
                    _report_failure(
                        pre_action_warning_msg=f"The sourced version of {tool.capitalize()} is "
                        f"'{getattr(AMD_Builder, f'_amd_{tool}_path').name}',"
                        f" but this project requires version '{self.project_cfg.external_tools.xilinx.version}'.",
                        error_msg=f"The sourced version of {tool.capitalize()} is "
                        f"'{getattr(AMD_Builder, f'_amd_{tool}_path').name}',"
                        f" but this project requires version '{self.project_cfg.external_tools.xilinx.version}'.",
                    )
                AMD_Builder._amd_tools_path = getattr(AMD_Builder, f"_amd_{tool}_path").parent.parent

        # Check if the license was found
        if AMD_Builder._amd_license is None:
            _report_failure(
                pre_action_warning_msg="AMD Xilinx license could not be found. It was expected in "
                "environment variable 'XILINXD_LICENSE_FILE'. This may cause errors during execution.",
                error_msg="AMD Xilinx license could not be found. It was expected in "
                "environment variable 'XILINXD_LICENSE_FILE'.",
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

        self.check_amd_tools(required_tools=["vivado", "vitis"])

        potential_mounts = [
            (self._xsa_dir, "Z"),
            (pathlib.Path(self._amd_tools_path), "ro"),
            (self._repo_dir, "Z"),
            (self._work_dir, "Z"),
            (self._output_dir, "Z"),
        ]

        init_commands = [
            f"export XILINXD_LICENSE_FILE={self._amd_license}",
            f"source {self._amd_vivado_path}/settings64.sh",
        ]

        self.container_executor.start_container(potential_mounts=potential_mounts, init_commands=init_commands)

    def import_xsa(self):
        """
        Imports an XSA archive.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        new_xsa_files = list((self._dependencies_dir / "vivado").glob("*.xsa"))
        # Check if there is more than one XSA file in the Vivado block package
        if len(new_xsa_files) != 1:
            pretty_print.print_error(f'Not exactly one XSA archive in {self._dependencies_dir / "vivado"}/')
            sys.exit(1)
        # Calculate md5 of the file to be imported
        md5_new_file = hashlib.md5(new_xsa_files[0].read_bytes()).hexdigest()

        imported_xsa_files = list(self._xsa_dir.glob("*.xsa"))
        # Check if there is more than one XSA file in the target directory
        if len(imported_xsa_files) > 1:
            pretty_print.print_error(f"More than one XSA archive in {self._xsa_dir}/")
            sys.exit(1)
        # Calculate md5 of the file that has already been imported, if any
        md5_imported_file = 0
        if imported_xsa_files:
            md5_imported_file = hashlib.md5(imported_xsa_files[0].read_bytes()).hexdigest()

        # Check whether the xsa archive needs to be imported
        if md5_new_file == md5_imported_file:
            pretty_print.print_build("No need to import XSA archive. No altered source files detected...")
            return

        # Clean source xsa directory
        self.clean_source_xsa()
        self._xsa_dir.mkdir(parents=True)

        pretty_print.print_build("Importing XSA archive...")

        # Copy XSA archive
        shutil.copy(new_xsa_files[0], self._xsa_dir / new_xsa_files[0].name)

    def clean_source_xsa(self):
        """
        This function cleans the source_xsa directory.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        if self._xsa_dir.exists():
            pretty_print.print_clean("Cleaning source_xsa directory...")

            cleaning_commands = [f"rm -rf {self._xsa_dir}/* {self._xsa_dir}/.* 2> /dev/null || true"]

            self.container_executor.exec_sh_commands(commands=cleaning_commands, dirs_to_mount=[(self._xsa_dir, "Z")])

            # Remove empty source_xsa directory
            self._xsa_dir.rmdir()

        else:
            pretty_print.print_clean("No need to clean the source_xsa directory...")
