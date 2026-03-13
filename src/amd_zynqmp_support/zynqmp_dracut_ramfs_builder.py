import sys
import pathlib
import shutil
import urllib
import hashlib
import inspect

import socks.pretty_print as pretty_print
from socks.container_executor import Container_Executor
from socks.build_validator import Build_Validator
from abstract_builders.file_system_builder import File_System_Builder
from amd_zynqmp_support.zynqmp_dracut_ramfs_model import ZynqMP_Dracut_RAMFS_Model


class ZynqMP_Dracut_RAMFS_Builder(File_System_Builder):
    """
    Dracut RAM file system builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "ramfs",
        block_description: str = "Build a Dracut RAM file system (initramfs)",
        model_class: type[object] = ZynqMP_Dracut_RAMFS_Model,
    ):

        super().__init__(
            project_cfg=project_cfg,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
            model_class=model_class,
        )

        # Project directories
        self._rootfs_dir = self._work_dir / "rootfs"
        self._kmodules_dir = self._work_dir / "kernel_modules"

        # Project files
        # Dracut configuration file
        self._dracut_conf_file = self._resources_dir / "dracut.conf"
        # File for saving the checksum of the Kernel module archive used
        self._source_kmods_md5_file = self._work_dir / "source_kmodules.md5"
        # File for saving the checksum of the RootFS archive used
        self._source_rootfs_md5_file = self._work_dir / "source_rootfs.md5"

        # Helpers
        self.container_executor = Container_Executor(
            container_tool=self.project_cfg.external_tools.container_tool,
            container_image=self.block_cfg.container.image,
            container_image_tag=self.block_cfg.container.tag,
            container_platform="linux/arm64/v8", # Use an emulated aarch64 container for this block
            container_file=self._container_dir / f"{self.block_cfg.container.image}.containerfile",
            container_log_file=self._project_temp_dir / ".container_log.csv",
        )

    @property
    def _block_deps(self):
        # Products of other blocks on which this block depends
        # This dict is used to check whether the imported block packages contain
        # all the required files. Regex can be used to describe the expected files.
        # Optional dependencies can also be listed here. They will be ignored if
        # they are not listed in the project configuration.
        block_deps = {
            "kernel": [".*"],
            "rootfs": [".*.tar.xz"]
        }
        return block_deps

    @property
    def block_cmds(self):
        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        block_cmds = {
            "prepare": [],
            "build": [],
            "clean": [],
            "start-container": [],
        }
        block_cmds["prepare"].extend(
            [
                self._build_validator.del_project_cfg,
                self.container_executor.enable_multiarch,
                self.container_executor.build_container_image,
                self.import_dependencies,
                self.import_root_file_system,
                self.import_kernel_modules,
                self._build_validator.save_project_cfg_prepare,
            ]
        )
        block_cmds["clean"].extend(
            [
                self.container_executor.enable_multiarch,
                self.container_executor.build_container_image,
                self.clean_work,
                self.clean_dependencies,
                self.clean_output,
                self.clean_block_temp,
            ]
        )
        if self.block_cfg.source == "build":
            block_cmds["build"].extend(block_cmds["prepare"])
            block_cmds["build"].extend(
                [
                    self.build_base_file_system,
                    self.export_block_package,
                    self._build_validator.save_project_cfg_build,
                ]
            )
            block_cmds["start-container"].extend([self.container_executor.build_container_image, self.start_container])
        elif self.block_cfg.source == "import":
            block_cmds["build"].extend(
                [
                    self.container_executor.enable_multiarch,
                    self.container_executor.build_container_image,
                    self.import_prebuilt
                ]
            )
        return block_cmds

    @property
    def _file_system_name(self):
        return f"dracut_fs_zynqmp_{self.project_cfg.project.name}"

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

    def import_root_file_system(self):
        """
        Unpacks the root file system.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        rootfs_archives = list((self._dependencies_dir / "rootfs").glob("*.tar.xz"))
        # Check if there is more than one *.tar.xz archive in the RootFS block package
        if len(rootfs_archives) != 1:
            pretty_print.print_error(f'Not exactly one *.tar.xz archive in {self._dependencies_dir / "rootfs"}/')
            sys.exit(1)
        # Calculate md5 of the file to be imported
        md5_new_file = hashlib.md5(rootfs_archives[0].read_bytes()).hexdigest()
        # Read md5 of previously used RootFS archive, if any
        md5_existsing_file = 0
        if self._source_rootfs_md5_file.is_file():
            with self._source_rootfs_md5_file.open("r") as f:
                md5_existsing_file = f.read()

        # Check whether the Kernel modules need to be added
        if md5_existsing_file == md5_new_file:
            pretty_print.print_build("No need to import the root file system. No altered source files detected...")
            return

        self._work_dir.mkdir(parents=True, exist_ok=True)

        pretty_print.print_build("Importing the root file system...")

        unpack_rootfs_commands = [
            f"rm -rf {self._rootfs_dir}",
            f"mkdir {self._rootfs_dir}",
            f"tar --numeric-owner -p -xf {rootfs_archives[0]} -C {self._rootfs_dir}",
        ]

        # The root user is used in this container. This is necessary in order to build a RAMFS image.
        self.container_executor.exec_sh_commands(
            commands=unpack_rootfs_commands,
            dirs_to_mount=[(self._dependencies_dir, "Z"), (self._work_dir, "Z")],
            print_commands=True,
            run_as_root=True,
        )

        # Save checksum in file
        with self._source_rootfs_md5_file.open("w") as f:
            print(md5_new_file, file=f, end="")

    def import_kernel_modules(self):
        """
        Unpacks the kernel modules.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        kmods_archive = self._dependencies_dir / "kernel" / "kernel_modules.tar.gz"

        # Skip this function if no kernel modules are available
        if not kmods_archive.is_file():
            pretty_print.print_info(f"File {kmods_archive} not found. No kernel modules are imported.")
            return

        # Calculate md5 of the provided file
        md5_new_file = hashlib.md5(kmods_archive.read_bytes()).hexdigest()
        # Read md5 of previously used Kernel module archive, if any
        md5_existsing_file = 0
        if self._source_kmods_md5_file.is_file():
            with self._source_kmods_md5_file.open("r") as f:
                md5_existsing_file = f.read()

        # Check whether the Kernel modules need to be added
        if md5_existsing_file == md5_new_file:
            pretty_print.print_build("No need to import Kernel modules. No altered source files detected...")
            return

        self._work_dir.mkdir(parents=True, exist_ok=True)

        pretty_print.print_build("Importing Kernel Modules...")

        unpack_kmodules_commands = [
            f"rm -rf {self._kmodules_dir}",
            f"mkdir {self._kmodules_dir}",
            f"tar -xf {kmods_archive} -C {self._kmodules_dir}",
            f"chown -R root:root {self._kmodules_dir}/lib",
            f"chmod -R 000 {self._kmodules_dir}/lib",
            f"chmod -R u=rwX,go=rX {self._kmodules_dir}/lib",
        ]

        # The root user is used in this container. This is necessary in order to build a file system image.
        self.container_executor.exec_sh_commands(
            commands=unpack_kmodules_commands,
            dirs_to_mount=[(self._dependencies_dir, "Z"), (self._work_dir, "Z")],
            print_commands=True,
            run_as_root=True,
        )

        # Save checksum in file
        with self._source_kmods_md5_file.open("w") as f:
            print(md5_new_file, file=f, end="")


    def build_base_file_system(self):
        """
        Builds the RAM file system.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check whether the RAM file system needs to be built
        if not Build_Validator.check_rebuild_bc_timestamp(
            src_search_list=[
                self._dracut_conf_file,
                self._rootfs_dir,
                self._kmodules_dir
            ],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ):
            pretty_print.print_build("No need to rebuild the RAM file system. No altered source files detected...")
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            self.clean_output()
            self._output_dir.mkdir(parents=True)

            pretty_print.print_build("Building the RAM file system...")

            kmodules_dir_param = ""
            kversion_param = ""
            if self._kmodules_dir.is_dir():
                kernel_module_dirs = list((self._kmodules_dir / "lib" / "modules").glob("*"))
                if len(kernel_module_dirs) != 1:
                    pretty_print.print_error(f'Kernel modules for more than one kernel version in {self._kmodules_dir / "lib" / "modules"}/')
                    sys.exit(1)
                kmodules_dir_param = f"--kmoddir {kernel_module_dirs[0]}"
                kversion_param = kernel_module_dirs[0].name

            ramfs_build_commands = [
                f"dracut --sysroot {self._rootfs_dir} {kmodules_dir_param} --conf {self._dracut_conf_file} --gzip --force {self._output_dir / self._file_system_name}.cpio.gz {kversion_param}",
                f"chmod 644 {self._output_dir / self._file_system_name}.cpio.gz",
            ]

            # The root user is used in this container. This is necessary in order to build a RAMFS image.
            self.container_executor.exec_sh_commands(
                commands=ramfs_build_commands,
                dirs_to_mount=[(self._resources_dir, "Z"), (self._work_dir, "Z"), (self._output_dir, "Z")],
                print_commands=True,
                run_as_root=True,
                logfile=self._block_temp_dir / "build.log",
                output_scrolling=True,
            )

    def build_archive(self):
        """
        Packs the entire ram file system in an archive.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # This method is required by the abstract parent class, but its functionality is not necessary because
        # the file system built with dracut is already archived.
        raise NotImplementedError("This method is not implemented.")