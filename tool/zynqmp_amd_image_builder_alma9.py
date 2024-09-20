import sys
import pathlib
import shutil
import zipfile

import pretty_print
import amd_builder

class ZynqMP_AMD_Image_Builder_Alma9(amd_builder.AMD_Builder):
    """
    AMD Image builder class
    """

    def __init__(self, project_cfg: dict, socks_dir: pathlib.Path, project_dir: pathlib.Path):
        block_name = 'image'

        super().__init__(project_cfg=project_cfg,
                        socks_dir=socks_dir,
                        project_dir=project_dir,
                        block_name=block_name)

        # Products of other blocks on which this block depends
        # This dict is used to check whether the imported block packages contain
        # all the required files. Regex can be used to describe the expected files.
        self._block_deps = {
            'atf': ['bl31.elf'],
            'devicetree': ['system.dtb'],
            'fsbl': ['fsbl.elf'],
            'kernel': ['Image.gz'],
            'pmu-fw': ['pmufw.elf'],
            'rootfs': ['.*.tar...'],
            'u-boot': ['u-boot.elf'],
            'vivado': ['.*.xsa']
        }

        # Source images to be used in this block
        self._atf_img_path = self._dependencies_dir / 'atf/bl31.elf'
        self._dt_img_path = self._dependencies_dir / 'devicetree/system.dtb'
        self._fsbl_img_path = self._dependencies_dir / 'fsbl/fsbl.elf'
        self._kernel_img_path = self._dependencies_dir / 'kernel/Image.gz'
        self._pmufw_img_path = self._dependencies_dir / 'pmu-fw/pmufw.elf'
        self._uboot_img_path = self._dependencies_dir / 'u-boot/u-boot.elf'
        self._vivado_xsa_path = None

        self._sdc_image_name = f'{self._pc_prj_name}_sd_card.img'

        # Project directories
        self._misc_dir = self._project_src_dir / self._block_name / 'misc'

        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        self.block_cmds = {
            'prepare': [],
            'build': [],
            'clean': [],
            'start_container': []
        }
        if self._pc_block_source == 'build':
            self.block_cmds['prepare'].extend([self.build_container_image, self.import_dependencies])
            self.block_cmds['build'].extend(self.block_cmds['prepare'])
            self.block_cmds['build'].extend([self.linux_img, self.bootscr_img, self.boot_img])
            self.block_cmds['build_sd_card'].extend(self.block_cmds['build'])
            self.block_cmds['build_sd_card'].extend([self.sd_card_img])
            self.block_cmds['start_container'].extend([self.start_container])
        elif self._pc_block_source == 'import':
            self.block_cmds['build'].extend([self.import_prebuilt])
        self.block_cmds['clean'].extend([self.clean_download, self.clean_work, self.clean_dependencies, self.clean_output])


    def start_container(self):
        """
        Starts an interactive container with which the block can be built.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        potential_mounts = [f'{self._pc_xilinx_path}:ro', f'{self._misc_dir}:Z', f'{self._dependencies_dir}:Z', f'{self._work_dir}:Z', f'{self._output_dir}:Z']

        ZynqMP_AMD_Image_Builder_Alma9._start_container(self, potential_mounts=potential_mounts)


    def linux_img(self):
        """
        Creates a Linux image that can be loaded from U-Boot.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check whether the Linux image needs to be built
        if not ZynqMP_AMD_Image_Builder_Alma9._check_rebuilt_required(src_search_list=[self._misc_dir / 'image.its.tpl', self._dependencies_dir / 'kernel', self._dependencies_dir / 'devicetree'], out_search_list=[self._output_dir / 'image.ub']):
            pretty_print.print_build('No need to rebuild Linux Image. No altered source files detected...')
            return

        pretty_print.print_build('Building Linux Image...')

        self._work_dir.mkdir(parents=True, exist_ok=True)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        linux_img_build_commands = f'\'cp {self._misc_dir}/image.its.tpl {self._work_dir}/image.its && ' \
                                    f'sed -i "s:<KERNEL_IMG_PATH>:{self._kernel_img_path}:g;" {self._work_dir}/image.its && ' \
                                    f'sed -i "s:<DT_IMG_PATH>:{self._dt_img_path}:g;" {self._work_dir}/image.its && ' \
                                    f'mkimage -f {self._work_dir}/image.its {self._output_dir}/image.ub\''

        if self._pc_container_tool  in ('docker', 'podman'):
            try:
                # Run commands in container
                ZynqMP_AMD_Image_Builder_Alma9._run_sh_command([self._pc_container_tool , 'run', '--rm', '-it', '-v', f'{self._misc_dir}:{self._misc_dir}:Z', '-v', f'{self._dependencies_dir}:{self._dependencies_dir}:Z', '-v', f'{self._work_dir}:{self._work_dir}:Z', '-v', f'{self._output_dir}:{self._output_dir}:Z', self._container_image, 'sh', '-c', linux_img_build_commands])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while building the Linux Image: {e}')
                sys.exit(1)
        elif self._pc_container_tool  == 'none':
            # Run commands without using a container
            ZynqMP_AMD_Image_Builder_Alma9._run_sh_command(['sh', '-c', linux_img_build_commands])
        else:
            self._err_unsup_container_tool()


    def bootscr_img(self):
        """
        Creates boot script image boot.scr for U-Boot

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check whether the boot script image needs to be built
        if not ZynqMP_AMD_Image_Builder_Alma9._check_rebuilt_required(src_search_list=[self._misc_dir / 'boot.cmd'], out_search_list=[self._output_dir / 'boot.scr']):
            pretty_print.print_build('No need to rebuild boot.scr. No altered source files detected...')
            return

        pretty_print.print_build('Building boot.scr...')

        self._output_dir.mkdir(parents=True, exist_ok=True)

        bootscr_img_build_commands = f'\'mkimage -c none -A arm -T script -d {self._misc_dir}/boot.cmd {self._output_dir}/boot.scr\''

        if self._pc_container_tool  in ('docker', 'podman'):
            try:
                # Run commands in container
                ZynqMP_AMD_Image_Builder_Alma9._run_sh_command([self._pc_container_tool , 'run', '--rm', '-it', '-v', f'{self._misc_dir}:{self._misc_dir}:Z', '-v', f'{self._output_dir}:{self._output_dir}:Z', self._container_image, 'sh', '-c', bootscr_img_build_commands])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while building boot.scr: {e}')
                sys.exit(1)
        elif self._pc_container_tool  == 'none':
            # Run commands without using a container
            ZynqMP_AMD_Image_Builder_Alma9._run_sh_command(['sh', '-c', bootscr_img_build_commands])
        else:
            self._err_unsup_container_tool()


    def boot_img(self):
        """
        Creates the primary boot image BOOT.BIN

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        xsa_files = list((self._dependencies_dir / 'vivado').glob('*.xsa'))

        if len(xsa_files) != 1:
            pretty_print.print_error(f'Not exactly one XSA archive in {self._dependencies_dir / "vivado"}.')
            sys.exit(1)

        self._vivado_xsa_path = xsa_files[0]

        # Check whether the boot script image needs to be built
        if not ZynqMP_AMD_Image_Builder_Alma9._check_rebuilt_required(src_search_list=[self._misc_dir / 'bootgen.bif.tpl', self._fsbl_img_path, self._pmufw_img_path, self._vivado_xsa_path, self._atf_img_path, self._dt_img_path, self._uboot_img_path, self._output_dir / 'image.ub', self._output_dir / 'boot.scr'], out_search_list=[self._output_dir / 'BOOT.BIN']):
            pretty_print.print_build('No need to rebuild BOOT.BIN. No altered source files detected...')
            return

        pretty_print.print_build('Building BOOT.BIN...')

        # Check if Xilinx tools are available
        if not pathlib.Path(self._pc_xilinx_path).is_dir():
            pretty_print.print_error(f'Directory {self._pc_xilinx_path} not found.')
            sys.exit(1)

        self._work_dir.mkdir(parents=True, exist_ok=True)

        # Extract .bit file from XSA archive
        bit_file = None
        with zipfile.ZipFile(self._vivado_xsa_path, 'r') as archive:
            # Find all .bit files in the archive
            bit_files = [file for file in archive.namelist() if file.endswith('.bit')]
            # Check if there is more than one bit file
            if len(bit_files) != 1:
                pretty_print.print_error(f'Not exactly one *.bit archive in {self._vivado_xsa_path}.')
                sys.exit(1)
            # Extract the single .bit file
            archive.extract(bit_files[0], path=str(self._work_dir))
            # Rename the extracted file
            temp_bit_file = self._work_dir / bit_files[0]
            bit_file = self._work_dir / 'system.bit'
            temp_bit_file.rename(bit_file)

        boot_img_build_commands = f'\'cp {self._misc_dir}/bootgen.bif.tpl {self._work_dir}/bootgen.bif && ' \
                                f'sed -i "s:<FSBL_PATH>:{self._fsbl_img_path}:g;" {self._work_dir}/bootgen.bif && ' \
                                f'sed -i "s:<PMUFW_PATH>:{self._pmufw_img_path}:g;" {self._work_dir}/bootgen.bif && ' \
                                f'sed -i "s:<PLBIT_PATH>:{bit_file}:g;" {self._work_dir}/bootgen.bif && ' \
                                f'sed -i "s:<ATF_PATH>:{self._atf_img_path}:g;" {self._work_dir}/bootgen.bif && ' \
                                f'sed -i "s:<DTB_PATH>:{self._dt_img_path}:g;" {self._work_dir}/bootgen.bif && ' \
                                f'sed -i "s:<UBOOT_PATH>:{self._uboot_img_path}:g;" {self._work_dir}/bootgen.bif && ' \
                                f'sed -i "s:<LINUX_PATH>:{self._output_dir / "image.ub"}:g;" {self._work_dir}/bootgen.bif && ' \
                                f'sed -i "s:<BSCR_PATH>:{self._output_dir / "boot.scr"}:g;" {self._work_dir}/bootgen.bif && ' \
                                f'{self._pc_xilinx_path}/Vitis/{self._pc_xilinx_version}/bin/bootgen -arch zynqmp -image {self._work_dir}/bootgen.bif -o {self._output_dir}/BOOT.BIN -w\''

        if self._pc_container_tool  in ('docker', 'podman'):
            try:
                # Run commands in container
                ZynqMP_AMD_Image_Builder_Alma9._run_sh_command([self._pc_container_tool , 'run', '--rm', '-it', '-v', f'{self._pc_xilinx_path}:{self._pc_xilinx_path}:ro', '-v', f'{self._misc_dir}:{self._misc_dir}:Z', '-v', f'{self._dependencies_dir}:{self._dependencies_dir}:Z', '-v', f'{self._work_dir}:{self._work_dir}:Z', '-v', f'{self._output_dir}:{self._output_dir}:Z', self._container_image, 'sh', '-c', boot_img_build_commands])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while building BOOT.BIN: {e}')
                sys.exit(1)
        elif self._pc_container_tool  == 'none':
            # Run commands without using a container
            ZynqMP_AMD_Image_Builder_Alma9._run_sh_command(['sh', '-c', boot_img_build_commands])
        else:
            self._err_unsup_container_tool()


    def sd_card_img(self):
        """
        Builds an image file that can be written to a SD card

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Get path of the root file system
        archives = list((self._dependencies_dir / 'rootfs').glob('*.tar.??'))

        # Check if there is more than one archive in the dependencie directory
        if len(archives) != 1:
            pretty_print.print_error(f'Not exactly one archive in {self._dependencies_dir / "rootfs"}.')
            sys.exit(1)

        rootfs_archive = archives[0]

        # Check whether the sd card image needs to be built
        if not ZynqMP_AMD_Image_Builder_Alma9._check_rebuilt_required(src_search_list=[self._output_dir / 'BOOT.BIN', self._output_dir / 'boot.scr', self._output_dir / 'image.ub', rootfs_archive], out_search_list=[self._output_dir / self._sdc_image_name]):
            pretty_print.print_build('No need to rebuild the SD card image. No altered source files detected...')
            return

        pretty_print.print_build(f'Building SD card image {self._sdc_image_name} (This may take a few minutes)...')

        sdc_img_build_commands = f'\'rm -f {self._output_dir}/{self._sdc_image_name} && ' \
                                    f'guestfish -N {self._output_dir}/{self._sdc_image_name}=bootroot:vfat:ext4:6G:500M -- ' \
                                    f'    set-label /dev/sda1 BOOT : ' \
                                    f'    set-label /dev/sda2 ROOTFS : ' \
                                    f'    mkmountpoint /p1 : ' \
                                    f'    mount /dev/sda1 /p1 : ' \
                                    f'    copy-in {self._output_dir}/image.ub {self._output_dir}/boot.scr {self._output_dir}/BOOT.BIN /p1/ : ' \
                                    f'    mkmountpoint /p2 : ' \
                                    f'    mount /dev/sda2 /p2 : ' \
                                    f'    tar-in {rootfs_archive} /p2/ compress:xz acls:true : ' \
                                    f'    umount-all\''

        if self._pc_container_tool  in ('docker', 'podman'):
            try:
                # Run commands in container
                ZynqMP_AMD_Image_Builder_Alma9._run_sh_command([self._pc_container_tool , 'run', '--rm', '-it', '-v', f'{self._dependencies_dir}:{self._dependencies_dir}:Z', '-v', f'{self._output_dir}:{self._output_dir}:Z', self._container_image, 'sh', '-c', sdc_img_build_commands])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while building BOOT.BIN: {e}')
                sys.exit(1)
        elif self._pc_container_tool  == 'none':
            # Run commands without using a container
            ZynqMP_AMD_Image_Builder_Alma9._run_sh_command(['sh', '-c', sdc_img_build_commands])
        else:
            self._err_unsup_container_tool()