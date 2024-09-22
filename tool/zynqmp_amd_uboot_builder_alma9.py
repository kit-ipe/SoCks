import sys
import pathlib
import shutil
import hashlib

import pretty_print
import builder

class ZynqMP_AMD_UBoot_Builder_Alma9(builder.Builder):
    """
    AMD U-Boot builder class
    """

    def __init__(self, project_cfg: dict, socks_dir: pathlib.Path, project_dir: pathlib.Path):
        block_name = 'u-boot'

        super().__init__(project_cfg=project_cfg,
                        socks_dir=socks_dir,
                        project_dir=project_dir,
                        block_name=block_name)

        # Products of other blocks on which this block depends
        # This dict is used to check whether the imported block packages contain
        # all the required files. Regex can be used to describe the expected files.
        self._block_deps = {
            'atf': ['bl31.bin']
        }

        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        self.block_cmds = {
            'prepare': [],
            'build': [],
            'clean': [],
            'create_patches': [],
            'start_container': [],
            'menucfg': [],
            'prep_clean_srcs': []
        }
        if self._pc_block_source == 'build':
            self.block_cmds['prepare'].extend([self.build_container_image, self.import_dependencies, self.init_repo, self.copy_atf, self.apply_patches])
            self.block_cmds['build'].extend(self.block_cmds['prepare'])
            self.block_cmds['build'].extend([self.build_uboot, self.export_block_package])
            self.block_cmds['create_patches'].extend([self.create_patches])
            self.block_cmds['start_container'].extend([self.start_container])
            self.block_cmds['menucfg'].extend([self.run_menuconfig])
            self.block_cmds['prep_clean_srcs'].extend([self.prep_clean_srcs])
        elif self._pc_block_source == 'import':
            self.block_cmds['build'].extend([self.import_prebuilt])
        self.block_cmds['clean'].extend([self.clean_download, self.clean_work, self.clean_repo, self.clean_dependencies, self.clean_output, self.rm_temp_block])


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
                                'export ARCH=aarch64 && ' \
                                'make menuconfig\''

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
                                'export ARCH=aarch64 && ' \
                                'make xilinx_zynqmp_virt_defconfig && ' \
                                'printf \"\n# Do not ignore the config file\n!.config\n\" >> .gitignore\''

        self._prep_clean_srcs(prep_srcs_commands=prep_srcs_commands)


    def copy_atf(self):
        """
        Copy a ATF bl31.bin file into the U-Boot project. U-Boot will be built to run in exception
        level EL2 if bl31.bin is present in the root directory of the U-Boot project. Otherwise it
        will be built to run in exception level EL3.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        bl31_bin_path = self._dependencies_dir / 'atf' / 'bl31.bin'

        # Check whether the specified file exists
        if not bl31_bin_path.is_file():
            pretty_print.print_error(f'The following file was not found: {bl31_bin_path}')
            sys.exit(1)

        # Calculate md5 of the provided file
        md5_new_file = hashlib.md5(bl31_bin_path.read_bytes()).hexdigest()
        # Calculate md5 of the existing file, if it exists
        md5_existsing_file = 0
        if (self._source_repo_dir / 'bl31.bin').is_file():
            md5_existsing_file = hashlib.md5((self._source_repo_dir / 'bl31.bin').read_bytes()).hexdigest()
        # Copy the specified file if it is not identical to the existing file
        if md5_existsing_file != md5_new_file:
            shutil.copy(bl31_bin_path, self._source_repo_dir / bl31_bin_path.name)
        else:
            pretty_print.print_warning('No new \'bl31.bin\' recognized. The file that already exists in the target directory will be used.')


    def build_uboot(self):
        """
        Builds das U-Boot.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check whether das U-Boot needs to be built
        if not ZynqMP_AMD_UBoot_Builder_Alma9._check_rebuilt_required(src_search_list=[self._patch_dir, self._source_repo_dir], src_ignore_list=[self._source_repo_dir / 'u-boot.elf', self._source_repo_dir / 'spl/.boot.bin.cmd'], out_search_list=[self._source_repo_dir / 'u-boot.elf', self._source_repo_dir / 'spl/.boot.bin.cmd']):
            pretty_print.print_build('No need to rebuild U-Boot. No altered source files detected...')
            return

        pretty_print.print_build('Building U-Boot...')

        uboot_build_commands = f'\'cd {self._source_repo_dir} && ' \
                                'export CROSS_COMPILE=aarch64-linux-gnu- && ' \
                                'export ARCH=aarch64 && ' \
                                'make olddefconfig && ' \
                                f'make -j{self._pc_make_threads}\''

        if self._pc_container_tool  in ('docker', 'podman'):
            try:
                # Run commands in container
                ZynqMP_AMD_UBoot_Builder_Alma9._run_sh_command([self._pc_container_tool , 'run', '--rm', '-it', '-v', f'{self._repo_dir}:{self._repo_dir}:Z', '-v', f'{self._output_dir}:{self._output_dir}:Z', self._container_image, 'sh', '-c', uboot_build_commands])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while building das U-Boot: {e}')
                sys.exit(1)
        elif self._pc_container_tool  == 'none':
            # Run commands without using a container
            ZynqMP_AMD_UBoot_Builder_Alma9._run_sh_command(['sh', '-c', uboot_build_commands])
        else:
            self._err_unsup_container_tool()

        # Create symlink to the output file
        (self._output_dir / 'u-boot.elf').unlink(missing_ok=True)
        (self._output_dir / 'u-boot.elf').symlink_to(self._source_repo_dir / 'u-boot.elf')