import sys
import pathlib

import pretty_print
import builder

class ZynqMP_AMD_Kernel_Builder_Alma9(builder.Builder):
    """
    AMD Kernel builder class
    """

    def __init__(self, project_cfg: dict, socks_dir: pathlib.Path, project_dir: pathlib.Path):
        block_name = 'kernel'

        super().__init__(project_cfg=project_cfg,
                        socks_dir=socks_dir,
                        project_dir=project_dir,
                        block_name=block_name)


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

        self._run_menuconfig(menuconfig_commands=menuconfig_commands)


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

        self._prep_clean_srcs(prep_srcs_commands=prep_srcs_commands)


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
        if not ZynqMP_AMD_Kernel_Builder_Alma9._check_rebuilt_required(src_search_list=[self._patch_dir, self._source_repo_dir], src_ignore_list=[self._source_repo_dir / 'arch/arm64/boot'], out_search_list=[self._source_repo_dir / 'arch/arm64/boot']):
            pretty_print.print_build('No need to rebuild the Linux Kernel. No altered source files detected...')
            return

        pretty_print.print_build('Building Linux Kernel...')

        kernel_build_commands = f'\'cd {self._source_repo_dir} && ' \
                                'export CROSS_COMPILE=aarch64-linux-gnu- && ' \
                                'make ARCH=arm64 olddefconfig && ' \
                                f'make ARCH=arm64 -j{self._pc_make_threads}\''

        if self._pc_container_tool  in ('docker', 'podman'):
            try:
                # Run commands in container
                ZynqMP_AMD_Kernel_Builder_Alma9._run_sh_command([self._pc_container_tool , 'run', '--rm', '-it', '-v', f'{self._repo_dir}:{self._repo_dir}:Z', '-v', f'{self._output_dir}:{self._output_dir}:Z', self._container_image, 'sh', '-c', kernel_build_commands])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while building the Linux Kernel: {e}')
                sys.exit(1)
        elif self._pc_container_tool  == 'none':
            # Run commands without using a container
            ZynqMP_AMD_Kernel_Builder_Alma9._run_sh_command(['sh', '-c', kernel_build_commands])
        else:
            self._err_unsup_container_tool()

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
        if not ZynqMP_AMD_Kernel_Builder_Alma9._check_rebuilt_required(src_search_list=[self._patch_dir, self._source_repo_dir], src_ignore_list=[self._source_repo_dir / 'arch/arm64/boot'], out_search_list=[self._output_dir / 'kernel_modules.tar.gz']):
            pretty_print.print_build('No need to export Kernel modules. No altered source files detected...')
            return

        pretty_print.print_build('Exporting Kernel Modules...')

        export_modules_commands = f'\'cd {self._source_repo_dir} && ' \
                                'export CROSS_COMPILE=aarch64-linux-gnu- && ' \
                                f'make ARCH=arm64 modules_install INSTALL_MOD_PATH={self._output_dir} && ' \
                                f'find {self._output_dir}/lib -type l -delete && ' \
                                f'tar -P --xform=\'s:{self._output_dir}::\' --numeric-owner -p -czf {self._output_dir}/kernel_modules.tar.gz {self._output_dir}/lib && ' \
                                f'rm -rf {self._output_dir}/lib\''

        if self._pc_container_tool  in ('docker', 'podman'):
            try:
                # Run commands in container
                ZynqMP_AMD_Kernel_Builder_Alma9._run_sh_command([self._pc_container_tool , 'run', '--rm', '-it', '-v', f'{self._repo_dir}:{self._repo_dir}:Z', '-v', f'{self._output_dir}:{self._output_dir}:Z', self._container_image, 'sh', '-c', export_modules_commands])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while exporting Kernel modules: {e}')
                sys.exit(1)
        elif self._pc_container_tool  == 'none':
            # Run commands without using a container
            ZynqMP_AMD_Kernel_Builder_Alma9._run_sh_command(['sh', '-c', export_modules_commands])
        else:
            self._err_unsup_container_tool()