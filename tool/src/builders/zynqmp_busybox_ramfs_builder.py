import sys
import pathlib
import shutil
import urllib
import hashlib
import inspect

import socks.pretty_print as pretty_print
from socks.build_validator import Build_Validator
from builders.builder import Builder
from builders.zynqmp_busybox_ramfs_model import ZynqMP_BusyBox_RAMFS_Model


class ZynqMP_BusyBox_RAMFS_Builder(Builder):
    """
    BusyBox RAM file system builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "ramfs",
        block_description: str = "Build an BusyBox RAM file system (initramfs)",
        model_class: type[object] = ZynqMP_BusyBox_RAMFS_Model,
    ):

        super().__init__(
            project_cfg=project_cfg,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
            model_class=model_class,
        )

        self._ramfs_name = f"busybox_fs_zynqmp_{self.project_cfg.project.name}"

        # Project directories
        self._resources_dir = self._block_src_dir / "resources"
        self._mod_dir = self._work_dir / self._ramfs_name

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
        self._block_deps = {"kernel": [".*"]}

        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        self.block_cmds = {
            "prepare": [],
            "build": [],
            "prebuild": [],
            "clean": [],
            "create-patches": [],
            "start-container": [],
            "menucfg": [],
            "prep-clean-srcs": [],
        }
        self.block_cmds["prepare"].extend(
            [
                self._build_validator.del_project_cfg,
                self.container_executor.build_container_image,
                self.import_dependencies,
                self._build_validator.save_project_cfg_prepare,
            ]
        )
        self.block_cmds["clean"].extend(
            [
                self.container_executor.build_container_image,
                self.clean_download,
                self.clean_work,
                self.clean_repo,
                self.clean_dependencies,
                self.clean_output,
                self.clean_block_temp,
            ]
        )
        if self.block_cfg.source == "build":
            self.block_cmds["prepare"] = [  # Move save_project_cfg_prepare to the end of the new list
                func for func in self.block_cmds["prepare"] if func != self._build_validator.save_project_cfg_prepare
            ] + [
                self.init_repo,
                self.apply_patches,
                self.import_clean_srcs,
                self._build_validator.save_project_cfg_prepare,
            ]
            self.block_cmds["build"].extend(self.block_cmds["prepare"])
            self.block_cmds["build"].extend(
                [
                    self.build_base_ramfs,
                    self.populate_ramfs,
                    self.add_kmodules,
                    self.build_archive,
                    self.export_block_package,
                    self._build_validator.save_project_cfg_build,
                ]
            )
            self.block_cmds["prebuild"].extend(self.block_cmds["prepare"])
            self.block_cmds["prebuild"].extend(
                [
                    self.build_base_ramfs,
                    self.build_archive_prebuilt,
                    self.export_block_package,
                    self._build_validator.save_project_cfg_build,
                ]
            )
            self.block_cmds["create-patches"].extend([self.create_patches])
            self.block_cmds["start-container"].extend(
                [self.container_executor.build_container_image, self.start_container]
            )
            self.block_cmds["menucfg"].extend([self.container_executor.build_container_image, self.run_menuconfig])
            self.block_cmds["prep-clean-srcs"].extend(self.block_cmds["clean"])
            self.block_cmds["prep-clean-srcs"].extend(
                [self.container_executor.build_container_image, self.init_repo, self.prep_clean_srcs]
            )
        elif self.block_cfg.source == "import":
            self.block_cmds["build"].extend(self.block_cmds["prepare"])
            self.block_cmds["build"].extend(
                [
                    self.import_prebuilt,
                    self.add_kmodules,
                    self.build_archive,
                    self.export_block_package,
                    self._build_validator.save_project_cfg_build,
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

        if not self._patch_dir.is_dir():
            self.pre_action_warnings.append(
                "This block requires patch files, but none were found. "
                "If you proceed, SoCks will automatically generate patches for a clean project and add them to your project."
            )
            # Function 'import_clean_srcs' is called with block command 'prepare' at a suitable stage.
            # Calling it here would not make sense, because the repo might not be ready yet.

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

        menuconfig_commands = [
            f"cd {self._source_repo_dir}",
            "make CROSS_COMPILE=aarch64-unknown-linux-uclibc- menuconfig",
        ]

        super()._run_menuconfig(menuconfig_commands=menuconfig_commands)

    def prep_clean_srcs(self):
        """
        This function is intended to create a new, clean project. After the creation
        of the project one should create a patch that includes .gitignore and .config.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        prep_srcs_commands = [
            f"cd {self._source_repo_dir}",
            "make CROSS_COMPILE=aarch64-unknown-linux-uclibc- defconfig",
            'sed -i "s%^# CONFIG_STATIC is not set$%CONFIG_STATIC=y%" .config',
            'printf "\n# Do not ignore the config file\n!.config\n" >> .gitignore',
        ]

        super()._prep_clean_srcs(prep_srcs_commands=prep_srcs_commands)

    def build_base_ramfs(self):
        """
        Builds the base ram file system.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check whether the base ram file system needs to be built
        if not Build_Validator.check_rebuild_bc_timestamp(
            src_search_list=[self._source_repo_dir],
            src_ignore_list=[
                self._source_repo_dir / "busybox",
                self._source_repo_dir / "busybox.links",
                self._source_repo_dir / ".kernelrelease",
            ],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ):
            pretty_print.print_build("No need to rebuild the base ram file system. No altered source files detected...")
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            self.clean_work()
            self._mod_dir.mkdir(parents=True)

            pretty_print.print_build("Building the base ram file system...")

            base_ramfs_build_commands = [
                f"cd {self._source_repo_dir}",
                f'sed -i "s%^CONFIG_PREFIX=.*$%CONFIG_PREFIX=\\"{self._mod_dir}\\"%" .config',
                f"make -j{self.project_cfg.external_tools.make.max_build_threads} CROSS_COMPILE=aarch64-unknown-linux-uclibc-",
                f"mkdir -p {self._mod_dir}",
                f"cd {self._mod_dir}",
                "mkdir -p {bin,dev,etc,lib64,proc,sbin,sys,tmp,usr,var}",
                "mkdir -p usr/{bin,sbin}",
                "mkdir -p var/log",
                "ln -sf lib64 lib",
                f"cd {self._source_repo_dir}",
                "make CROSS_COMPILE=aarch64-unknown-linux-uclibc- install",
            ]

            # The root user is used in this container. This is necessary in order to build a RAMFS image.
            self.container_executor.exec_sh_commands(
                commands=base_ramfs_build_commands,
                dirs_to_mount=[(self._repo_dir, "Z"), (self._work_dir, "Z")],
                print_commands=True,
                run_as_root=True,
                logfile=self._block_temp_dir / "build.log",
                output_scrolling=True,
            )

    def populate_ramfs(self):
        """
        Populates the ram file system with some fundamental files and directories.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check whether the ram file system needs to be populated
        if not Build_Validator.check_rebuild_bc_timestamp(
            src_search_list=[self._resources_dir],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ):
            pretty_print.print_build("No need to populate the ramfs. No altered source files detected...")
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            pretty_print.print_build("Populating the initramfs...")

            # Copy all required files to the work directory to make them accessable in the container
            # The files are copied before every build to make sure they are up to date
            shutil.copy(self._resources_dir / "interfaces", self._work_dir / "interfaces")
            shutil.copy(self._resources_dir / "init", self._work_dir / "init")

            populate_ramfs_commands = [
                f"cd {self._source_repo_dir}",
                f"install -D -m 755 examples/udhcp/simple.script {self._mod_dir}/usr/share/udhcpc/default.script",
                f"cd {self._mod_dir}",
                "mkdir -p etc/network",
                f"mv {self._work_dir}/interfaces etc/network/",
                "mkdir -p etc/network/if-pre-up.d",
                "mkdir -p etc/network/if-up.d",
                "mkdir -p etc/network/if-down.d",
                "mkdir -p etc/network/if-post-down.d",
                "mkdir -p var/run",
                f"mv {self._work_dir}/init .",
                "chmod a+x init",
            ]

            # The root user is used in this container. This is necessary in order to build a RAMFS image.
            self.container_executor.exec_sh_commands(
                commands=populate_ramfs_commands,
                dirs_to_mount=[(self._repo_dir, "Z"), (self._work_dir, "Z")],
                print_commands=True,
                run_as_root=True,
            )

    def add_kmodules(self):
        """
        Adds kernel modules to the ram file system.

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
            if (self._mod_dir / "lib" / "modules").is_dir():
                delete_old_kmodules_commands = [f"rm -rf {self._mod_dir}/lib/modules"]
                # The root user is used in this container. This is necessary in order to build a RootFS image.
                self.container_executor.exec_sh_commands(
                    commands=delete_old_kmodules_commands,
                    dirs_to_mount=[(self._work_dir, "Z")],
                    run_as_root=True,
                )
            return

        # Check whether a RootFS is present
        if not self._mod_dir.is_dir():
            pretty_print.print_error(f"RootFS at {self._mod_dir} not found.")
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
            f"rm -rf {self._mod_dir}/lib/modules",
            f"mkdir -p {self._mod_dir}/lib/modules",
            f"mv lib/modules/* {self._mod_dir}/lib/modules/",
            "rm -rf lib",
        ]

        # The root user is used in this container. This is necessary in order to build a RootFS image.
        self.container_executor.exec_sh_commands(
            commands=add_kmodules_commands,
            dirs_to_mount=[(self._dependencies_dir, "Z"), (self._work_dir, "Z")],
            print_commands=True,
            run_as_root=True,
        )

        # Save checksum in file
        with self._source_kmods_md5_file.open("w") as f:
            print(md5_new_file, file=f, end="")

    def build_archive(self, prebuilt: bool = False):
        """
        Packs the entire ramfs in a archive.

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
        if not Build_Validator.check_rebuild_bc_timestamp(
            src_search_list=[self._mod_dir],
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
                    f"mv {self._build_info_file} {self._mod_dir}/etc/fs_build_info",
                    f"chmod 0444 {self._mod_dir}/etc/fs_build_info",
                ]

                # The root user is used in this container. This is necessary in order to build a RootFS image.
                self.container_executor.exec_sh_commands(
                    commands=add_build_info_commands, dirs_to_mount=[(self._work_dir, "Z")], run_as_root=True
                )
            else:
                # Remove existing build information file
                clean_build_info_commands = [f"rm -f {self._mod_dir}/etc/fs_build_info"]

                # The root user is used in this container. This is necessary in order to build a RootFS image.
                self.container_executor.exec_sh_commands(
                    commands=clean_build_info_commands, dirs_to_mount=[(self._work_dir, "Z")], run_as_root=True
                )

            if prebuilt:
                archive_name = f"busybox_fs_zynqmp_pre-built"
            else:
                archive_name = self._ramfs_name

            archive_build_commands = [
                f"cd {self._mod_dir}",
                f"find . | cpio -H newc -o | gzip -9 > {self._output_dir / f'{archive_name}.cpio.gz'}",
                f"if id {self._host_user} >/dev/null 2>&1; then "
                f"    chown -R {self._host_user}:{self._host_user} {self._output_dir / f'{archive_name}.cpio.gz'}; "
                f"fi",
            ]

            # The root user is used in this container. This is necessary in order to build a RAMFS image.
            self.container_executor.exec_sh_commands(
                commands=archive_build_commands,
                dirs_to_mount=[(self._work_dir, "Z"), (self._output_dir, "Z")],
                print_commands=True,
                run_as_root=True,
            )

    def build_archive_prebuilt(self):
        """
        Packs the entire pre-built ramfs in a archive.

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
        Imports a pre-built ram file system.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Get path of the pre-built ram file system
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

        # Check if the pre-built ram file system needs to be imported
        if md5_existsing_file == md5_new_file:
            pretty_print.print_build(
                "No need to import the pre-built ram file system. No altered source files detected..."
            )
            return

        self.clean_work()
        self._mod_dir.mkdir(parents=True)

        pretty_print.print_build("Importing pre-built ram file system...")

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
            prebuilt_ramfs_archive = tar_files[0]
            # Extract ramfs archive to the work directory
            archive.extract(member=prebuilt_ramfs_archive, path=self._work_dir)

        extract_pb_ramfs_commands = [
            f'gunzip -c {self._work_dir / prebuilt_ramfs_archive} | sh -c "cd {self._mod_dir}/ && cpio -i"'
        ]

        # The root user is used in this container. This is necessary in order to build a RootFS image.
        self.container_executor.exec_sh_commands(
            commands=extract_pb_ramfs_commands, dirs_to_mount=[(self._work_dir, "Z")], run_as_root=True
        )

        # Save checksum in file
        with self._source_pb_md5_file.open("w") as f:
            print(md5_new_file, file=f, end="")

        # Delete imported, pre-built ramfs archive
        (self._work_dir / prebuilt_ramfs_archive).unlink()

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

    def clean_repo(self):
        """
        This function cleans the work directory as root user.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        super().clean_repo(as_root=True)
