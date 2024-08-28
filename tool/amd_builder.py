import pathlib
import shutil

import pretty_print
import builder

class AMD_Builder(builder.Builder):
    """
    Base class for all builder classes that use AMD Xilinx tools
    """

    def __init__(self, project_cfg: dict, socks_dir: pathlib.Path, project_dir: pathlib.Path, block_name: str):

        super().__init__(project_cfg=project_cfg,
                        socks_dir=socks_dir,
                        project_dir=project_dir,
                        block_name=block_name)

        # Toolset directories
        self._xilinx_tools_dir = pathlib.Path(self._project_cfg['externalTools']['xilinx']['path'])

        # Project directories
        self._xsa_dir = self._project_temp_dir / self._block_name / 'source_xsa'


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

        potential_mounts = [f'{str(self._xsa_dir)}:Z', f'{str(self._xilinx_tools_dir)}:ro', f'{str(self._repo_dir)}:Z', f'{str(self._work_dir)}:Z', f'{str(self._output_dir)}:Z']

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

        # Get path to XSA archive
        xsa_path = pathlib.Path(self._project_dir / self._project_cfg['blocks'][self._block_name]['project']['dependencies']['xsa'])

        if not xsa_path.is_file():
            pretty_print.print_error(f'XSA archive {xsa_path} not found')
            sys.exit(1)
        
        if xsa_path.suffix != '.xsa':
            pretty_print.print_error(f'The extension of the file {xsa_path} is not \'xsa\'')
            sys.exit(1)
        
        # Clean source xsa directory
        AMD_Builder.clean_source_xsa(self=self)
        self._xsa_dir.mkdir(parents=True, exist_ok=True)

        pretty_print.print_build('Importing the *.xsa source file...')

        # Copy XSA archive
        shutil.copy(xsa_path, self._xsa_dir / xsa_path.name)


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
            if self._container_tool in ('docker', 'podman'):
                try:
                    # Clean up the source_xsa directory from the container
                    AMD_Builder._run_sh_command([self._container_tool, 'run', '--rm', '-it', '-v', f'{str(self._xsa_dir)}:/app/source_xsa:Z', self._container_image, 'sh', '-c', '\"rm -rf /app/source_xsa/* /app/source_xsa/.* 2> /dev/null || true\"'])
                except Exception as e:
                    pretty_print.print_error(f'An error occurred while cleaning the source_xsa directory: {str(e)}')
                    sys.exit(1)

            elif self._container_tool == 'none':
                # Clean up the source_xsa directory without using a container
                AMD_Builder._run_sh_command(['sh', '-c', f'\"rm -rf {str(self._xsa_dir)}/* {str(self._xsa_dir)}/.* 2> /dev/null || true\"'])
            else:
                AMD_Builder._err_unsup_container_tool()

            # Remove empty source_xsa directory
            self._xsa_dir.rmdir()

        else:
            pretty_print.print_clean('No need to clean the source_xsa directory...')