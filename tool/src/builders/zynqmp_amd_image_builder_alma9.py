import sys
import pathlib
import shutil
import zipfile

import socks.pretty_print as pretty_print
from socks.amd_builder import AMD_Builder
from socks.builder import Builder


class ZynqMP_AMD_Image_Builder_Alma9(AMD_Builder):
    """
    AMD Image builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        project_cfg_files: list,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "image",
        block_description: str = "Build the boot image for ZynqMP devices",
    ):

        super().__init__(
            project_cfg=project_cfg,
            project_cfg_files=project_cfg_files,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
        )

        # Source images to be used in this block
        self._atf_img_path = self._dependencies_dir / "atf/bl31.elf"
        self._dt_img_path = self._dependencies_dir / "devicetree/system.dtb"
        self._fsbl_img_path = self._dependencies_dir / "fsbl/fsbl.elf"
        self._kernel_img_path = self._dependencies_dir / "kernel/Image.gz"
        self._pmufw_img_path = self._dependencies_dir / "pmu-fw/pmufw.elf"
        self._uboot_img_path = self._dependencies_dir / "u-boot/u-boot.elf"
        self._vivado_xsa_path = None

        self._sdc_image_name = f"{self._pc_prj_name}_sd_card.img"

        # Project directories
        self._misc_dir = self._block_src_dir / "misc"

        # Products of other blocks on which this block depends
        # This dict is used to check whether the imported block packages contain
        # all the required files. Regex can be used to describe the expected files.
        # Optional dependencies can also be listed here. They will be ignored if
        # they are not listed in the project configuration.
        self._block_deps = {
            "atf": ["bl31.elf"],
            "devicetree": ["system.dtb"],
            "fsbl": ["fsbl.elf"],
            "kernel": ["Image.gz"],
            "pmu-fw": ["pmufw.elf"],
            "ramfs": [".*.cpio.gz"],
            "rootfs": [".*.tar.xz"],
            "u-boot": ["u-boot.elf"],
            "vivado": [".*.xsa"],
        }

        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        self.block_cmds = {"prepare": [], "build": [], "build-sd-card": [], "clean": [], "start-container": []}
        self.block_cmds["clean"].extend(
            [
                self.build_container_image,
                self.clean_download,
                self.clean_work,
                self.clean_dependencies,
                self.clean_output,
                self.clean_block_temp,
            ]
        )
        if self._pc_block_source == "build":
            self.block_cmds["prepare"].extend([self.build_container_image, self.import_dependencies])
            self.block_cmds["build"].extend(self.block_cmds["prepare"])
            self.block_cmds["build"].extend([self.linux_img, self.bootscr_img, self.boot_img])
            self.block_cmds["build-sd-card"].extend(self.block_cmds["build"])
            self.block_cmds["build-sd-card"].extend([self.sd_card_img])
            self.block_cmds["start-container"].extend([self.build_container_image, self.start_container])
        elif self._pc_block_source == "import":
            self.block_cmds["build"].extend([self.import_prebuilt])

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

        self.check_amd_tools(required_tools=["vitis"])

        potential_mounts = [
            (pathlib.Path(self._amd_tools_path), "ro"),
            (self._misc_dir, "Z"),
            (self._dependencies_dir, "Z"),
            (self._work_dir, "Z"),
            (self._output_dir, "Z"),
        ]

        super(Builder, self).start_container(potential_mounts=potential_mounts)

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

        # Get path of the RAM file system, if any
        ramfs_archives = []
        if (self._dependencies_dir / "ramfs").is_dir():
            ramfs_archives = list((self._dependencies_dir / "ramfs").glob("*.cpio.gz"))

        # Check if there is more than one archive in the dependencie directory
        if len(ramfs_archives) > 1:
            pretty_print.print_error(f'More than one .cpio.gz archive in {self._dependencies_dir / "ramfs"}.')
            sys.exit(1)
        elif not ramfs_archives:
            # Check if a ramfs archive is needed
            with open(self._misc_dir / "image.its.tpl", "r") as file:
                if "<RAMFS_IMG_PATH>" in file.read():
                    pretty_print.print_error(
                        f'Block \'{self.block_id}\' needs input from block \'ramfs\', but it was not found in {self._dependencies_dir / "ramfs"}.'
                    )
                    sys.exit(1)

        # Check whether the Linux image needs to be built
        if not ZynqMP_AMD_Image_Builder_Alma9._check_rebuild_required(
            src_search_list=[
                self._misc_dir / "image.its.tpl",
                self._dependencies_dir / "kernel",
                self._dependencies_dir / "devicetree",
                self._dependencies_dir / "ramfs",
            ],
            out_search_list=[self._output_dir / "image.ub"],
        ):
            pretty_print.print_build("No need to rebuild Linux Image. No altered source files detected...")
            return

        self._work_dir.mkdir(parents=True, exist_ok=True)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        pretty_print.print_build("Building Linux Image...")

        linux_img_build_commands = (
            f"'cp {self._misc_dir}/image.its.tpl {self._work_dir}/image.its && "
            f'sed -i "s:<KERNEL_IMG_PATH>:{self._kernel_img_path}:g;" {self._work_dir}/image.its && '
            f'sed -i "s:<DT_IMG_PATH>:{self._dt_img_path}:g;" {self._work_dir}/image.its && '
        )
        if ramfs_archives:
            linux_img_build_commands = (
                linux_img_build_commands
                + f'sed -i "s:<RAMFS_IMG_PATH>:{ramfs_archives[0]}:g;" {self._work_dir}/image.its && '
            )
        linux_img_build_commands = (
            linux_img_build_commands + f"mkimage -f {self._work_dir}/image.its {self._output_dir}/image.ub'"
        )

        self.run_containerizable_sh_command(
            command=linux_img_build_commands,
            dirs_to_mount=[
                (self._misc_dir, "Z"),
                (self._dependencies_dir, "Z"),
                (self._work_dir, "Z"),
                (self._output_dir, "Z"),
            ],
        )

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
        if not ZynqMP_AMD_Image_Builder_Alma9._check_rebuild_required(
            src_search_list=[self._misc_dir / "boot.cmd"], out_search_list=[self._output_dir / "boot.scr"]
        ):
            pretty_print.print_build("No need to rebuild boot.scr. No altered source files detected...")
            return

        self._output_dir.mkdir(parents=True, exist_ok=True)

        pretty_print.print_build("Building boot.scr...")

        bootscr_img_build_commands = (
            f"'mkimage -c none -A arm -T script -d {self._misc_dir}/boot.cmd {self._output_dir}/boot.scr'"
        )

        self.run_containerizable_sh_command(
            command=bootscr_img_build_commands, dirs_to_mount=[(self._misc_dir, "Z"), (self._output_dir, "Z")]
        )

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

        xsa_files = list((self._dependencies_dir / "vivado").glob("*.xsa"))

        if len(xsa_files) != 1:
            pretty_print.print_error(f'Not exactly one XSA archive in {self._dependencies_dir / "vivado"}.')
            sys.exit(1)

        self._vivado_xsa_path = xsa_files[0]

        # Check whether the boot script image needs to be built
        if not ZynqMP_AMD_Image_Builder_Alma9._check_rebuild_required(
            src_search_list=self._project_cfg_files
            + [
                self._misc_dir / "bootgen.bif.tpl",
                self._fsbl_img_path,
                self._pmufw_img_path,
                self._vivado_xsa_path,
                self._atf_img_path,
                self._dt_img_path,
                self._uboot_img_path,
                self._output_dir / "image.ub",
                self._output_dir / "boot.scr",
            ],
            out_search_list=[self._output_dir / "BOOT.BIN"],
        ):
            pretty_print.print_build("No need to rebuild BOOT.BIN. No altered source files detected...")
            return

        self.check_amd_tools(required_tools=["vitis"])

        self._work_dir.mkdir(parents=True, exist_ok=True)

        pretty_print.print_build("Building BOOT.BIN...")

        # Extract .bit file from XSA archive
        bit_file = None
        with zipfile.ZipFile(self._vivado_xsa_path, "r") as archive:
            # Find all .bit files in the archive
            bit_files = [file for file in archive.namelist() if file.endswith(".bit")]
            # Check if there is more than one bit file
            if len(bit_files) != 1:
                pretty_print.print_error(f"Not exactly one *.bit archive in {self._vivado_xsa_path}.")
                sys.exit(1)
            # Extract the single .bit file
            archive.extract(bit_files[0], path=str(self._work_dir))
            # Rename the extracted file
            temp_bit_file = self._work_dir / bit_files[0]
            bit_file = self._work_dir / "system.bit"
            temp_bit_file.rename(bit_file)

        boot_img_build_commands = (
            f"'export XILINXD_LICENSE_FILE={self._amd_license} && "
            f"source {self._amd_vitis_path}/settings64.sh && "
            f"cp {self._misc_dir}/bootgen.bif.tpl {self._work_dir}/bootgen.bif && "
            f'sed -i "s:<FSBL_PATH>:{self._fsbl_img_path}:g;" {self._work_dir}/bootgen.bif && '
            f'sed -i "s:<PMUFW_PATH>:{self._pmufw_img_path}:g;" {self._work_dir}/bootgen.bif && '
            f'sed -i "s:<PLBIT_PATH>:{bit_file}:g;" {self._work_dir}/bootgen.bif && '
            f'sed -i "s:<ATF_PATH>:{self._atf_img_path}:g;" {self._work_dir}/bootgen.bif && '
            f'sed -i "s:<DTB_PATH>:{self._dt_img_path}:g;" {self._work_dir}/bootgen.bif && '
            f'sed -i "s:<UBOOT_PATH>:{self._uboot_img_path}:g;" {self._work_dir}/bootgen.bif && '
            f'sed -i "s:<LINUX_PATH>:{self._output_dir / "image.ub"}:g;" {self._work_dir}/bootgen.bif && '
            f'sed -i "s:<BSCR_PATH>:{self._output_dir / "boot.scr"}:g;" {self._work_dir}/bootgen.bif && '
            f"bootgen -arch zynqmp -image {self._work_dir}/bootgen.bif -o {self._output_dir}/BOOT.BIN -w'"
        )

        self.run_containerizable_sh_command(
            command=boot_img_build_commands,
            dirs_to_mount=[
                (pathlib.Path(self._amd_tools_path), "ro"),
                (self._misc_dir, "Z"),
                (self._dependencies_dir, "Z"),
                (self._work_dir, "Z"),
                (self._output_dir, "Z"),
            ],
        )

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

        # Get path of the root file system, if any
        rootfs_archives = []
        if (self._dependencies_dir / "rootfs").is_dir():
            rootfs_archives = list((self._dependencies_dir / "rootfs").glob("*.tar.xz"))

        # Check if there is more than one archive in the dependencie directory
        if len(rootfs_archives) > 1:
            pretty_print.print_error(f'More than one .tar.xz archive in {self._dependencies_dir / "rootfs"}.')
            sys.exit(1)

        # Check whether the sd card image needs to be built
        if not ZynqMP_AMD_Image_Builder_Alma9._check_rebuild_required(
            src_search_list=[
                self._output_dir / "BOOT.BIN",
                self._output_dir / "boot.scr",
                self._output_dir / "image.ub",
                self._dependencies_dir / "rootfs",
            ],
            out_search_list=[self._output_dir / self._sdc_image_name],
        ):
            pretty_print.print_build("No need to rebuild the SD card image. No altered source files detected...")
            return

        pretty_print.print_build(f"Building SD card image {self._sdc_image_name} (This may take a few minutes)...")

        sdc_img_build_commands = (
            f"'rm -f {self._output_dir}/{self._sdc_image_name} && "
            f"guestfish -N {self._output_dir}/{self._sdc_image_name}=bootroot:vfat:ext4:6G:500M -- "
            f"    set-label /dev/sda1 BOOT : "
            f"    set-label /dev/sda2 ROOTFS : "
            f"    mkmountpoint /p1 : "
            f"    mount /dev/sda1 /p1 : "
            f"    copy-in {self._output_dir}/image.ub {self._output_dir}/boot.scr {self._output_dir}/BOOT.BIN /p1/ : "
        )
        if rootfs_archives:
            sdc_img_build_commands = (
                sdc_img_build_commands + f"    mkmountpoint /p2 : "
                f"    mount /dev/sda2 /p2 : "
                f"    tar-in {rootfs_archives[0]} /p2/ compress:xz acls:true : "
            )
        sdc_img_build_commands = sdc_img_build_commands + f"    umount-all'"

        self.run_containerizable_sh_command(
            command=sdc_img_build_commands, dirs_to_mount=[(self._dependencies_dir, "Z"), (self._output_dir, "Z")]
        )
