import sys
import pathlib
import shutil
import urllib
import hashlib
import inspect

import socks.pretty_print as pretty_print
from socks.build_validator import Build_Validator
from abstract_builders.file_system_builder import File_System_Builder
from amd_zynqmp_support.zynqmp_busybox_ramfs_model import ZynqMP_BusyBox_RAMFS_Model


class ZynqMP_BusyBox_RAMFS_Builder(File_System_Builder):
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

        # Project files
        # File for version & build info tracking
        self._build_info_file = self._work_dir / "fs_build_info"
        # File for saving the checksum of the Kernel module archive used
        self._source_kmods_md5_file = self._work_dir / "source_kmodules.md5"

    @property
    def _block_deps(self):
        # Products of other blocks on which this block depends
        # This dict is used to check whether the imported block packages contain
        # all the required files. Regex can be used to describe the expected files.
        # Optional dependencies can also be listed here. They will be ignored if
        # they are not listed in the project configuration.
        block_deps = {"kernel": [".*"]}
        return block_deps

    @property
    def block_cmds(self):
        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        block_cmds = {
            "prepare": [],
            "build": [],
            "prebuild": [],
            "clean": [],
            "create-patches": [],
            "start-container": [],
            "menucfg": [],
            "prep-clean-srcs": [],
        }
        block_cmds["prepare"].extend(
            [
                self._build_validator.del_project_cfg,
                self.container_executor.build_container_image,
                self.import_dependencies,
                self._build_validator.save_project_cfg_prepare,
            ]
        )
        block_cmds["clean"].extend(
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
            block_cmds["prepare"] = [  # Move save_project_cfg_prepare to the end of the new list
                func for func in block_cmds["prepare"] if func != self._build_validator.save_project_cfg_prepare
            ] + [
                self.init_repo,
                self.apply_patches,
                self.create_proj_cfg_patch,
                self._build_validator.save_project_cfg_prepare,
            ]
            block_cmds["build"].extend(block_cmds["prepare"])
            block_cmds["build"].extend(
                [
                    self.build_base_file_system,
                    self.add_kmodules,
                    self.add_sr_layer,
                    self.add_pd_layers,
                    self.build_archive,
                    self.export_block_package,
                    self._build_validator.save_project_cfg_build,
                ]
            )
            block_cmds["prebuild"].extend(block_cmds["prepare"])
            block_cmds["prebuild"].extend(
                [
                    self.build_base_file_system,
                    self.add_sr_layer,
                    self.build_archive_prebuilt,
                    self.export_block_package,
                    self._build_validator.save_project_cfg_build,
                ]
            )
            block_cmds["create-patches"].extend([self.create_patches])
            block_cmds["start-container"].extend([self.container_executor.build_container_image, self.start_container])
            block_cmds["menucfg"].extend([self.container_executor.build_container_image, self.run_menuconfig])
            block_cmds["prep-clean-srcs"].extend(block_cmds["clean"])
            block_cmds["prep-clean-srcs"].extend(
                [self.container_executor.build_container_image, self.init_repo, self.prep_clean_srcs]
            )
        elif self.block_cfg.source == "import":
            block_cmds["build"].extend(block_cmds["prepare"])
            block_cmds["build"].extend(
                [
                    self.import_prebuilt,
                    self.add_kmodules,
                    self.add_pd_layers,
                    self.build_archive,
                    self.export_block_package,
                    self._build_validator.save_project_cfg_build,
                ]
            )
        return block_cmds

    @property
    def _file_system_name(self):
        return f"busybox_fs_zynqmp_{self.project_cfg.project.name}"

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

        if not self._patch_dir.is_dir():
            self.pre_action_warnings.append(
                "This block requires a configuration file in the source repo to be initialized, "
                "but no patches were found. If you proceed, SoCks will automatically initialize the "
                "configuration file, create a patch and add it to your project."
            )
            # Function 'create_proj_cfg_patch' is called with block command 'prepare' at a suitable stage.
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

    def build_base_file_system(self):
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
            self._build_dir.mkdir(parents=True)

            pretty_print.print_build("Building the base ram file system...")

            base_ramfs_build_commands = [
                f"cd {self._source_repo_dir}",
                f'sed -i "s%^CONFIG_PREFIX=.*$%CONFIG_PREFIX=\\"{self._build_dir}\\"%" .config',
                f"make -j{self.project_cfg.external_tools.make.max_build_threads} CROSS_COMPILE=aarch64-unknown-linux-uclibc-",
                f"mkdir -p {self._build_dir}",
                f"cd {self._build_dir}",
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

    def add_sr_layer(self):
        """
        Adds unprocessed files and directories from the source repo.

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

        # Check whether the layer needs to be added
        if not self.block_cfg.project.source_repo_fs_layer:
            pretty_print.print_info(
                f"'{self.block_id} -> project -> source_repo_fs_layer' not specified. "
                "No additional unprocessed files and directories from the source repo will be added."
            )
            return
        layer_already_added = (
            self._build_log.get_logged_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")
            != 0.0
        )
        if (
            layer_already_added
            and not Build_Validator.check_rebuild_bc_timestamp(
                src_search_list=[self._source_repo_dir],
                out_timestamp=self._build_log.get_logged_timestamp(
                    identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
                ),
            )
            and not self._build_validator.check_rebuild_bc_config(
                keys=[["blocks", self.block_id, "project", "source_repo_fs_layer"]]
            )
        ):
            pretty_print.print_build(
                "No need to add additional unprocessed files and directories from the source repo. "
                "No altered source files detected..."
            )
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            pretty_print.print_build("Adding additional unprocessed files and directories from the source repo...")

            add_sr_layer_commands = []
            for item in self.block_cfg.project.source_repo_fs_layer:
                srcs = self._source_repo_dir.glob(item.src_name)
                if not srcs:
                    pretty_print.print_error(
                        f"Source item '{item.src_name}' specified in '{self.block_id} -> project -> source_repo_fs_layer' "
                        f"could not be found in the source repo '{self._source_repo_dir}'."
                    )
                    sys.exit(1)
                add_sr_layer_commands.append(f"mkdir -p {self._build_dir}/{item.dest_path}")
                for src in srcs:
                    add_sr_layer_commands.append(f"cp -r {src} {self._build_dir}/{item.dest_path}/{item.dest_name}")
                    if item.dest_owner_group:
                        add_sr_layer_commands.append(
                            f"chown -R {item.dest_owner_group} {self._build_dir}/{item.dest_path}/{item.dest_name}"
                        )
                    if item.dest_permissions:
                        add_sr_layer_commands.append(
                            f"chmod -R {item.dest_permissions} {self._build_dir}/{item.dest_path}/{item.dest_name}"
                        )

            # The root user is used in this container. This is necessary in order to build a file system image.
            self.container_executor.exec_sh_commands(
                commands=add_sr_layer_commands,
                dirs_to_mount=[(self._repo_dir, "Z"), (self._work_dir, "Z")],
                print_commands=True,
                run_as_root=True,
            )

    def build_archive(self, prebuilt: bool = False):
        """
        Packs the entire ram file system in an archive.

        Args:
            prebuilt:
                Set to True if the archive will contain pre-built files
                instead of a complete project file system.

        Returns:
            None

        Raises:
            None
        """

        if prebuilt:
            archive_name = f"busybox_fs_zynqmp_pre-built"
        else:
            archive_name = self._file_system_name

        self._build_archive(archive_name=archive_name, file_extension="cpio.gz")

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
