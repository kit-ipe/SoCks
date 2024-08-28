import sys
import pathlib

import pretty_print
import builder

class ZynqMP_AMD_ATF_Builder_Alma9(builder.Builder):
    """
    AMD ATF builder class
    """

    def __init__(self, project_cfg: dict, socks_dir: pathlib.Path, project_dir: pathlib.Path):
        block_name = 'atf'

        super().__init__(project_cfg=project_cfg,
                        socks_dir=socks_dir,
                        project_dir=project_dir,
                        block_name=block_name)


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

        atf_build_commands = f'\'cd {str(self._source_repo_dir)} && ' \
                                'make distclean && ' \
                                'make CROSS_COMPILE=aarch64-none-elf- PLAT=zynqmp RESET_TO_BL31=1 ZYNQMP_CONSOLE=cadence0\''

        if not ZynqMP_AMD_ATF_Builder_Alma9._check_rebuilt_required(src_search_list=[self._patch_dir, self._source_repo_dir], src_ignore_list=[self._source_repo_dir / 'build'], out_search_list=[self._source_repo_dir / 'build/zynqmp/release/bl31/bl31.elf', self._source_repo_dir / 'build/zynqmp/release/bl31.bin']):
            pretty_print.print_build('No need to rebuild the ATF. No altered source files detected...')
            return

        pretty_print.print_build('Building the ATF...')

        if self._pc_container_tool  in ('docker', 'podman'):
            try:
                # Run build commands in container
                ZynqMP_AMD_ATF_Builder_Alma9._run_sh_command([self._pc_container_tool , 'run', '--rm', '-it', '-v', f'{str(self._repo_dir)}:{str(self._repo_dir)}:Z', '-v', f'{str(self._output_dir)}:{str(self._output_dir)}:Z', self._container_image, 'sh', '-c', atf_build_commands])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while building the ATF: {str(e)}')
                sys.exit(1)
        elif self._pc_container_tool  == 'none':
            # Run build commands without using a container
            ZynqMP_AMD_ATF_Builder_Alma9._run_sh_command(['sh', '-c', atf_build_commands])
        else:
            Builder._err_unsup_container_tool()

        # Create symlinks to the output files
        (self._output_dir / 'bl31.elf').unlink(missing_ok=True)
        (self._output_dir / 'bl31.elf').symlink_to(self._source_repo_dir / 'build/zynqmp/release/bl31/bl31.elf')
        (self._output_dir / 'bl31.bin').unlink(missing_ok=True)
        (self._output_dir / 'bl31.bin').symlink_to(self._source_repo_dir / 'build/zynqmp/release/bl31.bin')     