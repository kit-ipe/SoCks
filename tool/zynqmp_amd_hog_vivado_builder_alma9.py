import sys
import pathlib

import pretty_print
import builder

class ZynqMP_AMD_Hog_Vivado_Builder_Alma9(builder.Builder):
    """
    Builder class for Vivado projects utilizing the Hog framework
    """

    def __init__(self, project_cfg: dict, socks_dir: pathlib.Path, project_dir: pathlib.Path):
        block_name = 'vivado'

        super().__init__(project_cfg=project_cfg,
                        socks_dir=socks_dir,
                        project_dir=project_dir,
                        block_name=block_name)

        self._xilinx_tools_path = pathlib.Path(self._project_cfg['externalTools']['xilinx']['path'])


    def start_container(self):
        """
        Start an interactive container with which the block can be built.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """
 
        potential_mounts=[f'{str(self._xilinx_tools_path)}:ro', f'{str(self._repo_dir)}:Z', f'{str(self._output_dir)}:Z']
 
        ZynqMP_AMD_Hog_Vivado_Builder_Alma9._start_container(self, potential_mounts=potential_mounts)


    def vivado_project(self):
        """
        Create the Vivado project utilizing the Hog framework

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        create_vivado_project_commands = f'\'export XILINXD_LICENSE_FILE={self._project_cfg["externalTools"]["xilinx"]["license"]} && ' \
                                            f'source {str(self._xilinx_tools_path)}/Vivado/{self._project_cfg["externalTools"]["xilinx"]["version"]}/settings64.sh && ' \
                                            f'git config --global --add safe.directory {str(self._source_repo_dir)} && ' \
                                            f'git config --global --add safe.directory {str(self._source_repo_dir)}/Hog && ' \
                                            f'LD_PRELOAD=/lib64/libudev.so.1 {str(self._source_repo_dir)}/Hog/Do CREATE {self._project_cfg["blocks"]["vivado"]["project"]["name"]}\''

        # Check if the Vivado project needs to be created
        if (self._source_repo_dir / 'Projects' / self._project_cfg['blocks']['vivado']['project']['name']).is_dir():
            pretty_print.print_build('The Vivado Project already exists. It will not be recreated...')
            return

        if not self._xilinx_tools_path.is_dir():
            pretty_print.print_error(f'Directory {str(self._xilinx_tools_path)} not found.')
            sys.exit(1)

        pretty_print.print_build('Creating the Vivado Project...')
        
        if self._container_tool in ('docker', 'podman'):
            try:
                # Run build commands in container
                ZynqMP_AMD_Hog_Vivado_Builder_Alma9._run_sh_command([self._container_tool, 'run', '--rm', '-it', '-v', f'{str(self._xilinx_tools_path)}:{str(self._xilinx_tools_path)}:ro', '-v', f'{str(self._repo_dir)}:{str(self._repo_dir)}:Z', '-v', f'{str(self._output_dir)}:{str(self._output_dir)}:Z', self._container_image, 'sh', '-c', create_vivado_project_commands])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while creating the vivado project: {str(e)}')
                sys.exit(1)
        elif self._container_tool == 'none':
            # Run build commands without using a container
            ZynqMP_AMD_Hog_Vivado_Builder_Alma9._run_sh_command(['sh', '-c', create_vivado_project_commands])
        else:
            Builder._err_unsup_container_tool()


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

        vivado_build_commands = f'\'rm -rf {str(self._source_repo_dir)}/bin' \
                                f'export XILINXD_LICENSE_FILE={self._project_cfg["externalTools"]["xilinx"]["license"]} && ' \
                                f'source {str(self._xilinx_tools_path)}/Vivado/{self._project_cfg["externalTools"]["xilinx"]["version"]}/settings64.sh && ' \
                                f'git config --global --add safe.directory {str(self._source_repo_dir)} && ' \
                                f'git config --global --add safe.directory {str(self._source_repo_dir)}/Hog && ' \
                                f'LD_PRELOAD=/lib64/libudev.so.1 {str(self._source_repo_dir)}/Hog/Do WORKFLOW {self._project_cfg["blocks"]["vivado"]["project"]["name"]}\''

        # Check if the project needs to be build
        if not ZynqMP_AMD_Hog_Vivado_Builder_Alma9._check_rebuilt_required(src_search_list=[self._source_repo_dir / 'Top', self._source_repo_dir / 'Hog', self._source_repo_dir / f'lib_{self._project_cfg["blocks"]["vivado"]["project"]["name"]}'], out_search_list=[self._source_repo_dir / 'bin']):
            pretty_print.print_build('No need to rebuild the Vivado Project. No altered source files detected...')
            return

        if not self._xilinx_tools_path.is_dir():
            pretty_print.print_error(f'Directory {str(self._xilinx_tools_path)} not found.')
            sys.exit(1)

        # Clean output
        ZynqMP_AMD_Hog_Vivado_Builder_Alma9.clean_output(self)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        
        pretty_print.print_build('Building the Vivado Project...')

        if self._container_tool in ('docker', 'podman'):
            try:
                # Run build commands in container
                ZynqMP_AMD_Hog_Vivado_Builder_Alma9._run_sh_command([self._container_tool, 'run', '--rm', '-it', '-v', f'{str(self._xilinx_tools_path)}:{str(self._xilinx_tools_path)}:ro', '-v', f'{str(self._repo_dir)}:{str(self._repo_dir)}:Z', '-v', f'{str(self._output_dir)}:{str(self._output_dir)}:Z', self._container_image, 'sh', '-c', vivado_build_commands])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while creating the vivado project: {str(e)}')
                sys.exit(1)
        elif self._container_tool == 'none':
            # Run build commands without using a container
            ZynqMP_AMD_Hog_Vivado_Builder_Alma9._run_sh_command(['sh', '-c', vivado_build_commands])
        else:
            Builder._err_unsup_container_tool()

        # Create symlinks to the output files
        xsa_files = list(self._source_repo_dir.glob(f'bin/{self._project_cfg["blocks"]["vivado"]["project"]["name"]}-*/{self._project_cfg["blocks"]["vivado"]["project"]["name"]}-*.xsa'))
        if len(xsa_files) != 1:
            pretty_print.print_error(f'Unexpected number of {len(xsa_files)} *.xsa files in output direct. Expected was 1.')
            sys.exit(1)
        (self._output_dir / xsa_files[0].name).symlink_to(xsa_files[0])
        (self._output_dir / 'system.xsa').symlink_to(self._output_dir / xsa_files[0].name)

        bit_files = list(self._source_repo_dir.glob(f'bin/{self._project_cfg["blocks"]["vivado"]["project"]["name"]}-*/{self._project_cfg["blocks"]["vivado"]["project"]["name"]}-*.bit'))
        if len(bit_files) != 1:
            pretty_print.print_error(f'Unexpected number of {len(bit_files)} *.xsa files in output direct. Expected was 1.')
            sys.exit(1)
        (self._output_dir / bit_files[0].name).symlink_to(bit_files[0])
        (self._output_dir / 'system.bit').symlink_to(self._output_dir / bit_files[0].name)