import sys
import pathlib
import shutil
import inspect
import hashlib

import socks.pretty_print as pretty_print
from socks.build_validator import Build_Validator
from socks.file_downloader import File_Downloader
from abstract_builders.builder import Builder
from raspberrypi_support.raspberrypi_image_model import RaspberryPi_Image_Model


class RaspberryPi_Image_Builder(Builder):
    """
    Raspberry Pi Image builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "image",
        block_description: str = "Build the boot image for ZynqMP devices",
        model_class: type[object] = RaspberryPi_Image_Model,
    ):

        super().__init__(
            project_cfg=project_cfg,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
            model_class=model_class,
        )

        self.pre_action_warnings.append("This block is experimental, it should not be used for production.")
        self.pre_action_warnings.append(
            "At the moment there is somthing wrong with the boot images created with "
            "'build-sd-card'. To fix it manually you have to do the following. After writing the SD card, copy all "
            "files from the bootfs partition to your PC, format the bootfs partition e.g. with grub to FAT16 or FAT32 "
            "And after that copy the files back to the boot partition. Now it should be possible to boot from the SD "
            "card. Additionally it must be noted that at the moment the boot process without U-Boot is more stable. "
            "Probably one has to tweak the settings a bit more."
        )

        self._sdc_image_name = f"{self.project_cfg.project.name}_sd_card.img"

    @property
    def _block_deps(self):
        # Products of other blocks on which this block depends
        # This dict is used to check whether the imported block packages contain
        # all the required files. Regex can be used to describe the expected files.
        # Optional dependencies can also be listed here. They will be ignored if
        # they are not listed in the project configuration.
        block_deps = {
            "kernel": ["Image.gz", ".*.dtb"],
            # "ramfs": [".*.cpio.gz"],
            "rootfs": [".*.tar.xz"],
            "ssbl": ["u-boot.bin"],
        }
        return block_deps

    @property
    def block_cmds(self):
        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        block_cmds = {"prepare": [], "build": [], "build-sd-card": [], "clean": [], "start-container": []}
        block_cmds["clean"].extend(
            [
                self.container_executor.build_container_image,
                self.clean_work,
                self.clean_dependencies,
                self.clean_output,
                self.clean_block_temp,
            ]
        )
        if self.block_cfg.source == "build":
            block_cmds["prepare"].extend(
                [
                    self._build_validator.del_project_cfg,
                    self.container_executor.build_container_image,
                    self.import_dependencies,
                    self.boot_cfg_files,
                    self.proprietary_files,
                    self._build_validator.save_project_cfg_prepare,
                ]
            )
            block_cmds["build"].extend(block_cmds["prepare"])
            block_cmds["build"].extend(
                [
                    self.bootscr_img,
                    self.export_block_package,
                    self._build_validator.save_project_cfg_build,
                ]
            )
            block_cmds["build-sd-card"].extend(
                [func for func in block_cmds["build"] if func != self._build_validator.save_project_cfg_build]
            )  # Append list without save_project_cfg_build
            block_cmds["build-sd-card"].extend([self.sd_card_img, self._build_validator.save_project_cfg_build])
            block_cmds["start-container"].extend([self.container_executor.build_container_image, self.start_container])
        elif self.block_cfg.source == "import":
            block_cmds["build"].extend([self.container_executor.build_container_image, self.import_prebuilt])
        return block_cmds

    def validate_srcs(self):
        """
        Check whether all sources required to build this block are present.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        super().validate_srcs()
        self.import_req_src_tpl()

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
            (self._resources_dir, "Z"),
            (self._dependencies_dir, "Z"),
            (self._work_dir, "Z"),
            (self._output_dir, "Z"),
        ]

        self.container_executor.start_container(potential_mounts=potential_mounts)

    def boot_cfg_files(self):
        """
        Provides the boot configuration files required by the Raspberry Pi bootloader.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        bl_config_src = self._resources_dir / "config.txt"
        bl_cmdline_src = self._resources_dir / "cmdline.txt"

        # Check whether the boot configuration files needs to be exported
        if not Build_Validator.check_rebuild_bc_timestamp(
            src_search_list=[
                bl_config_src,
                bl_cmdline_src,
            ],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ):
            pretty_print.print_build("No need to export boot configuration files. No altered source files detected...")
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            self._work_dir.mkdir(parents=True, exist_ok=True)
            self._output_dir.mkdir(parents=True, exist_ok=True)

            # Remove old build artifacts
            (self._output_dir / bl_config_src.name).unlink(missing_ok=True)
            (self._output_dir / bl_cmdline_src.name).unlink(missing_ok=True)

            pretty_print.print_build("Exporting boot configuration files...")

            # Create symlinks for files that do not need to be processed
            if bl_config_src.is_file():
                (self._output_dir / bl_config_src.name).symlink_to(bl_config_src)
            else:
                pretty_print.print_error(
                    f"The following source file is required but could not be found: {bl_config_src}"
                )
                sys.exit(1)
            if bl_cmdline_src.is_file():
                (self._output_dir / bl_cmdline_src.name).symlink_to(bl_cmdline_src)

    def proprietary_files(self):
        """
        Downloads proprietary files required by the Raspberry Pi for booting.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        if self.project_cfg.project.rpi_model == "RPi_5":
            return  # No need to download proprietary files for Raspberry Pi 5

        start4_url = "https://raw.githubusercontent.com/raspberrypi/firmware/master/boot/start4.elf"
        fixup4_url = "https://raw.githubusercontent.com/raspberrypi/firmware/master/boot/fixup4.dat"

        start4_out = self._output_dir / start4_url.split("/")[-1]
        fixup4_out = self._output_dir / fixup4_url.split("/")[-1]

        # Get checksum of the proprietary files online
        start4_online_md5 = File_Downloader.get_checksum(url=start4_url, hash_function="md5")
        fixup4_online_md5 = File_Downloader.get_checksum(url=fixup4_url, hash_function="md5")

        # Get checksum of the downloaded files, if any
        if start4_out.is_file():
            start4_local_md5 = hashlib.md5(start4_out.read_bytes()).hexdigest()
        else:
            start4_local_md5 = 0
        if fixup4_out.is_file():
            fixup4_local_md5 = hashlib.md5(fixup4_out.read_bytes()).hexdigest()
        else:
            fixup4_local_md5 = 0

        # Check whether the proprietary files need to be downloaded
        if start4_online_md5 == start4_local_md5 and fixup4_online_md5 == fixup4_local_md5:
            pretty_print.print_build("No need to download proprietary files. No altered files detected...")
            return

        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Remove old files
        start4_out.unlink(missing_ok=True)
        fixup4_out.unlink(missing_ok=True)

        pretty_print.print_build("Downloading proprietary files...")

        # Download the files
        File_Downloader.get_file(url=start4_url, output_dir=self._output_dir)
        File_Downloader.get_file(url=fixup4_url, output_dir=self._output_dir)

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

        # Check if boot.scr is required
        if self.block_cfg.project.dependencies.ssbl is None:
            pretty_print.print_build("No need to build boot.scr because there is no dependency on an ssbl...")
            return

        # Check whether the boot script image needs to be built
        if not Build_Validator.check_rebuild_bc_timestamp(
            src_search_list=[self._resources_dir / "boot.cmd"],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ):
            pretty_print.print_build("No need to rebuild boot.scr. No altered source files detected...")
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            self._output_dir.mkdir(parents=True, exist_ok=True)

            # Remove old build artifacts
            (self._output_dir / "boot.scr").unlink(missing_ok=True)

            pretty_print.print_build("Building boot.scr...")

            bootscr_img_build_commands = [
                f"mkimage -c none -A arm64 -O linux -T script -d {self._resources_dir}/boot.cmd {self._output_dir}/boot.scr"
            ]

            self.container_executor.exec_sh_commands(
                commands=bootscr_img_build_commands,
                dirs_to_mount=[(self._resources_dir, "Z"), (self._output_dir, "Z")],
                print_commands=True,
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
        if (
            not Build_Validator.check_rebuild_bc_timestamp(
                src_search_list=[
                    self._output_dir / "config.txt",
                    self._output_dir / "cmdline.txt",
                    self._output_dir / "start4.elf",
                    self._output_dir / "fixup4.dat",
                    self._output_dir / "uboot.bin",
                    self._output_dir / "boot.scr",
                    self._dependencies_dir / "kernel",
                    self._dependencies_dir / "rootfs",
                ],
                out_timestamp=self._build_log.get_logged_timestamp(
                    identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
                ),
            )
            and not self._build_validator.check_rebuild_bc_config(
                keys=[
                    ["blocks", self.block_id, "project", "size_boot_partition"],
                    ["blocks", self.block_id, "project", "size_rootfs_partition"],
                ]
            )
            and (self._output_dir / self._sdc_image_name).is_file()
        ):
            pretty_print.print_build("No need to rebuild the SD card image. No altered source files detected...")
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            pretty_print.print_build(f"Building SD card image {self._sdc_image_name} (This may take a few minutes)...")

            # Check if all required files are available
            if self.block_cfg.project.dependencies.ssbl is None:
                # The Raspberry Pi bootloader reads the kernel boot command from cmdline.txt
                if not (self._output_dir / "cmdline.txt").exists():
                    pretty_print.print_error(
                        f'If you do not use U-Boot, you need {self._resources_dir / "cmdline.txt"}.'
                    )
                    sys.exit(1)
                # The Raspberry Pi bootloader on models 4B and 5 searches for a kernel image named kernel8.img
                if not (self._output_dir / "kernel8.img").is_file():
                    (self._output_dir / "kernel8.img").symlink_to(self._dependencies_dir / "kernel" / "Image.gz")

            # Replace symlinks in the output directory with actual files
            for path in self._output_dir.iterdir():
                if path.is_symlink():
                    if path.name.endswith(".link"):
                        # Symlink was already replaced
                        continue
                    new_link_path = self._output_dir / f"{path.name}.link"
                    shutil.move(path, new_link_path)
                    shutil.copy(new_link_path, path)

            # Create a list with all devicetree files to be copied to the image
            dtb_files = list((self._dependencies_dir / "kernel").glob("*.dtb"))

            # Create a list of all possible boot files that can be copied
            possible_boot_files = dtb_files + [
                self._output_dir / "config.txt",
                self._output_dir / "cmdline.txt",
                self._output_dir / "start4.elf",
                self._output_dir / "fixup4.dat",
                self._output_dir / "boot.scr",
                self._output_dir / "kernel8.img",
                self._dependencies_dir / "ssbl" / "u-boot.bin",
                self._dependencies_dir / "kernel" / "Image.gz",
            ]

            # Remove all files that do not exist
            possible_boot_files = [path for path in possible_boot_files if path.exists()]

            # Remove unnecessary files from the list
            if self.block_cfg.project.dependencies.ssbl is None:
                possible_boot_files = [
                    path for path in possible_boot_files if path != (self._dependencies_dir / "kernel" / "Image.gz")
                ]
                possible_boot_files = [path for path in possible_boot_files if path != (self._output_dir / "boot.scr")]
            else:
                possible_boot_files = [
                    path for path in possible_boot_files if path != (self._output_dir / "cmdline.txt")
                ]

            # Convert list to Bash compatible string
            possible_boot_files_strs = [str(path) for path in possible_boot_files]
            possible_boot_files_str = " ".join(possible_boot_files_strs)

            boot_partition_size = self.block_cfg.project.size_boot_partition
            total_image_size = self.block_cfg.project.size_boot_partition + self.block_cfg.project.size_rootfs_partition

            sdc_img_build_commands = [
                f"rm -f {self._output_dir}/{self._sdc_image_name}",
                f"guestfish -N {self._output_dir}/{self._sdc_image_name}=bootroot:vfat:ext4:{total_image_size}M:{boot_partition_size}M -- "
                f"    set-label /dev/sda1 bootfs : "
                f"    set-label /dev/sda2 rootfs : "
                f"    mkmountpoint /p1 : "
                f"    mount /dev/sda1 /p1 : "
                f"    copy-in {possible_boot_files_str} /p1/ : ",
            ]
            if rootfs_archives:
                sdc_img_build_commands[-1] = (
                    sdc_img_build_commands[-1] + f"    mkmountpoint /p2 : "
                    f"    mount /dev/sda2 /p2 : "
                    f"    tar-in {rootfs_archives[0]} /p2/ compress:xz acls:true : "
                )
            sdc_img_build_commands[-1] = sdc_img_build_commands[-1] + f"    umount-all"

            self.container_executor.exec_sh_commands(
                commands=sdc_img_build_commands,
                dirs_to_mount=[(self._dependencies_dir, "Z"), (self._resources_dir, "Z"), (self._output_dir, "Z")],
                print_commands=True,
            )

            # Restore symlinks
            for path in self._output_dir.glob("*.link"):
                if path.is_symlink():
                    new_link_path = self._output_dir / path.name[:-5]
                    shutil.move(path, new_link_path)
