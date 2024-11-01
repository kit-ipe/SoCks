import sys
import pathlib
import urllib

import socks.pretty_print as pretty_print
from socks.builder import Builder

class ZynqMP_AMD_Kernel_Builder_Alma9(Builder):
    """
    AMD Kernel builder class
    """

    def __init__(self, project_cfg: dict, project_cfg_files: list, socks_dir: pathlib.Path, project_dir: pathlib.Path, block_id: str = 'kernel', block_description: str = 'Build the official AMD/Xilinx version of the Linux Kernel for ZynqMP devices'):

        super().__init__(project_cfg=project_cfg,
                        project_cfg_files=project_cfg_files,
                        socks_dir=socks_dir,
                        project_dir=project_dir,
                        block_id=block_id,
                        block_description=block_description)

        # Import project configuration
        self._pc_project_source = project_cfg['blocks'][self.block_id]['project']['build-srcs']['source']
        if 'branch' in project_cfg['blocks'][self.block_id]['project']['build-srcs']:
            self._pc_project_branch = project_cfg['blocks'][self.block_id]['project']['build-srcs']['branch']

        # Find sources for this block
        self._source_repo, self._local_source_dir = self._get_single_source()

        # Project directories
        self._source_repo_dir = self._repo_dir / f'{pathlib.Path(urllib.parse.urlparse(url=self._source_repo["url"]).path).stem}-{self._source_repo["branch"]}'

        # Project files
        # File for version & build info tracking
        self._build_info_file = self._source_repo_dir / 'include' / 'build_info.h'

        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        self.block_cmds = {
            'prepare': [],
            'build': [],
            'clean': [],
            'create-patches': [],
            'start-container': [],
            'menucfg': [],
            'prep-clean-srcs': []
        }
        self.block_cmds['clean'].extend([self.build_container_image, self.clean_download, self.clean_work, self.clean_repo, self.clean_output, self.clean_block_temp])
        if self._pc_block_source == 'build':
            self.block_cmds['prepare'].extend([self.build_container_image, self.init_repo, self.apply_patches])
            self.block_cmds['build'].extend(self.block_cmds['prepare'])
            self.block_cmds['build'].extend([self.build_kernel, self.export_modules, self.export_block_package])
            self.block_cmds['create-patches'].extend([self.create_patches])
            self.block_cmds['start-container'].extend([self.build_container_image, self.start_container])
            self.block_cmds['menucfg'].extend([self.build_container_image, self.run_menuconfig])
            self.block_cmds['prep-clean-srcs'].extend(self.block_cmds['clean'])
            self.block_cmds['prep-clean-srcs'].extend([self.build_container_image, self.init_repo, self.prep_clean_srcs])
        elif self._pc_block_source == 'import':
            self.block_cmds['build'].extend([self.import_prebuilt])


    def run_menuconfig(self):
        """
        Opens the menuconfig tool to enable interactive configuration of the project.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        menuconfig_commands = f'\'cd {self._source_repo_dir} && ' \
                                'export CROSS_COMPILE=aarch64-linux-gnu- && ' \
                                'make ARCH=arm64 menuconfig\''

        super()._run_menuconfig(menuconfig_commands=menuconfig_commands)


    def prep_clean_srcs(self):
        """
        This function is intended to create a new, clean Linux kernel or U-Boot project. After the creation of the project you should create a patch that includes .gitignore and .config.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        prep_srcs_commands = f'\'cd {self._source_repo_dir} && ' \
                                'export CROSS_COMPILE=aarch64-linux-gnu- && ' \
                                'make ARCH=arm64 xilinx_zynqmp_defconfig && ' \
                                'printf \"\n# Do not ignore the config file\n!.config\n\" >> .gitignore\''

        super()._prep_clean_srcs(prep_srcs_commands=prep_srcs_commands)


    def build_kernel(self):
        """
        Builds the Linux Kernel.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check whether the Kernel needs to be built
        if not ZynqMP_AMD_Kernel_Builder_Alma9._check_rebuild_required(src_search_list=self._project_cfg_files + [self._patch_dir, self._source_repo_dir], src_ignore_list=[self._source_repo_dir / 'arch/arm64/boot'], out_search_list=[self._source_repo_dir / 'arch/arm64/boot']):
            pretty_print.print_build('No need to rebuild the Linux Kernel. No altered source files detected...')
            return

        pretty_print.print_build('Building Linux Kernel...')

        if self._pc_project_build_info_flag == True:
            # Add build information file
            with self._build_info_file.open('w') as f:
                print('const char *build_info = "', file=f, end='')
                print(self._compose_build_info().replace('\n', '\\n'), file=f, end='')
                print('";', file=f, end='')
        else:
            # Remove existing build information file
            self._build_info_file.unlink(missing_ok=True)

        kernel_build_commands = f'\'cd {self._source_repo_dir} && ' \
                                'export CROSS_COMPILE=aarch64-linux-gnu- && ' \
                                'make ARCH=arm64 olddefconfig && ' \
                                f'make ARCH=arm64 -j{self._pc_make_threads}\''

        self.run_containerizable_sh_command(command=kernel_build_commands,
                    dirs_to_mount=[(self._repo_dir, 'Z'), (self._output_dir, 'Z')])

        # Create symlink to the output files
        (self._output_dir / 'Image').unlink(missing_ok=True)
        (self._output_dir / 'Image').symlink_to(self._source_repo_dir / 'arch/arm64/boot/Image')
        (self._output_dir / 'Image.gz').unlink(missing_ok=True)
        (self._output_dir / 'Image.gz').symlink_to(self._source_repo_dir / 'arch/arm64/boot/Image.gz')


    def export_modules(self):
        """
        Exports all built Kernel modules.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check if Kernel sources are available
        if not self._source_repo_dir.is_dir():
            pretty_print.print_build('No output files to extract Kernel modules...')
            return

        # Check whether the Kernel modules need to be exported
        if not ZynqMP_AMD_Kernel_Builder_Alma9._check_rebuild_required(src_search_list=[self._patch_dir, self._source_repo_dir], src_ignore_list=[self._source_repo_dir / 'arch/arm64/boot'], out_search_list=[self._output_dir / 'kernel_modules.tar.gz']):
            pretty_print.print_build('No need to export Kernel modules. No altered source files detected...')
            return

        pretty_print.print_build('Exporting Kernel Modules...')

        export_modules_commands = f'\'cd {self._source_repo_dir} && ' \
                                'export CROSS_COMPILE=aarch64-linux-gnu- && ' \
                                f'make ARCH=arm64 modules_install INSTALL_MOD_PATH={self._output_dir} && ' \
                                f'find {self._output_dir}/lib -type l -delete && ' \
                                f'tar -P --xform=\'s:{self._output_dir}::\' --numeric-owner -p -czf {self._output_dir}/kernel_modules.tar.gz {self._output_dir}/lib && ' \
                                f'rm -rf {self._output_dir}/lib\''

        self.run_containerizable_sh_command(command=export_modules_commands,
                    dirs_to_mount=[(self._repo_dir, 'Z'), (self._output_dir, 'Z')])