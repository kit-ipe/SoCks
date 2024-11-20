import sys
import pathlib
import shutil
import hashlib
import tarfile
import csv
from dateutil import parser
import urllib
import requests
import validators
import tqdm

import socks.pretty_print as pretty_print
from builders.builder import Builder
from builders.zynqmp_alma_rootfs_model import ZynqMP_Alma_RootFS_Model


class ZynqMP_Alma_RootFS_Builder_Alma8(Builder):
    """
    AlmaLinux root file system builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        project_cfg_files: list,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "rootfs",
        block_description: str = "Build an AlmaLinux root file system",
    ):

        super().__init__(
            project_cfg=project_cfg,
            project_cfg_files=project_cfg_files,
            model_class=ZynqMP_Alma_RootFS_Model,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
        )

        self._rootfs_name = f"almalinux{self.block_cfg.release}_zynqmp_{self.project_cfg.project.name}"
        self._target_arch = "aarch64"

        # Project directories
        self._repo_dir = self._block_src_dir / "src"
        self._build_dir = self._work_dir / self._rootfs_name

        # Project files
        # File for version & build info tracking
        self._build_info_file = self._work_dir / "fs_build_info"
        # Flag to remember if predefined file system layers have already been added
        self._pfs_added_flag = self._work_dir / ".pfsladded"
        # Flag to remember if the build time file system layer has already been added
        self._btfs_added_flag = self._work_dir / ".btfsladded"
        # Flag to remember if users have already been added
        self._users_added_flag = self._work_dir / ".usersadded"
        # File for saving the checksum of the Kernel module archive used
        self._source_kmods_md5_file = self._work_dir / "source_kmodules.md5"

        # Products of other blocks on which this block depends
        # This dict is used to check whether the imported block packages contain
        # all the required files. Regex can be used to describe the expected files.
        # Optional dependencies can also be listed here. They will be ignored if
        # they are not listed in the project configuration.
        self._block_deps = {
            "kernel": ["kernel_modules.tar.gz"],
            "devicetree": ["system.dtb", "system.dts"],
            "vivado": [".*.xsa", ".*.bit"],
        }

        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        self.block_cmds = {"prepare": [], "build": [], "prebuild": [], "clean": [], "start-container": []}
        self.block_cmds["prepare"].extend([self.build_container_image, self.import_dependencies, self.enable_multiarch])
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
        if self.block_cfg.source == "build":
            self.block_cmds["build"].extend(self.block_cmds["prepare"])
            self.block_cmds["build"].extend(
                [
                    self.build_base_rootfs,
                    self.add_pd_layers,
                    self.add_users,
                    self.add_kmodules,
                    self.add_bt_layer,
                    self.build_archive,
                    self.export_block_package,
                ]
            )
            self.block_cmds["prebuild"].extend(self.block_cmds["prepare"])
            self.block_cmds["prebuild"].extend(
                [self.build_base_rootfs, self.build_archive_prebuilt, self.export_block_package]
            )
            self.block_cmds["start-container"].extend([self.build_container_image, self.start_container])
        elif self.block_cfg.source == "import":
            self.block_cmds["build"].extend(self.block_cmds["prepare"])
            self.block_cmds["build"].extend(
                [
                    self.import_prebuilt,
                    self.add_pd_layers,
                    self.add_users,
                    self.add_kmodules,
                    self.add_bt_layer,
                    self.build_archive,
                    self.export_block_package,
                ]
            )

    def build_base_rootfs(self):
        """
        Builds the base root file system.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check whether the base root file system needs to be built
        if not ZynqMP_Alma_RootFS_Builder_Alma8._check_rebuild_required(
            src_search_list=self._project_cfg_files + [self._repo_dir / "dnf_build_time.conf", self._repo_dir / "extra_rpms.csv"],
            out_search_list=[self._work_dir],
        ):
            pretty_print.print_build(
                "No need to rebuild the base root file system. No altered source files detected..."
            )
            return

        self._work_dir.mkdir(parents=True, exist_ok=True)

        dnf_conf_file = self._repo_dir / "dnf_build_time.conf"
        if not dnf_conf_file.is_file():
            pretty_print.print_error(f"The following dnf configuration file is required: {dnf_conf_file}")
            sys.exit(1)

        # Copy the build script to the working directory so that it is accessible from the container.
        build_script = self._work_dir / "mk_alma_rootfs.py"
        shutil.copy(self._builders_res_dir / build_script.name, build_script)

        pretty_print.print_build("Building the base root file system...")

        extra_rpms_file = self._repo_dir / "extra_rpms.csv"
        if extra_rpms_file.is_file():
            base_rootfs_build_commands = [
                f"python3 {build_script} --root={self._build_dir} --arch={self._target_arch} --dnfconf={dnf_conf_file} --extra={extra_rpms_file} --releasever={self.block_cfg.release}"
            ]
        else:
            pretty_print.print_warning(
                f"File {extra_rpms_file} not found. No additional rpm packages will be installed."
            )
            base_rootfs_build_commands = [
                f"python3 {build_script} --root={self._build_dir} --arch={self._target_arch} --dnfconf={dnf_conf_file} --releasever={self.block_cfg.release}"
            ]

        # The root user is used in this container. This is necessary in order to build a RootFS image.
        self.run_containerizable_sh_command(
            commands=base_rootfs_build_commands,
            dirs_to_mount=[(self._repo_dir, "Z"), (self._work_dir, "Z")],
            run_as_root=True,
        )

        # Remove flags
        self._pfs_added_flag.unlink(missing_ok=True)
        self._btfs_added_flag.unlink(missing_ok=True)
        self._users_added_flag.unlink(missing_ok=True)

    def add_pd_layers(self):
        """
        Adds predefined file system layers to the root file system.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check whether a RootFS is present
        if not self._build_dir.is_dir():
            pretty_print.print_error(f"RootFS at {self._build_dir} not found.")
            sys.exit(1)

        layer_conf_dir = self._repo_dir / "predefined_fs_layers"

        # Check whether the predefined file system layers need to be added
        if not layer_conf_dir.is_dir():
            pretty_print.print_warning(
                f"Directory {layer_conf_dir} not found. No predefined file system layers will be added."
            )
            return
        if self._pfs_added_flag.is_file() and not ZynqMP_Alma_RootFS_Builder_Alma8._check_rebuild_required(
            src_search_list=[layer_conf_dir], out_search_list=[self._work_dir]
        ):
            pretty_print.print_build(
                "No need to add predefined file system layers. No altered source files detected..."
            )
            return

        pretty_print.print_build("Adding predefined file system layers...")

        add_pd_layers_commands = [
            f"cd {layer_conf_dir}",
            f"for dir in ./*; do \"$dir\"/install_layer.sh {self._build_dir}/; done"
        ]

        # The root user is used in this container. This is necessary in order to build a RootFS image.
        self.run_containerizable_sh_command(
            commands=add_pd_layers_commands,
            dirs_to_mount=[(self._repo_dir, "Z"), (self._work_dir, "Z")],
            run_as_root=True,
        )

        # Create the flag if it doesn't exist and update the timestamps
        self._pfs_added_flag.touch()

    def add_bt_layer(self):
        """
        Adds external files and directories created at build time.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check whether a RootFS is present
        if not self._build_dir.is_dir():
            pretty_print.print_error(f"RootFS at {self._build_dir} not found.")
            sys.exit(1)

        layer_conf_file = self._repo_dir / "build_time_fs_layer.csv"

        # Check whether the layer needs to be added
        if not layer_conf_file.is_file():
            pretty_print.print_warning(
                f"File {layer_conf_file} not found. No files and directories created at build time will be added."
            )
            return
        if self._btfs_added_flag.is_file() and not ZynqMP_Alma_RootFS_Builder_Alma8._check_rebuild_required(
            src_search_list=[self._dependencies_dir, layer_conf_file], out_search_list=[self._work_dir]
        ):
            pretty_print.print_build(
                "No need to add external files and directories created at build time. No altered source files detected..."
            )
            return

        pretty_print.print_build("Adding external files and directories created at build time...")

        add_bt_layer_commands = []
        with open(layer_conf_file, "r", newline="") as csvfile:
            layer_conf = csv.reader(csvfile)
            for i, row in enumerate(layer_conf):
                line = i+1
                if len(row) != 6:
                    pretty_print.print_error(f"Line {line} in {layer_conf_file} does not have 6 columns.")
                    sys.exit(1)
                block, src_item, dest_path, dest_item, og, permissions = row
                if block not in self._block_deps.keys():
                    pretty_print.print_error(f"The block in line {line} in {layer_conf_file} is invalid.")
                    sys.exit(1)
                srcs = (self._dependencies_dir / block).glob(src_item)
                if not srcs:
                    pretty_print.print_error(f"The source in line {line} in {layer_conf_file} could not be found.")
                    sys.exit(1)
                add_bt_layer_commands.append(f"mkdir -p {self._build_dir}/{dest_path}")
                for src in srcs:
                    add_bt_layer_commands.append(f"cp -r {src} {self._build_dir}/{dest_path}/{dest_item}")
                    if og:
                        add_bt_layer_commands.append(f"chown -R {og} {self._build_dir}/{dest_path}/{dest_item}")
                    if permissions:
                        add_bt_layer_commands.append(f"chmod -R {permissions} {self._build_dir}/{dest_path}/{dest_item}")

        # The root user is used in this container. This is necessary in order to build a RootFS image.
        self.run_containerizable_sh_command(
            commands=add_bt_layer_commands,
            dirs_to_mount=[(self._repo_dir, "Z"), (self._dependencies_dir, "Z"), (self._work_dir, "Z")],
            run_as_root=True,
        )

        # Create the flag if it doesn't exist and update the timestamps
        self._btfs_added_flag.touch()

    def add_users(self):
        """
        Adds users to the root file system.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check whether a RootFS is present
        if not self._build_dir.is_dir():
            pretty_print.print_error(f"RootFS at {self._build_dir} not found.")
            sys.exit(1)

        user_conf_dir = self._repo_dir / "users"

        # Check whether users need to be added
        if not user_conf_dir.is_dir():
            pretty_print.print_warning(
                f"Directory {user_conf_dir} not found. No users will be added."
            )
            return
        if self._users_added_flag.is_file() and not ZynqMP_Alma_RootFS_Builder_Alma8._check_rebuild_required(
            src_search_list=[user_conf_dir], out_search_list=[self._work_dir]
        ):
            pretty_print.print_build("No need to add users. No altered source files detected...")
            return

        pretty_print.print_build("Adding users...")

        add_users_commands = [
            f"cp -r {user_conf_dir} {self._build_dir / 'tmp'}",
            f"chroot {self._build_dir} /bin/bash /tmp/users/add_users.sh",
            f"rm -rf {self._build_dir}/tmp/users"
        ]

        # The root user is used in this container. This is necessary in order to build a RootFS image.
        self.run_containerizable_sh_command(
            commands=add_users_commands, dirs_to_mount=[(self._repo_dir, "Z"), (self._work_dir, "Z")], run_as_root=True
        )

        # Create the flag if it doesn't exist and update the timestamps
        self._users_added_flag.touch()

    def add_kmodules(self):
        """
        Adds kernel modules to the root file system.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check whether a RootFS is present
        if not self._build_dir.is_dir():
            pretty_print.print_error(f"RootFS at {self._build_dir} not found.")
            sys.exit(1)

        kmods_archive = self._dependencies_dir / "kernel" / "kernel_modules.tar.gz"

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
            f"chown -R root:root lib",
            f"chmod -R 000 lib",
            f"chmod -R u=rwX,go=rX lib",
            f"rm -rf {self._build_dir}/lib/modules/*",
            f"mv lib/modules/* {self._build_dir}/lib/modules/",
            f"rm -rf lib"
        ]

        # The root user is used in this container. This is necessary in order to build a RootFS image.
        self.run_containerizable_sh_command(
            commands=add_kmodules_commands,
            dirs_to_mount=[(self._dependencies_dir, "Z"), (self._work_dir, "Z")],
            run_as_root=True,
        )

        # Save checksum in file
        with self._source_kmods_md5_file.open("w") as f:
            print(md5_new_file, file=f, end="")

    def build_archive(self, prebuilt: bool = False):
        """
        Packs the entire rootfs in a archive.

        Args:
            prebuilt:
                Set to True if the archive will contain pre-built files
                instead of a complete project file system.

        Returns:
            None

        Raises:
            None
        """

        # Check if the archive needs to be built
        if not ZynqMP_Alma_RootFS_Builder_Alma8._check_rebuild_required(
            src_search_list=self._project_cfg_files + [self._work_dir], out_search_list=[self._output_dir]
        ):
            pretty_print.print_build("No need to rebuild archive. No altered source files detected...")
            return

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
                f"chmod 0444 {self._build_dir}/etc/fs_build_info"
            ]

            # The root user is used in this container. This is necessary in order to build a RootFS image.
            self.run_containerizable_sh_command(
                commands=add_build_info_commands,
                dirs_to_mount=[(self._repo_dir, "Z"), (self._work_dir, "Z")],
                run_as_root=True,
            )
        else:
            # Remove existing build information file
            clean_build_info_commands = [f"rm -f {self._build_dir}/etc/fs_build_info"]

            # The root user is used in this container. This is necessary in order to build a RootFS image.
            self.run_containerizable_sh_command(
                commands=clean_build_info_commands,
                dirs_to_mount=[(self._repo_dir, "Z"), (self._work_dir, "Z")],
                run_as_root=True,
            )

        if prebuilt:
            archive_name = f"almalinux{self.block_cfg.release}_zynqmp_pre-built"
        else:
            archive_name = self._rootfs_name

        # Tar was tested with three compression options:
        # Option	Size	Duration
        # --xz	872M	real	17m59.080s
        # -I pxz	887M	real	3m43.987s
        # -I pigz	1.3G	real	0m20.747s
        archive_build_commands = [
            f"cd {self._build_dir}",
            f"tar -I pxz --numeric-owner -p -cf  {self._output_dir / f'{archive_name}.tar.xz'} ./",
            f"if id {self._host_user} >/dev/null 2>&1; then "
            f"    chown -R {self._host_user}:{self._host_user} {self._output_dir / f'{archive_name}.tar.xz'}; "
            f"fi"
        ]

        # The root user is used in this container. This is necessary in order to build a RootFS image.
        self.run_containerizable_sh_command(
            commands=archive_build_commands,
            dirs_to_mount=[(self._work_dir, "Z"), (self._output_dir, "Z")],
            run_as_root=True,
        )

    def build_archive_prebuilt(self):
        """
        Packs the entire pre-built rootfs in a archive.

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
        Imports a pre-built root file system and overwrites the existing one.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Get path of the pre-built root file system
        if self.block_cfg.project.import_src is None:
            pretty_print.print_error(
                f"The property blocks/{self.block_id}/project/import_src is required to import the block, but it is not set."
            )
            sys.exit(1)
        elif validators.url(self.block_cfg.project.import_src):
            self._download_prebuilt()
            downloads = list(self._download_dir.glob("*"))
            # Check if there is more than one file in the download directory
            if len(downloads) != 1:
                pretty_print.print_error(f"Not exactly one file in {self._download_dir}.")
                sys.exit(1)
            prebuilt_block_package = downloads[0]
        else:
            try:
                prebuilt_block_package = pathlib.Path(self.block_cfg.project.import_src)
            except ValueError:
                pretty_print.print_error(f"{self.block_cfg.project.import_src} is not a valid URL and not a valid path")
                sys.exit(1)

        # Check whether the file is a supported archive
        if prebuilt_block_package.name.partition(".")[2] not in ["tar.gz", "tgz", "tar.xz", "txz"]:
            pretty_print.print_error(
                f'Unable to import block package. The following archive type is not supported: {prebuilt_block_package.name.partition(".")[2]}'
            )
            sys.exit(1)

        # Calculate md5 of the provided file
        md5_new_file = hashlib.md5(prebuilt_block_package.read_bytes()).hexdigest()
        # Read md5 of previously used file, if any
        md5_existsing_file = 0
        if self._source_pb_md5_file.is_file():
            with self._source_pb_md5_file.open("r") as f:
                md5_existsing_file = f.read()

        # Check if the pre-built root file system needs to be imported
        if md5_existsing_file == md5_new_file:
            pretty_print.print_build(
                "No need to import the pre-built root file system. No altered source files detected..."
            )
            return

        self.clean_work()
        self._work_dir.mkdir(parents=True)

        pretty_print.print_build("Importing pre-built root file system...")

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
            prebuilt_rootfs_archive = tar_files[0]
            # Extract rootfs archive to the work directory
            archive.extract(member=prebuilt_rootfs_archive, path=self._work_dir)

        extract_pb_rootfs_commands = [
            f"mkdir -p {self._build_dir}",
            f"tar --numeric-owner -p -xf {self._work_dir / prebuilt_rootfs_archive} -C {self._build_dir}"
        ]

        # The root user is used in this container. This is necessary in order to build a RootFS image.
        self.run_containerizable_sh_command(
            commands=extract_pb_rootfs_commands, dirs_to_mount=[(self._work_dir, "Z")], run_as_root=True
        )

        # Save checksum in file
        with self._source_pb_md5_file.open("w") as f:
            print(md5_new_file, file=f, end="")

        # Delete imported, pre-built rootfs archive
        (self._work_dir / prebuilt_rootfs_archive).unlink()

    def clean_work(self):
        """
        This function cleans the work directory.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        super().clean_work(as_root=True)
