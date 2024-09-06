import sys
import pathlib

import pretty_print
import amd_builder

class ZynqMP_AMD_Vivado_Hog_Builder_Alma9(amd_builder.AMD_Builder):
    """
    Builder class for AMD Vivado projects utilizing the Hog framework
    """

    def __init__(self, project_cfg: dict, socks_dir: pathlib.Path, project_dir: pathlib.Path):
        block_name = 'vivado'

        super().__init__(project_cfg=project_cfg,
                        socks_dir=socks_dir,
                        project_dir=project_dir,
                        block_name=block_name)

        # Import project configuration
        self._pc_project_name = project_cfg['blocks'][self._block_name]['project']['name']


    def create_vivado_project(self):
        """
        Create the Vivado project utilizing the Hog framework.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        create_vivado_project_commands = f'\'export XILINXD_LICENSE_FILE={self._pc_xilinx_license} && ' \
                                            f'source {self._pc_xilinx_path}/Vivado/{self._pc_xilinx_version}/settings64.sh && ' \
                                            f'git config --global --add safe.directory {self._source_repo_dir} && ' \
                                            f'git config --global --add safe.directory {self._source_repo_dir}/Hog && ' \
                                            f'LD_PRELOAD=/lib64/libudev.so.1 {self._source_repo_dir}/Hog/Do CREATE {self._pc_project_name}\''

        # Check if the Vivado project needs to be created
        if (self._source_repo_dir / 'Projects' / self._pc_project_name).is_dir():
            pretty_print.print_build('The Vivado Project already exists. It will not be recreated...')
            return

        pretty_print.print_build('Creating the Vivado Project...')

        # Check if Xilinx tools are available
        if not pathlib.Path(self._pc_xilinx_path).is_dir():
            pretty_print.print_error(f'Directory {self._pc_xilinx_path} not found.')
            sys.exit(1)
        
        if self._pc_container_tool  in ('docker', 'podman'):
            try:
                # Run commands in container
                ZynqMP_AMD_Vivado_Hog_Builder_Alma9._run_sh_command([self._pc_container_tool , 'run', '--rm', '-it', '-v', f'{self._pc_xilinx_path}:{self._pc_xilinx_path}:ro', '-v', f'{self._repo_dir}:{self._repo_dir}:Z', '-v', f'{self._output_dir}:{self._output_dir}:Z', self._container_image, 'sh', '-c', create_vivado_project_commands])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while creating the vivado project: {e}')
                sys.exit(1)
        elif self._pc_container_tool  == 'none':
            # Run commands without using a container
            ZynqMP_AMD_Vivado_Hog_Builder_Alma9._run_sh_command(['sh', '-c', create_vivado_project_commands])
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

        vivado_build_commands = f'\'rm -rf {self._source_repo_dir}/bin' \
                                f'export XILINXD_LICENSE_FILE={self._pc_xilinx_license} && ' \
                                f'source {self._pc_xilinx_path}/Vivado/{self._pc_xilinx_version}/settings64.sh && ' \
                                f'git config --global --add safe.directory {self._source_repo_dir} && ' \
                                f'git config --global --add safe.directory {self._source_repo_dir}/Hog && ' \
                                f'LD_PRELOAD=/lib64/libudev.so.1 {self._source_repo_dir}/Hog/Do WORKFLOW {self._pc_project_name}\''

        # Check if the project needs to be build
        if not ZynqMP_AMD_Vivado_Hog_Builder_Alma9._check_rebuilt_required(src_search_list=[self._source_repo_dir / 'Top', self._source_repo_dir / 'Hog', self._source_repo_dir / f'lib_{self._pc_project_name}'], out_search_list=[self._source_repo_dir / 'bin']):
            pretty_print.print_build('No need to rebuild the Vivado Project. No altered source files detected...')
            return

        pretty_print.print_build('Building the Vivado Project...')

        # Check if Xilinx tools are available
        if not pathlib.Path(self._pc_xilinx_path).is_dir():
            pretty_print.print_error(f'Directory {self._pc_xilinx_path} not found.')
            sys.exit(1)

        # Clean output directory
        ZynqMP_AMD_Vivado_Hog_Builder_Alma9.clean_output(self=self)
        self._output_dir.mkdir(parents=True)

        if self._pc_container_tool  in ('docker', 'podman'):
            try:
                # Run commands in container
                ZynqMP_AMD_Vivado_Hog_Builder_Alma9._run_sh_command([self._pc_container_tool , 'run', '--rm', '-it', '-v', f'{self._pc_xilinx_path}:{self._pc_xilinx_path}:ro', '-v', f'{self._repo_dir}:{self._repo_dir}:Z', '-v', f'{self._output_dir}:{self._output_dir}:Z', self._container_image, 'sh', '-c', vivado_build_commands])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while building the vivado project: {e}')
                sys.exit(1)
        elif self._pc_container_tool  == 'none':
            # Run commands without using a container
            ZynqMP_AMD_Vivado_Hog_Builder_Alma9._run_sh_command(['sh', '-c', vivado_build_commands])
        else:
            Builder._err_unsup_container_tool()

        # Create symlinks to the output files
        xsa_files = list(self._source_repo_dir.glob(f'bin/{self._pc_project_name}-*/{self._pc_project_name}-*.xsa'))
        if len(xsa_files) != 1:
            pretty_print.print_error(f'Unexpected number of {len(xsa_files)} *.xsa files in output direct. Expected was 1.')
            sys.exit(1)
        (self._output_dir / xsa_files[0].name).symlink_to(xsa_files[0])
        (self._output_dir / 'system.xsa').symlink_to(self._output_dir / xsa_files[0].name)

        bit_files = list(self._source_repo_dir.glob(f'bin/{self._pc_project_name}-*/{self._pc_project_name}-*.bit'))
        if len(bit_files) != 1:
            pretty_print.print_error(f'Unexpected number of {len(bit_files)} *.bit files in output direct. Expected was 1.')
            sys.exit(1)
        (self._output_dir / bit_files[0].name).symlink_to(bit_files[0])
        (self._output_dir / 'system.bit').symlink_to(self._output_dir / bit_files[0].name)