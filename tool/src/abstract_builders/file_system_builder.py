import sys
import pathlib
import hashlib
import tarfile
import zipfile
import urllib
import validators
import inspect
from abc import abstractmethod

import socks.pretty_print as pretty_print
from socks.build_validator import Build_Validator
from abstract_builders.builder import Builder


class File_System_Builder(Builder):
    """
    Abstract file system builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_description: str,
        model_class: type[object],
        block_id: str,
    ):

        super().__init__(
            project_cfg=project_cfg,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_description=block_description,
            model_class=model_class,
            block_id=block_id,
        )

        # Project directories
        self._build_dir = self._work_dir / self._file_system_name

        # Project files
        # File for version & build info tracking
        self._build_info_file = self._work_dir / "fs_build_info"
        # File for saving the checksum of the Kernel module archive used
        self._source_kmods_md5_file = self._work_dir / "source_kmodules.md5"

    @property
    @abstractmethod
    def _file_system_name(self):
        pass

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

    def import_dependencies(self):
        super().import_dependencies()

        # Stop if this block does not depend on the Vivado block
        if (
            not hasattr(self.block_cfg.project.dependencies, "vivado")
            or self.block_cfg.project.dependencies.vivado is None
        ):
            return

        xsafiles = list((self._dependencies_dir / "vivado").glob("*.xsa"))
        if len(xsafiles) != 1:
            pretty_print.print_error(f'Not exactly one *.xsa file in {self._dependencies_dir / "vivado"}.')
            sys.exit(1)

        # Extract the *.bit file only if it was not already extracted. This folder is deleted by the implementation
        # of this function in the parent class if the respective block package is reimported.
        xsa_extract_dir = self._dependencies_dir / "vivado" / "xsa_extracted"
        if xsa_extract_dir.is_dir():
            return

        # Extract *.bit file from the XSA if it contains one
        with zipfile.ZipFile(xsafiles[0], "r") as archive:
            # Find all .bit files in the archive
            bitfiles = [file for file in archive.namelist() if file.endswith(".bit")]
            # Stop if there is more than one bit file
            if len(bitfiles) > 1:
                pretty_print.print_error(f"More than one *.bit file in {xsafiles[0]}.")
                sys.exit(1)
            elif len(bitfiles) == 1:
                # Create a folder with the name of the XSA
                xsa_extract_dir.mkdir()
                # Extract the single .bit file
                archive.extract(bitfiles[0], path=str(xsa_extract_dir))

    @abstractmethod
    def build_base_file_system(self):
        """
        Builds the base file system.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        pass

    def add_pd_layers(self):
        """
        Adds predefined file system layers to the file system.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check whether a file system is present
        if not self._build_dir.is_dir():
            pretty_print.print_error(f"File system at {self._build_dir} not found.")
            sys.exit(1)

        # Check whether predefined file system layers are available
        pd_layers_dir = self._resources_dir / "predefined_fs_layers"
        if not pd_layers_dir.is_dir():
            pretty_print.print_info(
                f"Directory '{pd_layers_dir}' does not exist. No predefined file system layers will be added."
            )
            return

        # Check whether the layers need to be added
        layers_already_added = (
            self._build_log.get_logged_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")
            != 0.0
        )
        if layers_already_added and not Build_Validator.check_rebuild_bc_timestamp(
            src_search_list=[pd_layers_dir],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ):
            pretty_print.print_build(
                "No need to add predefined file system layers. No altered source files detected..."
            )
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            pretty_print.print_build("Adding predefined file system layers...")

            add_pd_layers_commands = [
                f"cd {self._resources_dir / 'predefined_fs_layers'}",
                f'for dir in ./*; do "$dir"/install_layer.sh {self._build_dir}/; done',
            ]

            # The root user is used in this container. This is necessary in order to build a file system image.
            self.container_executor.exec_sh_commands(
                commands=add_pd_layers_commands,
                dirs_to_mount=[(self._resources_dir, "Z"), (self._work_dir, "Z")],
                print_commands=True,
                run_as_root=True,
            )

    def add_bt_layer(self):
        """
        Adds external files and directories created by other blocks at
        build time.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check whether a file system is present
        if not self._build_dir.is_dir():
            pretty_print.print_error(f"File system at {self._build_dir} not found.")
            sys.exit(1)

        # Check whether the build time file system layer is specified
        if not self.block_cfg.project.build_time_fs_layer:
            pretty_print.print_info(
                f"'{self.block_id} -> project -> build_time_fs_layer' not specified. "
                "No files and directories created by other blocks at build time will be added."
            )
            return

        # Check whether the layer needs to be added
        layer_already_added = (
            self._build_log.get_logged_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")
            != 0.0
        )
        if (
            layer_already_added
            and not Build_Validator.check_rebuild_bc_timestamp(
                src_search_list=[self._dependencies_dir],
                out_timestamp=self._build_log.get_logged_timestamp(
                    identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
                ),
            )
            and not self._build_validator.check_rebuild_bc_config(
                keys=[["blocks", self.block_id, "project", "build_time_fs_layer"]]
            )
        ):
            pretty_print.print_build(
                "No need to add external files and directories created at build time. "
                "No altered source files detected..."
            )
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            pretty_print.print_build("Adding external files and directories created at build time...")

            add_bt_layer_commands = []
            for item in self.block_cfg.project.build_time_fs_layer:
                if item.src_block not in self._block_deps.keys():
                    pretty_print.print_error(
                        f"Source block '{item.src_block}' specified in '{self.block_id} -> project -> build_time_fs_layer' is invalid."
                    )
                    sys.exit(1)
                srcs = (self._dependencies_dir / item.src_block).glob(item.src_name)
                if not srcs:
                    pretty_print.print_error(
                        f"Source item '{item.src_name}' specified in '{self.block_id} -> project -> build_time_fs_layer' "
                        f"could not be found in the block package of source block '{item.src_block}'."
                    )
                    sys.exit(1)
                add_bt_layer_commands.append(f"mkdir -p {self._build_dir}/{item.dest_path}")
                for src in srcs:
                    add_bt_layer_commands.append(f"cp -r {src} {self._build_dir}/{item.dest_path}/{item.dest_name}")
                    if item.dest_owner_group:
                        add_bt_layer_commands.append(
                            f"chown -R {item.dest_owner_group} {self._build_dir}/{item.dest_path}/{item.dest_name}"
                        )
                    if item.dest_permissions:
                        add_bt_layer_commands.append(
                            f"chmod -R {item.dest_permissions} {self._build_dir}/{item.dest_path}/{item.dest_name}"
                        )

            # The root user is used in this container. This is necessary in order to build a file system image.
            self.container_executor.exec_sh_commands(
                commands=add_bt_layer_commands,
                dirs_to_mount=[(self._dependencies_dir, "Z"), (self._work_dir, "Z")],
                print_commands=True,
                run_as_root=True,
            )

    def add_kmodules(self):
        """
        Adds kernel modules to the file system.

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
            pretty_print.print_info(f"File {kmods_archive} not found. No kernel modules are added.")
            if any((self._build_dir / "lib" / "modules").iterdir()):
                delete_old_kmodules_commands = [f"rm -rf {self._build_dir}/lib/modules/*"]
                # The root user is used in this container. This is necessary in order to build a file system image.
                self.container_executor.exec_sh_commands(
                    commands=delete_old_kmodules_commands,
                    dirs_to_mount=[(self._work_dir, "Z")],
                    run_as_root=True,
                )
            return

        # Check whether a file system is present
        if not self._build_dir.is_dir():
            pretty_print.print_error(f"File system at {self._build_dir} not found.")
            sys.exit(1)

        # Calculate md5 of the provided file
        md5_new_file = hashlib.md5(kmods_archive.read_bytes()).hexdigest()
        # Read md5 of previously used Kernel module archive, if any
        md5_existsing_file = 0
        if self._source_kmods_md5_file.is_file():
            with self._source_kmods_md5_file.open("r") as f:
                md5_existsing_file = f.read()

        # Check whether the Kernel modules need to be added
        if md5_existsing_file == md5_new_file:
            pretty_print.print_build("No need to add Kernel Modules. No altered source files detected...")
            return

        pretty_print.print_build("Adding Kernel Modules...")

        add_kmodules_commands = [
            f"cd {self._work_dir}",
            f"tar -xzf {kmods_archive}",
            "chown -R root:root lib",
            "chmod -R 000 lib",
            "chmod -R u=rwX,go=rX lib",
            f"rm -rf {self._build_dir}/lib/modules",
            f"mkdir -p {self._build_dir}/lib/modules",
            f"mv lib/modules/* {self._build_dir}/lib/modules/",
            "rm -rf lib",
        ]

        # The root user is used in this container. This is necessary in order to build a file system image.
        self.container_executor.exec_sh_commands(
            commands=add_kmodules_commands,
            dirs_to_mount=[(self._dependencies_dir, "Z"), (self._work_dir, "Z")],
            print_commands=True,
            run_as_root=True,
        )

        # Save checksum in file
        with self._source_kmods_md5_file.open("w") as f:
            print(md5_new_file, file=f, end="")

    def _build_archive(self, archive_name: str, file_extension: str, tar_compress_param: str = ""):
        """
        Packs the entire file system in an archive.

        Args:
            archive_name:
                Name of the archive.
            file_extension:
                The extension to be added to the archive name.
                For rootfs: "tar.gz", "tar.xz"
                For ramfs: "cpio.gz"
            tar_compress_param:
                The compression option to be used by tar. Only relevant
                for root file systems, as ram file systems are not
                archived with tar.
                Tar was tested with three compression options:
                    Option      Size    Duration
                    "--xz"      872M    real	17m59.080s
                    "-I pxz"    887M    real	3m43.987s
                    "-I pigz"   1.3G    real	0m20.747s

        Returns:
            None

        Raises:
            ValueError:
                If block_id has an unexpected value
        """

        # Check if the archive needs to be built
        if not Build_Validator.check_rebuild_bc_timestamp(
            src_search_list=[self._work_dir],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ) and not self._build_validator.check_rebuild_bc_config(
            keys=[["blocks", self.block_id, "project", "add_build_info"], ["project", "name"]]
        ):
            pretty_print.print_build("No need to rebuild archive. No altered source files detected...")
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            self.clean_output()
            self._output_dir.mkdir(parents=True)

            pretty_print.print_build("Building archive...")

            if self.block_cfg.project.add_build_info == True:
                # Add build information file
                with self._build_info_file.open("w") as f:
                    print("# Filesystem build info (autogenerated)\n\n", file=f, end="")
                    print(self._compose_build_info(), file=f, end="")

                add_build_info_commands = [
                    f"mv {self._build_info_file} {self._build_dir}/etc/fs_build_info",
                    f"chmod 0444 {self._build_dir}/etc/fs_build_info",
                ]

                # The root user is used in this container. This is necessary in order to build a file system image.
                self.container_executor.exec_sh_commands(
                    commands=add_build_info_commands,
                    dirs_to_mount=[(self._work_dir, "Z")],
                    run_as_root=True,
                )
            else:
                # Remove existing build information file
                clean_build_info_commands = [f"rm -f {self._build_dir}/etc/fs_build_info"]

                # The root user is used in this container. This is necessary in order to build a file system image.
                self.container_executor.exec_sh_commands(
                    commands=clean_build_info_commands,
                    dirs_to_mount=[(self._work_dir, "Z")],
                    run_as_root=True,
                )

            if self.block_id == "rootfs":
                archive_build_commands = [
                    f"cd {self._build_dir}",
                    f"tar {tar_compress_param} --numeric-owner -p -cf  {self._output_dir / f'{archive_name}.{file_extension}'} ./",
                    f"if id {self._host_user} >/dev/null 2>&1; then "
                    f"    chown -R {self._host_user}:{self._host_user} {self._output_dir / f'{archive_name}.{file_extension}'}; "
                    f"fi",
                ]
            elif self.block_id == "ramfs":
                archive_build_commands = [
                    f"cd {self._build_dir}",
                    f"find . | cpio -H newc -o | gzip -9 > {self._output_dir / f'{archive_name}.{file_extension}'}",
                    f"if id {self._host_user} >/dev/null 2>&1; then "
                    f"    chown -R {self._host_user}:{self._host_user} {self._output_dir / f'{archive_name}.{file_extension}'}; "
                    f"fi",
                ]
            else:
                raise ValueError(f"Value of 'block_id' must be 'rootfs' or 'ramfs'")

            # The root user is used in this container. This is necessary in order to build a file system image.
            self.container_executor.exec_sh_commands(
                commands=archive_build_commands,
                dirs_to_mount=[(self._work_dir, "Z"), (self._output_dir, "Z")],
                print_commands=True,
                run_as_root=True,
            )

    @abstractmethod
    def build_archive(self, prebuilt: bool):
        """
        Packs the entire file system in an archive.

        Args:
            prebuilt:
                Set to True if the archive will contain pre-built files
                instead of a complete project file system.

        Returns:
            None

        Raises:
            None
        """

        pass

    def build_archive_prebuilt(self):
        """
        Packs the entire pre-built file system in an archive.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        self.build_archive(prebuilt=True)

    def import_prebuilt(self):
        """
        Imports a pre-built file system and overwrites the existing one.

        Args:
            None

        Returns:
            None

        Raises:
            ValueError:
                If block_id has an unexpected value
        """

        # Get path of the pre-built file system
        if self.block_cfg.project.import_src is None:
            pretty_print.print_error(
                f"The property blocks/{self.block_id}/project/import_src is required to import the block, but it is not set."
            )
            sys.exit(1)
        elif urllib.parse.urlparse(self.block_cfg.project.import_src).scheme == "file":
            prebuilt_block_package = pathlib.Path(urllib.parse.urlparse(self.block_cfg.project.import_src).path)
        elif validators.url(self.block_cfg.project.import_src):
            self._download_prebuilt()
            downloads = list(self._download_dir.glob("*"))
            # Check if there is more than one file in the download directory
            if len(downloads) != 1:
                pretty_print.print_error(f"Not exactly one file in {self._download_dir}")
                sys.exit(1)
            prebuilt_block_package = downloads[0]
        else:
            raise ValueError(
                "The following string is not a valid reference to a block package: "
                f"{self.block_cfg.project.import_src}. Only URI schemes 'https', 'http', and 'file' "
                "are supported."
            )

        # Check whether the file is a supported archive
        if not prebuilt_block_package.name.endswith(("tar.gz", "tgz", "tar.xz", "txz")):
            pretty_print.print_error(
                f"Unable to import block package. The type of this archive is not supported: {prebuilt_block_package.name}"
            )
            sys.exit(1)

        # Calculate md5 of the provided file
        md5_new_file = hashlib.md5(prebuilt_block_package.read_bytes()).hexdigest()
        # Read md5 of previously used file, if any
        md5_existsing_file = 0
        if self._source_bp_md5_file.is_file():
            with self._source_bp_md5_file.open("r") as f:
                md5_existsing_file = f.read()

        # Check if the pre-built file system needs to be imported
        if md5_existsing_file == md5_new_file:
            pretty_print.print_build("No need to import the pre-built file system. No altered source files detected...")
            return

        self.clean_work()
        self._work_dir.mkdir(parents=True)

        pretty_print.print_build("Importing pre-built file system...")

        # Extract pre-built files
        with tarfile.open(prebuilt_block_package, "r:*") as archive:
            content = archive.getnames()
            # Filter the list to get only .tar.xz and .tar.gz files
            tar_files = [f for f in content if f.endswith((".tar.xz", ".tar.gz"))]
            if len(tar_files) != 1:
                pretty_print.print_error(
                    f"There are {len(tar_files)} *.tar.xz and *.tar.gz files in archive {prebuilt_block_package}. Expected was 1."
                )
                sys.exit(1)
            prebuilt_fs_archive = tar_files[0]
            # Extract file system archive to the work directory
            archive.extract(member=prebuilt_fs_archive, path=self._work_dir)

        if self.block_id == "rootfs":
            extract_pb_fs_commands = [
                f"mkdir -p {self._build_dir}",
                f"tar --numeric-owner -p -xf {self._work_dir / prebuilt_fs_archive} -C {self._build_dir}",
            ]
        elif self.block_id == "ramfs":
            extract_pb_fs_commands = [
                f"mkdir -p {self._build_dir}",
                f'gunzip -c {self._work_dir / prebuilt_fs_archive} | sh -c "cd {self._build_dir}/ && cpio -i"',
            ]
        else:
            raise ValueError(f"Value of 'block_id' must be 'rootfs' or 'ramfs'")

        # The root user is used in this container. This is necessary in order to build a file system image.
        self.container_executor.exec_sh_commands(
            commands=extract_pb_fs_commands, dirs_to_mount=[(self._work_dir, "Z")], run_as_root=True
        )

        # Save checksum in file
        with self._source_bp_md5_file.open("w") as f:
            print(md5_new_file, file=f, end="")

        # Delete imported, pre-built file system archive
        (self._work_dir / prebuilt_fs_archive).unlink()

    def clean_work(self):
        """
        This function cleans the work directory as root user.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        super().clean_work(as_root=True)
