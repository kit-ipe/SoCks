import sys
import pathlib
import hashlib
import tarfile
from dateutil import parser
import urllib
import requests
import validators
import tqdm
import inspect

import socks.pretty_print as pretty_print
from builders.builder import Builder
from builders.zynqmp_almalinux_rootfs_model import ZynqMP_AlmaLinux_RootFS_Model


class ZynqMP_AlmaLinux_RootFS_Builder(Builder):
    """
    AlmaLinux root file system builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "rootfs",
        block_description: str = "Build an AlmaLinux root file system",
        model_class: type[object] = ZynqMP_AlmaLinux_RootFS_Model,
    ):

        super().__init__(
            project_cfg=project_cfg,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
            model_class=model_class,
        )

        self._rootfs_name = f"almalinux{self.block_cfg.project.release}_zynqmp_{self.project_cfg.project.name}"
        self._target_arch = "aarch64"

        # Project directories
        self._repo_dir = self._block_src_dir / "resources"
        self._build_dir = self._work_dir / self._rootfs_name

        # Project files
        # File for version & build info tracking
        self._build_info_file = self._work_dir / "fs_build_info"
        # File for saving the checksum of the Kernel module archive used
        self._source_kmods_md5_file = self._work_dir / "source_kmodules.md5"

        # Products of other blocks on which this block depends
        # This dict is used to check whether the imported block packages contain
        # all the required files. Regex can be used to describe the expected files.
        # Optional dependencies can also be listed here. They will be ignored if
        # they are not listed in the project configuration.
        self._block_deps = {
            "kernel": [".*"],
            "devicetree": ["system.dtb", "system.dts"],
            "vivado": [".*.bit"],
        }

        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        self.block_cmds = {"prepare": [], "build": [], "prebuild": [], "clean": [], "start-container": []}
        self.block_cmds["prepare"].extend(
            [
                self.container_executor.build_container_image,
                self.import_dependencies,
                self.container_executor.enable_multiarch,
                self.save_project_cfg_prepare,
            ]
        )
        self.block_cmds["clean"].extend(
            [
                self.container_executor.build_container_image,
                self.clean_download,
                self.clean_work,
                self.clean_dependencies,
                self.clean_output,
                self.clean_block_temp,
            ]
        )
        if self.block_cfg.source == "build":
            self.block_cmds["build"].extend(
                [func for func in self.block_cmds["prepare"] if func != self.save_project_cfg_prepare]
            )  # Append list without save_project_cfg_prepare
            self.block_cmds["build"].extend(
                [
                    self.build_base_rootfs,
                    self.add_pd_layers,
                    self.add_users,
                    self.add_kmodules,
                    self.add_bt_layer,
                    self.build_archive,
                    self.export_block_package,
                    self.save_project_cfg_build,
                ]
            )
            self.block_cmds["prebuild"].extend(
                [func for func in self.block_cmds["prepare"] if func != self.save_project_cfg_prepare]
            )  # Append list without save_project_cfg_prepare
            self.block_cmds["prebuild"].extend(
                [
                    self.build_base_rootfs,
                    self.build_archive_prebuilt,
                    self.export_block_package,
                    self.save_project_cfg_build,
                ]
            )
            self.block_cmds["start-container"].extend(
                [self.container_executor.build_container_image, self.start_container]
            )
        elif self.block_cfg.source == "import":
            self.block_cmds["build"].extend(
                [func for func in self.block_cmds["prepare"] if func != self.save_project_cfg_prepare]
            )  # Append list without save_project_cfg_prepare
            self.block_cmds["build"].extend(
                [
                    self.import_prebuilt,
                    self.add_pd_layers,
                    self.add_users,
                    self.add_kmodules,
                    self.add_bt_layer,
                    self.build_archive,
                    self.export_block_package,
                    self.save_project_cfg_build,
                ]
            )

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
        self.import_src_tpl()

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

        dnf_conf_file = self._repo_dir / "dnf_build_time.conf"
        mod_base_install_script = self._repo_dir / "mod_base_install.sh"

        # Check whether the base root file system needs to be built
        if not ZynqMP_AlmaLinux_RootFS_Builder._check_rebuild_bc_timestamp(
            src_search_list=[dnf_conf_file, mod_base_install_script],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ) and not self._check_rebuild_bc_config(keys=[["blocks", self.block_id, "project"], ["project", "name"]]):
            pretty_print.print_build(
                "No need to rebuild the base root file system. No altered source files detected..."
            )
            return

        # Reset function success log
        self._build_log.del_logged_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")

        self._work_dir.mkdir(parents=True, exist_ok=True)

        if not dnf_conf_file.is_file():
            pretty_print.print_error(f"The following dnf configuration file is required: {dnf_conf_file}")
            sys.exit(1)

        pretty_print.print_build("Building the base root file system...")

        dnf_base_command = f"dnf -y --nodocs --verbose -c {dnf_conf_file} --releasever={self.block_cfg.project.release} --forcearch={self._target_arch} --installroot={self._build_dir} "
        base_rootfs_build_commands = [
            # If a QEMU binary exists, it is probably needed to run aarch64 binaries on an x86 system during build. So copy it to build_dir.
            f"if [ -e /usr/bin/qemu-aarch64-static ]; then "
            f"    mkdir -p {self._build_dir}/usr/bin && "
            f"    cp -a /usr/bin/qemu-aarch64-static {self._build_dir}/usr/bin/; "
            f"fi",
            # Clean all cache files generated from repository metadata
            dnf_base_command + "clean all",
            # Update all the installed packages
            dnf_base_command + "update",
            'printf "\nInstall the base os via dnf group install...\n\n"',
            # The 'Minimal Install' group consists of the 'Core' group and optionally the 'Standard' and 'Guest Agents' groups
            dnf_base_command + 'groupinstall --with-optional "Minimal Install"',
        ]

        if mod_base_install_script.is_file():
            base_rootfs_build_commands.extend(
                [
                    'printf "\nCall user-defined script to make changes to the base os...\n\n"',
                    f"chmod a+x {mod_base_install_script}",
                    f"{mod_base_install_script} {self._target_arch} {self.block_cfg.project.release} {dnf_conf_file} {self._build_dir}",
                ]
            )
        else:
            pretty_print.print_info(
                f"File {mod_base_install_script} not found. No user-defined changes are made to the base os."
            )

        if self.block_cfg.project.extra_rpms:
            base_rootfs_build_commands.extend(
                [
                    'printf "\nInstalling user defined packages...\n\n"',
                    dnf_base_command + "install " + " ".join(self.block_cfg.project.extra_rpms),
                ]
            )
        else:
            pretty_print.print_info(
                f"'rootfs -> project -> extra_rpms' not specified. No additional rpm packages will be installed."
            )

        # The QEMU binary if only required during build, so delete it if it exists
        base_rootfs_build_commands.append(f"rm -f {self._build_dir}/usr/bin/qemu-aarch64-static")

        # The root user is used in this container. This is necessary in order to build a RootFS image.
        self.container_executor.exec_sh_commands(
            commands=base_rootfs_build_commands,
            dirs_to_mount=[(self._repo_dir, "Z"), (self._work_dir, "Z")],
            run_as_root=True,
            logfile=self._block_temp_dir / "build_base.log",
            output_scrolling=True,
        )

        # Reset timestamps
        self._build_log.del_logged_timestamp(identifier=f"function-add_pd_layers-success")
        self._build_log.del_logged_timestamp(identifier=f"function-add_bt_layer-success")
        self._build_log.del_logged_timestamp(identifier=f"function-add_users-success")

        # Log success of this function
        self._build_log.log_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")

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

        # Check whether the predefined file system layers need to be added
        layers_already_added = (
            self._build_log.get_logged_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")
            != 0.0
        )
        if layers_already_added and not ZynqMP_AlmaLinux_RootFS_Builder._check_rebuild_bc_timestamp(
            src_search_list=[self._repo_dir / "predefined_fs_layers"],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ):
            pretty_print.print_build(
                "No need to add predefined file system layers. No altered source files detected..."
            )
            return

        # Reset function success log
        self._build_log.del_logged_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")

        pretty_print.print_build("Adding predefined file system layers...")

        add_pd_layers_commands = [
            f"cd {self._repo_dir / 'predefined_fs_layers'}",
            f'for dir in ./*; do "$dir"/install_layer.sh {self._build_dir}/; done',
        ]

        # The root user is used in this container. This is necessary in order to build a RootFS image.
        self.container_executor.exec_sh_commands(
            commands=add_pd_layers_commands,
            dirs_to_mount=[(self._repo_dir, "Z"), (self._work_dir, "Z")],
            run_as_root=True,
        )

        # Log success of this function
        self._build_log.log_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")

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

        # Check whether the layer needs to be added
        if not self.block_cfg.project.build_time_fs_layer:
            pretty_print.print_info(
                f"'rootfs -> project -> build_time_fs_layer' not specified. No files and directories created at build time will be added."
            )
            return
        layer_already_added = (
            self._build_log.get_logged_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")
            != 0.0
        )
        if (
            layer_already_added
            and not ZynqMP_AlmaLinux_RootFS_Builder._check_rebuild_bc_timestamp(
                src_search_list=[self._dependencies_dir],
                out_timestamp=self._build_log.get_logged_timestamp(
                    identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
                ),
            )
            and not self._check_rebuild_bc_config(keys=[["blocks", self.block_id, "project", "build_time_fs_layer"]])
        ):
            pretty_print.print_build(
                "No need to add external files and directories created at build time. No altered source files detected..."
            )
            return

        # Reset function success log
        self._build_log.del_logged_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")

        pretty_print.print_build("Adding external files and directories created at build time...")

        add_bt_layer_commands = []
        for item in self.block_cfg.project.build_time_fs_layer:
            if item.src_block not in self._block_deps.keys():
                pretty_print.print_error(
                    f"Source block '{item.src_block}' specified in 'rootfs -> project -> build_time_fs_layer' is invalid."
                )
                sys.exit(1)
            srcs = (self._dependencies_dir / item.src_block).glob(item.src_name)
            if not srcs:
                pretty_print.print_error(
                    f"Source item '{item.src_name}' specified in 'rootfs -> project -> build_time_fs_layer' could not be found in the block package of source block '{item.src_block}'."
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

        # The root user is used in this container. This is necessary in order to build a RootFS image.
        self.container_executor.exec_sh_commands(
            commands=add_bt_layer_commands,
            dirs_to_mount=[(self._repo_dir, "Z"), (self._dependencies_dir, "Z"), (self._work_dir, "Z")],
            run_as_root=True,
        )

        # Log success of this function
        self._build_log.log_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")

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

        # Check whether users need to be added
        users_already_added = (
            self._build_log.get_logged_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")
            != 0.0
        )
        if users_already_added and not self._check_rebuild_bc_config(
            keys=[["blocks", self.block_id, "project", "users"]]
        ):
            pretty_print.print_build("No need to add users. No altered source files detected...")
            return

        # Reset function success log
        self._build_log.del_logged_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")

        pretty_print.print_build("Adding users...")

        add_users_commands = [
            # If a QEMU binary exists, it is probably needed to run aarch64 binaries on an x86 system during build. So copy it to build_dir.
            f"if [ -e /usr/bin/qemu-aarch64-static ]; then "
            f"    mkdir -p {self._build_dir}/usr/bin && "
            f"    cp -a /usr/bin/qemu-aarch64-static {self._build_dir}/usr/bin/; "
            f"fi"
        ]

        for user in self.block_cfg.project.users:
            add_user_str = ""
            if user.name != "root":
                add_user_str = add_user_str + f"useradd -m {user.name}; "
            for group in user.groups:
                add_user_str = add_user_str + f"usermod -a -G {group} {user.name} && "
            # Escape all $ symbols in the hash. I know this is ugly, but this is the only way I have found
            # to make it work through all the layers of Python, docker, sh and chroot.
            escaped_pw_hash = user.pw_hash.replace("$", "\\\\\\$")
            add_user_str = add_user_str + f"usermod -p {escaped_pw_hash} {user.name}"

            add_users_commands.append(f'chroot {self._build_dir} /bin/bash -c "{add_user_str}"')

        # The QEMU binary if only required during build, so delete it if it exists
        add_users_commands.append(f"rm -f {self._build_dir}/usr/bin/qemu-aarch64-static")

        # The root user is used in this container. This is necessary in order to build a RootFS image.
        self.container_executor.exec_sh_commands(
            commands=add_users_commands, dirs_to_mount=[(self._repo_dir, "Z"), (self._work_dir, "Z")], run_as_root=True
        )

        # Log success of this function
        self._build_log.log_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")

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

        kmods_archive = self._dependencies_dir / "kernel" / "kernel_modules.tar.gz"

        # Skip this function if no kernel modules are available
        if not kmods_archive.is_file():
            pretty_print.print_info(f"File {kmods_archive} not found. No kernel modules are added.")
            if any((self._build_dir / "lib" / "modules").iterdir()):
                delete_old_kmodules_commands = [f"rm -rf {self._build_dir}/lib/modules/*"]
                # The root user is used in this container. This is necessary in order to build a RootFS image.
                self.container_executor.exec_sh_commands(
                    commands=delete_old_kmodules_commands,
                    dirs_to_mount=[(self._work_dir, "Z")],
                    run_as_root=True,
                )
            return

        # Check whether a RootFS is present
        if not self._build_dir.is_dir():
            pretty_print.print_error(f"RootFS at {self._build_dir} not found.")
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
            f"chown -R root:root lib",
            f"chmod -R 000 lib",
            f"chmod -R u=rwX,go=rX lib",
            f"rm -rf {self._build_dir}/lib/modules",
            f"mkdir -p {self._build_dir}/lib/modules",
            f"mv lib/modules/* {self._build_dir}/lib/modules/",
            f"rm -rf lib",
        ]

        # The root user is used in this container. This is necessary in order to build a RootFS image.
        self.container_executor.exec_sh_commands(
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
        if not ZynqMP_AlmaLinux_RootFS_Builder._check_rebuild_bc_timestamp(
            src_search_list=[self._work_dir],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ) and not self._check_rebuild_bc_config(keys=[["blocks", self.block_id, "project"], ["project", "name"]]):
            pretty_print.print_build("No need to rebuild archive. No altered source files detected...")
            return

        # Reset function success log
        self._build_log.del_logged_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")

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

            # The root user is used in this container. This is necessary in order to build a RootFS image.
            self.container_executor.exec_sh_commands(
                commands=add_build_info_commands,
                dirs_to_mount=[(self._work_dir, "Z")],
                run_as_root=True,
            )
        else:
            # Remove existing build information file
            clean_build_info_commands = [f"rm -f {self._build_dir}/etc/fs_build_info"]

            # The root user is used in this container. This is necessary in order to build a RootFS image.
            self.container_executor.exec_sh_commands(
                commands=clean_build_info_commands,
                dirs_to_mount=[(self._work_dir, "Z")],
                run_as_root=True,
            )

        if prebuilt:
            archive_name = f"almalinux{self.block_cfg.project.release}_zynqmp_pre-built"
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
            f"fi",
        ]

        # The root user is used in this container. This is necessary in order to build a RootFS image.
        self.container_executor.exec_sh_commands(
            commands=archive_build_commands,
            dirs_to_mount=[(self._work_dir, "Z"), (self._output_dir, "Z")],
            run_as_root=True,
        )

        # Log success of this function
        self._build_log.log_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")

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
            f"tar --numeric-owner -p -xf {self._work_dir / prebuilt_rootfs_archive} -C {self._build_dir}",
        ]

        # The root user is used in this container. This is necessary in order to build a RootFS image.
        self.container_executor.exec_sh_commands(
            commands=extract_pb_rootfs_commands, dirs_to_mount=[(self._work_dir, "Z")], run_as_root=True
        )

        # Save checksum in file
        with self._source_pb_md5_file.open("w") as f:
            print(md5_new_file, file=f, end="")

        # Delete imported, pre-built rootfs archive
        (self._work_dir / prebuilt_rootfs_archive).unlink()

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
