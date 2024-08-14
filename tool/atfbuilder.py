import sys

import pretty_print
import builder

class ATFBuilder(builder.Builder):
    """
    ATF builder class
    """

    def __init__(self, socks_dir, project_dir):
        block_name = 'atf'

        source_repo_name = 'arm-trusted-firmware'
        source_repo_url = 'https://github.com/Xilinx/arm-trusted-firmware.git' # Should be read from YAML
        source_repo_branch = 'xilinx-v2022.2' # Should be read from YAML. At least the 2022.2 part.

        container_tool = 'docker' # Should be read from YAML

        container_image_name = 'atf-builder-alma9'
        container_image_tag = source_repo_branch
        container_image = container_image_name+':'+container_image_tag

        vivado_dir = '/media/marvin/T9MF/Tools/Xilinx/Vivado/' # Should be read from YAML
        vitis_dir = '/media/marvin/T9MF/Tools/Xilinx/Vitis/' # Should be read from YAML

        super().__init__(socks_dir=socks_dir,
                        block_name=block_name,
                        project_dir=project_dir,
                        source_repo_name=source_repo_name,
                        source_repo_url=source_repo_url,
                        source_repo_branch=source_repo_branch,
                        container_tool=container_tool,
                        container_image=container_image,
                        vivado_dir=vivado_dir,
                        vitis_dir=vitis_dir)


    def build_atf(self):
        """
        Builds the ATF.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        atf_build_commands = '\'cd '+str(self._source_repo_dir)+' && ' \
                               'make distclean && ' \
                               'make CROSS_COMPILE=aarch64-none-elf- PLAT=zynqmp RESET_TO_BL31=1 ZYNQMP_CONSOLE=cadence0\''

        if ATFBuilder._check_rebuilt_required(src_search_list=[self._patch_dir, self._source_repo_dir], src_ignore_list=[self._source_repo_dir / 'build'], out_search_list=[self._source_repo_dir / 'build/zynqmp/release/bl31/bl31.elf', self._source_repo_dir / 'build/zynqmp/release/bl31.bin']):
            pretty_print.print_build('Building the ATF...')

            if self._container_tool in ('docker', 'podman'):
                try:
                    # Run build commands in container
                    ATFBuilder._run_sh_command([self._container_tool, 'run', '--rm', '-it', '-v', str(self._repo_dir)+':'+str(self._repo_dir)+':Z', '-v', str(self._output_dir)+':'+str(self._output_dir)+':Z', self._container_image, 'sh', '-c', atf_build_commands])
                except Exception as e:
                    pretty_print.print_error('An error occurred while building the ATF: '+str(e))
                    sys.exit(1)
            elif self._container_tool == 'none':
                # Run build commands without using a container
                ATFBuilder._run_sh_command(['sh', '-c', atf_build_commands])
            else:
                Builder._err_unsup_container_tool()

            # Create symlinks to the output files
            (self._output_dir / 'bl31.elf').unlink(missing_ok=True)
            (self._output_dir / 'bl31.elf').symlink_to(self._source_repo_dir / 'build/zynqmp/release/bl31/bl31.elf')
            (self._output_dir / 'bl31.bin').unlink(missing_ok=True)
            (self._output_dir / 'bl31.bin').symlink_to(self._source_repo_dir / 'build/zynqmp/release/bl31.bin')
        else:
            pretty_print.print_build('No need to rebuild the ATF. No altered source files detected...')