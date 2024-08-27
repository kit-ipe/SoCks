import sys
import pathlib
import shutil
import hashlib

import pretty_print
import builder

class ZynqMP_AMD_UBoot_Builder_Alma9(builder.Builder):
    """
    U-Boot builder class
    """

    def __init__(self, project_cfg: dict, socks_dir: pathlib.Path, project_dir: pathlib.Path):
        block_name = 'u-boot'

        super().__init__(project_cfg=project_cfg,
                        socks_dir=socks_dir,
                        project_dir=project_dir,
                        block_name=block_name)


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

        potential_mounts=[f'{str(self._repo_dir)}:Z', f'{str(self._output_dir)}:Z']

        ZynqMP_AMD_UBoot_Builder_Alma9._start_container(self, potential_mounts=potential_mounts)


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

        menuconfig_commands = f'\'cd {str(self._source_repo_dir)} && ' \
                                'export CROSS_COMPILE=aarch64-linux-gnu- && ' \
                                'export ARCH=aarch64 && ' \
                                'make menuconfig\''

        builder.Builder._run_menuconfig(self, menuconfig_commands=menuconfig_commands)


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

        prep_srcs_commands = f'\'cd {str(self._source_repo_dir)} && ' \
                                'export CROSS_COMPILE=aarch64-linux-gnu- && ' \
                                'export ARCH=aarch64 && ' \
                                'make xilinx_zynqmp_virt_defconfig && ' \
                                'printf \"\n# Do not ignore the config file\n!.config\n\" >> .gitignore\''

        builder.Builder._prep_clean_srcs(self, prep_srcs_commands=prep_srcs_commands)


    def copy_atf(self, bl31_bin_path: pathlib.Path = None):
        """
        Copy a ATF bl31.bin file into the U-Boot project. U-Boot will be built to run in exception
        level EL2 if bl31.bin is present in the root directory of the U-Boot project. Otherwise it
        will be built to run in exception level EL3.

        Args:
            bl31_bin_path:
                The ATF bl31.bin file to be copied into the U-Boot project.

        Returns:
            None

        Raises:
            None
        """

        # Check whether a path was specified
        if not bl31_bin_path:
            if (self._source_repo_dir / 'bl31.bin').is_file():
                pretty_print.print_warning('bl31.bin was not specified. The file that already exists in the target directory will be used.')
            else:
                pretty_print.print_warning('bl31.bin was not provided. U-Boot will run in EL3.')
            return

        # Check whether the specified file exists
        if not bl31_bin_path.is_file():
            pretty_print.print_error(f'The following file was not found: {str(bl31_bin_path)}')
            sys.exit(1)

        # Check whether the specified file has the correct name
        if bl31_bin_path.name != 'bl31.bin':
            pretty_print.print_error(f'The name of the provided file is not \'bl31.bin\'.')
            sys.exit(1)

        # Calculate md5 of the provided file
        md5_new_file = hashlib.md5(bl31_bin_path.read_bytes()).hexdigest()
        # Calculate md5 of the existing file, if it exists
        md5_existsing_file = 0
        if (self._source_repo_dir / 'bl31.bin').is_file():
            md5_existsing_file = hashlib.md5((self._source_repo_dir / 'bl31.bin').read_bytes()).hexdigest()
        # Copy the specified file if it is not identical to the existing file
        if md5_existsing_file != md5_new_file:
            shutil.copy(bl31_bin_path, self._source_repo_dir / 'bl31.bin')
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

        uboot_build_commands = f'\'cd {str(self._source_repo_dir)} && ' \
                                'export CROSS_COMPILE=aarch64-linux-gnu- && ' \
                                'export ARCH=aarch64 && ' \
                                'make olddefconfig && ' \
                                f'make -j{self._project_cfg["externalTools"]["make"]["maxBuildThreads"]}\''

        if not ZynqMP_AMD_UBoot_Builder_Alma9._check_rebuilt_required(src_search_list=[self._patch_dir, self._source_repo_dir], src_ignore_list=[self._source_repo_dir / 'u-boot.elf', self._source_repo_dir / 'spl/.boot.bin.cmd'], out_search_list=[self._source_repo_dir / 'u-boot.elf', self._source_repo_dir / 'spl/.boot.bin.cmd']):
            pretty_print.print_build('No need to rebuild U-Boot. No altered source files detected...')
            return

        pretty_print.print_build('Building U-Boot...')

        if self._container_tool in ('docker', 'podman'):
            try:
                # Run build commands in container
                ZynqMP_AMD_UBoot_Builder_Alma9._run_sh_command([self._container_tool, 'run', '--rm', '-it', '-v', f'{str(self._repo_dir)}:{str(self._repo_dir)}:Z', '-v', f'{str(self._output_dir)}:{str(self._output_dir)}:Z', self._container_image, 'sh', '-c', uboot_build_commands])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while building das U-Boot: {str(e)}')
                sys.exit(1)
        elif self._container_tool == 'none':
            # Run build commands without using a container
            ZynqMP_AMD_UBoot_Builder_Alma9._run_sh_command(['sh', '-c', uboot_build_commands])
        else:
            Builder._err_unsup_container_tool()

        # Create symlinks to the output files
        (self._output_dir / 'u-boot.elf').unlink(missing_ok=True)
        (self._output_dir / 'u-boot.elf').symlink_to(self._source_repo_dir / 'u-boot.elf')