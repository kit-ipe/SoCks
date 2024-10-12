import sys
import pathlib

import socks.pretty_print as pretty_print
from socks.amd_builder import AMD_Builder

class ZynqMP_AMD_Vivado_Hog_Builder_Alma9(AMD_Builder):
    """
    Builder class for AMD Vivado projects utilizing the Hog framework
    """

    def __init__(self, project_cfg: dict, project_cfg_files: list, socks_dir: pathlib.Path, project_dir: pathlib.Path):
        block_id = 'vivado'
        block_description = 'Build an AMD/Xilinx Vivado Project with HDL on git (Hog)'

        super().__init__(project_cfg=project_cfg,
                        project_cfg_files=project_cfg_files,
                        socks_dir=socks_dir,
                        project_dir=project_dir,
                        block_id=block_id,
                        block_description=block_description)

        # Check if the project configuration contains all optional settings that are required for this block. This only covers settings that cannot be checked with the schema because they are not required by all builders for this block_id.
        if self._pc_project_source is None:
            pretty_print.print_error(f'Builder {self.__class__.__name__} expects a single object and not an array in blocks/{self.block_id}/project/build-srcs.')
            sys.exit(1)

        # Import project configuration
        self._pc_project_name = project_cfg['blocks'][self.block_id]['project']['name']

        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        self.block_cmds = {
            'prepare': [],
            'build': [],
            'clean': [],
            'start-container': [],
            'start-vivado-gui': []
        }
        self.block_cmds['clean'].extend([self.build_container_image, self.clean_download, self.clean_work, self.clean_repo, self.clean_output, self.clean_block_temp])
        if self._pc_block_source == 'build':
            self.block_cmds['prepare'].extend([self.build_container_image, self.init_repo, self.create_vivado_project])
            self.block_cmds['build'].extend(self.block_cmds['prepare'])
            self.block_cmds['build'].extend([self.build_vivado_project, self.export_block_package])
            self.block_cmds['start-container'].extend([self.build_container_image, self.start_container])
            self.block_cmds['start-vivado-gui'].extend([self.build_container_image, self.start_vivado_gui])
        elif self._pc_block_source == 'import':
            self.block_cmds['build'].extend([self.import_prebuilt])


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

        # Check if the Vivado project needs to be created
        if (self._source_repo_dir / 'Projects' / self._pc_project_name).is_dir():
            pretty_print.print_build('The Vivado Project already exists. It will not be recreated...')
            return

        # Check if Xilinx tools are available
        if not pathlib.Path(self._pc_xilinx_path).is_dir():
            pretty_print.print_error(f'Directory {self._pc_xilinx_path} not found.')
            sys.exit(1)

        pretty_print.print_build('Creating the Vivado Project...')

        create_vivado_project_commands = f'\'export XILINXD_LICENSE_FILE={self._pc_xilinx_license} && ' \
                                            f'source {self._pc_xilinx_path}/Vivado/{self._pc_xilinx_version}/settings64.sh && ' \
                                            f'git config --global --add safe.directory {self._source_repo_dir} && ' \
                                            f'git config --global --add safe.directory {self._source_repo_dir}/Hog && ' \
                                            f'LD_PRELOAD=/lib64/libudev.so.1 {self._source_repo_dir}/Hog/Do CREATE {self._pc_project_name}\''

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
            self._err_unsup_container_tool()


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

        # Check if the project needs to be build
        if not ZynqMP_AMD_Vivado_Hog_Builder_Alma9._check_rebuilt_required(src_search_list=self._project_cfg_files + [self._source_repo_dir / 'Top', self._source_repo_dir / 'Hog', self._source_repo_dir / f'lib_{self._pc_project_name}'], out_search_list=[self._source_repo_dir / 'bin']):
            pretty_print.print_build('No need to rebuild the Vivado Project. No altered source files detected...')
            return

        # Check if Xilinx tools are available
        if not pathlib.Path(self._pc_xilinx_path).is_dir():
            pretty_print.print_error(f'Directory {self._pc_xilinx_path} not found.')
            sys.exit(1)

        # Clean output directory
        self.clean_output()
        self._output_dir.mkdir(parents=True)

        pretty_print.print_build('Building the Vivado Project...')

        vivado_build_commands = f'\'rm -rf {self._source_repo_dir}/bin' \
                                f'export XILINXD_LICENSE_FILE={self._pc_xilinx_license} && ' \
                                f'source {self._pc_xilinx_path}/Vivado/{self._pc_xilinx_version}/settings64.sh && ' \
                                f'git config --global --add safe.directory {self._source_repo_dir} && ' \
                                f'git config --global --add safe.directory {self._source_repo_dir}/Hog && ' \
                                f'LD_PRELOAD=/lib64/libudev.so.1 {self._source_repo_dir}/Hog/Do WORKFLOW {self._pc_project_name}\''

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
            self._err_unsup_container_tool()

        # Create symlinks to the output files
        xsa_files = list(self._source_repo_dir.glob(f'bin/{self._pc_project_name}-*/{self._pc_project_name}-*.xsa'))
        if len(xsa_files) != 1:
            pretty_print.print_error(f'Unexpected number of {len(xsa_files)} *.xsa files in output direct. Expected was 1.')
            sys.exit(1)
        (self._output_dir / xsa_files[0].name).symlink_to(xsa_files[0])


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

        # Check if Xilinx tools are available
        if not pathlib.Path(self._pc_xilinx_path).is_dir():
            pretty_print.print_error(f'Directory {self._pc_xilinx_path} not found.')
            sys.exit(1)

        # Check if x11docker is installed
        results = ZynqMP_AMD_Vivado_Hog_Builder_Alma9._get_sh_results(['command', '-v', 'x11docker'])
        if not results.stdout:
            pretty_print.print_error('Command \'x11docker\' not found. Install x11docker (https://github.com/mviereck/x11docker).')
            sys.exit(1)

        pretty_print.print_build('Starting container...')

        start_vivado_gui_commands = f'\'export XILINXD_LICENSE_FILE={self._pc_xilinx_license} && ' \
                                    f'source {self._pc_xilinx_path}/Vivado/{self._pc_xilinx_version}/settings64.sh && ' \
                                    f'vivado -nojournal -nolog {self._source_repo_dir}/Projects/{self._pc_project_name}/{self._pc_project_name}.xpr && ' \
                                    f'exit\''

        try:
            if self._pc_container_tool  == 'docker':
                ZynqMP_AMD_Vivado_Hog_Builder_Alma9._run_sh_command(['x11docker' , '--backend=docker', '--interactive', '--network', '--clipboard=yes', '--xauth=trusted', '--user=RETAIN', '--share', f'{self._pc_xilinx_path}:ro', '--share', str(self._repo_dir), '--share', str(self._output_dir), self._container_image, f'--runasuser={start_vivado_gui_commands}'])
            elif self._pc_container_tool  == 'podman':
                ZynqMP_AMD_Vivado_Hog_Builder_Alma9._run_sh_command(['x11docker' , '--backend=podman', '--interactive', '--network', '--clipboard=yes', '--xauth=trusted', '--cap-default', '--user=RETAIN', '--share', f'{self._pc_xilinx_path}:ro', '--share', str(self._repo_dir), '--share', str(self._output_dir), self._container_image, f'--runasuser={start_vivado_gui_commands}'])
            elif self._pc_container_tool  == 'none':
                # This function is only supported if a container tool is used
                ZynqMP_AMD_Vivado_Hog_Builder_Alma9._err_container_feature(f'{inspect.getframeinfo(inspect.currentframe()).function}()')
            else:
                self._err_unsup_container_tool()
        except Exception as e:
                pretty_print.print_error(f'An error occurred while starting the container: {e}')
                sys.exit(1)