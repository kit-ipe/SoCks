import pathlib
import shutil
import sys

import socks.pretty_print as pretty_print
from socks.builder import Builder

class AMD_Builder(Builder):
    """
    Base class for all builder classes that use AMD Xilinx tools
    """

    def __init__(self, project_cfg: dict, socks_dir: pathlib.Path, project_dir: pathlib.Path, block_id: str, block_description: str):

        super().__init__(project_cfg=project_cfg,
                        socks_dir=socks_dir,
                        project_dir=project_dir,
                        block_id=block_id,
                        block_description=block_description)

        # Import project configuration
        self._pc_xilinx_path = project_cfg['externalTools']['xilinx']['path']
        self._pc_xilinx_version = project_cfg["externalTools"]["xilinx"]["version"]
        self._pc_xilinx_license = project_cfg["externalTools"]["xilinx"]["license"]

        # Project directories
        self._xsa_dir = self._project_temp_dir / self.block_id / 'source_xsa'

        # Project files
        # File for saving the checksum of the XSA-file on which the project is based
        self._source_xsa_md5_file = self._work_dir / 'source_xsa.md5'


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

        potential_mounts = [f'{self._xsa_dir}:Z', f'{self._pc_xilinx_path}:ro', f'{self._repo_dir}:Z', f'{self._work_dir}:Z', f'{self._output_dir}:Z']

        AMD_Builder._start_container(self, potential_mounts=potential_mounts)


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
        if not AMD_Builder._check_rebuilt_required(src_search_list=[xsa_files[0]], out_search_list=[self._xsa_dir]):
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
            if self._pc_container_tool  in ('docker', 'podman'):
                try:
                    # Clean up the source_xsa directory from the container
                    AMD_Builder._run_sh_command([self._pc_container_tool , 'run', '--rm', '-it', '-v', f'{self._xsa_dir}:/app/source_xsa:Z', self._container_image, 'sh', '-c', '\"rm -rf /app/source_xsa/* /app/source_xsa/.* 2> /dev/null || true\"'])
                except Exception as e:
                    pretty_print.print_error(f'An error occurred while cleaning the source_xsa directory: {e}')
                    sys.exit(1)

            elif self._pc_container_tool  == 'none':
                # Clean up the source_xsa directory without using a container
                AMD_Builder._run_sh_command(['sh', '-c', f'\"rm -rf {self._xsa_dir}/* {self._xsa_dir}/.* 2> /dev/null || true\"'])
            else:
                self._err_unsup_container_tool()

            # Remove empty source_xsa directory
            self._xsa_dir.rmdir()

        else:
            pretty_print.print_clean('No need to clean the source_xsa directory...')