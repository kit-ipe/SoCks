import sys
import pathlib

import socks.pretty_print as pretty_print
from socks.amd_builder import AMD_Builder

class ZynqMP_AMD_Vivado_IPBB_Builder_Alma9(AMD_Builder):
    """
    Builder class for AMD Vivado projects utilizing the IPbus Builder (IPBB) framework
    """

    def __init__(self, project_cfg: dict, project_cfg_files: list, socks_dir: pathlib.Path, project_dir: pathlib.Path, block_id: str = 'vivado', block_description: str = 'Build an AMD/Xilinx Vivado Project with IPbus Builder (IPBB)'):

        super().__init__(project_cfg=project_cfg,
                        project_cfg_files=project_cfg_files,
                        socks_dir=socks_dir,
                        project_dir=project_dir,
                        block_id=block_id,
                        block_description=block_description)

        # Import project configuration
        self._pc_project_sources = []
        self._pc_project_branches = []
        for item in project_cfg['blocks'][self.block_id]['project']['build-srcs']:
            self._pc_project_sources.append(item['source'])
            if 'branch' in item:
                self._pc_project_branches.append(item['branch'])
            else:
                self._pc_project_branches.append(None)
        self._pc_project_name = project_cfg['blocks'][self.block_id]['project']['name']

        # Find sources for this block
        self._source_repo_urls, self._source_repo_branches, self._local_source_dirs = self._get_multiple_sources()

        self._ipbb_work_dir_name = 'ipbb-work'

        # Project directories
        self._ipbb_work_dir = self._repo_dir / self._ipbb_work_dir_name

        # Project files
        # Flag to remember if IPBB has already been initialized
        self._ipbb_init_done_flag = self._block_temp_dir / '.ipbbinitdone'

        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        self.block_cmds = {
            'prepare': [],
            'build': [],
            'clean': [],
            'start-container': [],
            'start-vivado-gui': []
        }
        self.block_cmds['clean'].extend([self.build_container_image, self.clean_download, self.clean_repo, self.clean_output, self.clean_block_temp])
        if self._pc_block_source == 'build':
            self.block_cmds['prepare'].extend([self.build_container_image, self.init_repo, self.create_vivado_project])
            self.block_cmds['build'].extend(self.block_cmds['prepare'])
            self.block_cmds['build'].extend([self.build_vivado_project, self.export_block_package])
            self.block_cmds['start-container'].extend([self.build_container_image, self.start_container])
            self.block_cmds['start-vivado-gui'].extend([self.build_container_image, self.start_vivado_gui])
        elif self._pc_block_source == 'import':
            self.block_cmds['build'].extend([self.import_prebuilt])


    def init_repo(self):
        """
        Initialize the IPBB environment.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Skip all operations if the IPBB environment is already initialized
        if self._ipbb_init_done_flag.exists():
            pretty_print.print_build('The IPBB environment has already been initialized. It is not reinitialized...')
            return

        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._repo_dir.mkdir(parents=True, exist_ok=True)

        pretty_print.print_build('Initializing the IPBB environment...')

        init_ipbb_env_commands = '\'source ~/tools/ipbb-*/env.sh && ' \
                                f'cd {self._repo_dir} && ' \
                                f'ipbb init {self._ipbb_work_dir_name} && ' \
                                f'cd {self._ipbb_work_dir}'

        # ToDo: It is also possible to use local repos with 'ipbb add symlink ...'. This needs to be implemented if we want to support local block sources.  
        for index in range(len(self._source_repo_urls)):
            if not self._source_repo_branches[index].startswith(('-b ', '-r ')):
                pretty_print.print_error(f'Entries in blocks/{self.block_id}/project/build-srcs[N]/branch have to start with \'-b \' for branches and tags or with \'-r \' for commit ids.')
                sys.exit(1)
            init_ipbb_env_commands = init_ipbb_env_commands + f' && ipbb add git {self._source_repo_urls[index]} {self._source_repo_branches[index]}'

        init_ipbb_env_commands = init_ipbb_env_commands + '\''

        self.run_containerizable_sh_command(command=init_ipbb_env_commands,
                    dirs_to_mount=[(self._repo_dir, 'Z')],
                    custom_params=['-v', '$SSH_AUTH_SOCK:/ssh-auth-sock', '--env', 'SSH_AUTH_SOCK=/ssh-auth-sock'])

        # Create the flag if it doesn't exist and update the timestamps
        self._ipbb_init_done_flag.touch()


    def create_vivado_project(self):
        """
        Create the Vivado project utilizing the IPbus Builder framework.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check if the Vivado project needs to be created
        if (self._ipbb_work_dir / 'proj' / self._pc_project_name).is_dir():
            pretty_print.print_build('The Vivado Project already exists. It will not be recreated...')
            return

        # Check if Xilinx tools are available
        if not pathlib.Path(self._pc_xilinx_path).is_dir():
            pretty_print.print_error(f'Directory {self._pc_xilinx_path} not found.')
            sys.exit(1)

        pretty_print.print_build('Creating the Vivado Project...')

        create_vivado_project_commands = '\'source ~/tools/ipbb-*/env.sh && ' \
                                            f'cd {self._ipbb_work_dir} && ' \
                                            f'ipbb toolbox check-dep vivado serenity-s1-k26c-fw:projects/{self._pc_project_name} top.dep && ' \
                                            f'ipbb proj create vivado {self._pc_project_name} serenity-s1-k26c-fw:projects/{self._pc_project_name} && ' \
                                            f'cd proj/{self._pc_project_name} && ' \
                                            'export LD_LIBRARY_PATH=/opt/cactus/lib:\$$LD_LIBRARY_PATH PATH=/opt/cactus/bin/uhal/tools:\$$PATH && ' \
                                            'ipbb ipbus gendecoders -c && ' \
                                            f'export XILINXD_LICENSE_FILE={self._pc_xilinx_license} && ' \
                                            f'source {self._pc_xilinx_path}/Vivado/{self._pc_xilinx_version}/settings64.sh && ' \
                                            'LD_PRELOAD=/lib64/libudev.so.1 ipbb vivado generate-project\''

        self.run_containerizable_sh_command(command=create_vivado_project_commands,
                    dirs_to_mount=[(pathlib.Path(self._pc_xilinx_path), 'ro'), (self._repo_dir, 'Z')])


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
        if not ZynqMP_AMD_Vivado_IPBB_Builder_Alma9._check_rebuild_required(src_search_list=self._project_cfg_files + [self._ipbb_work_dir / 'src', self._ipbb_work_dir / 'var', self._ipbb_work_dir / 'proj' / self._pc_project_name / 'decoders', self._ipbb_work_dir / 'proj' / self._pc_project_name / self._pc_project_name], src_ignore_list=[self._ipbb_work_dir / 'proj' / self._pc_project_name / self._pc_project_name / f'{self._pc_project_name}.runs', self._ipbb_work_dir / 'proj' / self._pc_project_name / self._pc_project_name / f'{self._pc_project_name}.cache'], out_search_list=[self._ipbb_work_dir / 'proj' / self._pc_project_name / 'package']):
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

        vivado_build_commands = '\'source ~/tools/ipbb-*/env.sh && ' \
                                f'export XILINXD_LICENSE_FILE={self._pc_xilinx_license} && ' \
                                f'source {self._pc_xilinx_path}/Vivado/{self._pc_xilinx_version}/settings64.sh && ' \
                                f'cd {self._ipbb_work_dir}/proj/{self._pc_project_name} && ' \
                                'LD_PRELOAD=/lib64/libudev.so.1 ipbb vivado check-syntax && ' \
                                f'LD_PRELOAD=/lib64/libudev.so.1 ipbb vivado synth -j{self._pc_vivado_threads} impl -j{self._pc_vivado_threads} && ' \
                                'LD_PRELOAD=/lib64/libudev.so.1 ipbb vivado bitfile package\''

        self.run_containerizable_sh_command(command=vivado_build_commands,
                    dirs_to_mount=[(pathlib.Path(self._pc_xilinx_path), 'ro'), (self._repo_dir, 'Z')])

        # Create symlinks to the output files
        for item in (self._ipbb_work_dir / 'proj' / self._pc_project_name / 'package' / 'src').glob('*'):
            (self._output_dir / item.name).symlink_to(item)


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

        start_vivado_gui_commands = f'\'export XILINXD_LICENSE_FILE={self._pc_xilinx_license} && ' \
                                    f'source {self._pc_xilinx_path}/Vivado/{self._pc_xilinx_version}/settings64.sh && ' \
                                    f'vivado -nojournal -nolog {self._ipbb_work_dir}/proj/{self._pc_project_name}/{self._pc_project_name}/{self._pc_project_name}.xpr && ' \
                                    f'exit\''

        self.start_gui_container(start_gui_command=start_vivado_gui_commands,
                    potential_mounts=[(pathlib.Path(self._pc_xilinx_path), 'ro'), (self._repo_dir, 'Z'),
                                (self._output_dir, 'Z')])