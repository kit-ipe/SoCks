import typing
import os
import pathlib
import shutil
import sys

import socks.pretty_print as pretty_print
from socks.builder import Builder

class AMD_Builder(Builder):
    """
    Base class for all builder classes that use AMD Xilinx tools
    """

    def __init__(self, project_cfg: dict, project_cfg_files: list, socks_dir: pathlib.Path, project_dir: pathlib.Path, block_id: str, block_description: str):

        super().__init__(project_cfg=project_cfg,
                        project_cfg_files=project_cfg_files,
                        socks_dir=socks_dir,
                        project_dir=project_dir,
                        block_id=block_id,
                        block_description=block_description)

        # Import project configuration
        self._pc_xilinx_version = project_cfg["externalTools"]["xilinx"]["version"]
        self._pc_vivado_threads = project_cfg["externalTools"]["xilinx"]["maxThreadsVivado"]

        self._amd_vivado_path = None
        self._amd_vitis_path = None
        self._amd_tools_path = None
        self._amd_license = None

        # Project directories
        self._xsa_dir = self._block_temp_dir / 'source_xsa'

        # Project files
        # File for saving the checksum of the XSA-file on which the project is based
        self._source_xsa_md5_file = self._work_dir / 'source_xsa.md5'


    def check_amd_tools(self, required_tools: typing.List[str]):
        """
        Collects and checks AMD Xilinx tool setup information from the host environment.

        Args:
            required_tools:
                A list of all AMD Xilinx tools (vivado, vitis) that are required.

        Returns:
            None

        Raises:
            ValueError: If an unsupported tool is requested.
        """

        for tool in required_tools:
            if tool not in ['vivado', 'vitis']:
                raise ValueError(f'The following AMD Xilinx tool is not supported {tool}.')

        # Skip if the requested AMD Xilinx tools have already been checked
        if (not ('vivado' in required_tools and self._amd_vivado_path is None) and
                    not ('vitis' in required_tools and self._amd_vitis_path is None) and
                    self._amd_license is not None):
            return

        self._amd_vivado_path = pathlib.Path(os.getenv('XILINX_VIVADO')) if os.getenv('XILINX_VIVADO') else None
        self._amd_vitis_path = pathlib.Path(os.getenv('XILINX_VITIS')) if os.getenv('XILINX_VITIS') else None
        self._amd_license = os.getenv('XILINXD_LICENSE_FILE')

        # If requested, check if Vivado is available and if the version matches the project
        if 'vivado' in required_tools and self._amd_vivado_path is None:
            pretty_print.print_error(f'Vivado could not be found. Please source Vivado.\n' \
                        '(The installation path is expected in environment variable \'XILINX_VIVADO\'.)')
            sys.exit(1)
        elif 'vivado' in required_tools:
            if self._amd_vivado_path.name != str(self._pc_xilinx_version):
                pretty_print.print_error(f'The sourced version of Vivado is \'{self._amd_vivado_path.name}\',' \
                            f' but this project requires version \'{self._pc_xilinx_version}\'.')
                sys.exit(1)
            self._amd_tools_path = self._amd_vivado_path.parent.parent

        # If requested, check if Vitis is available and if the version matches the project
        if 'vitis' in required_tools and self._amd_vitis_path is None:
            pretty_print.print_error(f'Vitis could not be found. Please source Vitis.\n' \
                        '(The installation path is expected in environment variable \'XILINX_VITIS\'.)')
            sys.exit(1)
        elif 'vitis' in required_tools:
            if self._amd_vitis_path.name != str(self._pc_xilinx_version):
                pretty_print.print_error(f'The sourced version of Vitis is \'{self._amd_vitis_path.name}\',' \
                            f' but this project requires version \'{self._pc_xilinx_version}\'.')
                sys.exit(1)
            self._amd_tools_path = self._amd_vivado_path.parent.parent

        # Check if the license was found
        if 'vitis' in required_tools and self._amd_vitis_path is None:
            pretty_print.print_error(f'AMD Xilinx license could not be found. It was expected in ' \
                        'environment variable \'XILINXD_LICENSE_FILE\'.')
            sys.exit(1)


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

        self.check_amd_tools(required_tools=['vivado', 'vitis'])

        potential_mounts = [(self._xsa_dir, 'Z'), (pathlib.Path(self._amd_tools_path), 'ro'), (self._repo_dir, 'Z'),
                    (self._work_dir, 'Z'), (self._output_dir, 'Z')]

        super(Builder, self).start_container(potential_mounts=potential_mounts)


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

        xsa_files = list((self._dependencies_dir / 'vivado').glob('*.xsa'))

        # Check if there is more than one XSA file in the xsa directory
        if len(xsa_files) != 1:
            pretty_print.print_error(f'Not exactly one XSA archive in {self._dependencies_dir / "vivado"}.')
            sys.exit(1)

        # Check whether the xsa archive needs to be imported
        if not AMD_Builder._check_rebuild_required(src_search_list=[xsa_files[0]], out_search_list=[self._xsa_dir]):
            pretty_print.print_build('No need to import XSA archive. No altered source files detected...')
            return
        
        # Clean source xsa directory
        self.clean_source_xsa()
        self._xsa_dir.mkdir(parents=True)

        pretty_print.print_build('Importing XSA archive...')

        # Copy XSA archive
        shutil.copy(xsa_files[0], self._xsa_dir / xsa_files[0].name)


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
            pretty_print.print_clean('Cleaning source_xsa directory...')

            cleaning_commands = f'\"rm -rf {self._xsa_dir}/* {self._xsa_dir}/.* 2> /dev/null || true\"'

            self.run_containerizable_sh_command(command=cleaning_commands,
                        dirs_to_mount=[(self._xsa_dir, 'Z')])

            # Remove empty source_xsa directory
            self._xsa_dir.rmdir()

        else:
            pretty_print.print_clean('No need to clean the source_xsa directory...')