import sys
import pathlib

import socks.pretty_print as pretty_print
from socks.builder import Builder

class ZynqMP_AMD_ATF_Builder_Alma9(Builder):
    """
    AMD ATF builder class
    """

    def __init__(self, project_cfg: dict, project_cfg_files: list, socks_dir: pathlib.Path, project_dir: pathlib.Path):
        block_id = 'atf'
        block_description = 'Build the ARM Trusted Firmware for ZynqMP devices'

        super().__init__(project_cfg=project_cfg,
                        project_cfg_files=project_cfg_files,
                        socks_dir=socks_dir,
                        project_dir=project_dir,
                        block_id=block_id,
                        block_description=block_description)

        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        self.block_cmds = {
            'prepare': [],
            'build': [],
            'clean': [],
            'create-patches': [],
            'start-container': []
        }
        self.block_cmds['clean'].extend([self.build_container_image, self.clean_download, self.clean_work, self.clean_repo, self.clean_output, self.clean_block_temp])
        if self._pc_block_source == 'build':
            self.block_cmds['prepare'].extend([self.build_container_image, self.init_repo, self.apply_patches])
            self.block_cmds['build'].extend(self.block_cmds['prepare'])
            self.block_cmds['build'].extend([self.build_atf, self.export_block_package])
            self.block_cmds['create-patches'].extend([self.create_patches])
            self.block_cmds['start-container'].extend([self.build_container_image, self.start_container])
        elif self._pc_block_source == 'import':
            self.block_cmds['build'].extend([self.import_prebuilt])


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

        # Check whether the ATF needs to be built
        if not ZynqMP_AMD_ATF_Builder_Alma9._check_rebuilt_required(src_search_list=[self._patch_dir, self._source_repo_dir], src_ignore_list=[self._source_repo_dir / 'build'], out_search_list=[self._source_repo_dir / 'build/zynqmp/release/bl31/bl31.elf', self._source_repo_dir / 'build/zynqmp/release/bl31.bin']):
            pretty_print.print_build('No need to rebuild the ATF. No altered source files detected...')
            return

        pretty_print.print_build('Building the ATF...')

        atf_build_commands = f'\'cd {self._source_repo_dir} && ' \
                                'make distclean && ' \
                                'make CROSS_COMPILE=aarch64-none-elf- PLAT=zynqmp RESET_TO_BL31=1 ZYNQMP_CONSOLE=cadence0\''

        if self._pc_container_tool  in ('docker', 'podman'):
            try:
                # Run commands in container
                ZynqMP_AMD_ATF_Builder_Alma9._run_sh_command([self._pc_container_tool , 'run', '--rm', '-it', '-v', f'{self._repo_dir}:{self._repo_dir}:Z', '-v', f'{self._output_dir}:{self._output_dir}:Z', self._container_image, 'sh', '-c', atf_build_commands])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while building the ATF: {e}')
                sys.exit(1)
        elif self._pc_container_tool  == 'none':
            # Run commands without using a container
            ZynqMP_AMD_ATF_Builder_Alma9._run_sh_command(['sh', '-c', atf_build_commands])
        else:
            self._err_unsup_container_tool()

        # Create symlinks to the output files
        (self._output_dir / 'bl31.elf').unlink(missing_ok=True)
        (self._output_dir / 'bl31.elf').symlink_to(self._source_repo_dir / 'build/zynqmp/release/bl31/bl31.elf')
        (self._output_dir / 'bl31.bin').unlink(missing_ok=True)
        (self._output_dir / 'bl31.bin').symlink_to(self._source_repo_dir / 'build/zynqmp/release/bl31.bin')