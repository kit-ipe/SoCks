import sys
import pathlib
import inspect

import socks.pretty_print as pretty_print
from socks.build_validator import Build_Validator
from abstract_builders.file_system_builder import File_System_Builder
from amd_zynqmp_builders.zynqmp_almalinux_rootfs_model import ZynqMP_AlmaLinux_RootFS_Model


class ZynqMP_AlmaLinux_RootFS_Builder(File_System_Builder):
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

        self._target_arch = "aarch64"

        # Project directories
        self._resources_dir = self._block_src_dir / "resources"

        # Project files
        # dnf configuration file to be used to build the file system for the target architecture
        self._dnf_conf_file = self._resources_dir / "dnf_build_time.conf"

    @property
    def _block_deps(self):
        # Products of other blocks on which this block depends
        # This dict is used to check whether the imported block packages contain
        # all the required files. Regex can be used to describe the expected files.
        # Optional dependencies can also be listed here. They will be ignored if
        # they are not listed in the project configuration.
        block_deps = {
            "kernel": [".*"],
            "devicetree": ["system.dtb", "system.dts"],
            "vivado": [".*.bit"],
        }
        return block_deps

    @property
    def block_cmds(self):
        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        block_cmds = {"prepare": [], "build": [], "prebuild": [], "clean": [], "start-container": []}
        block_cmds["prepare"].extend(
            [
                self._build_validator.del_project_cfg,
                self.container_executor.build_container_image,
                self.import_dependencies,
                self.container_executor.enable_multiarch,
                self._build_validator.save_project_cfg_prepare,
            ]
        )
        block_cmds["clean"].extend(
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
            block_cmds["build"].extend(block_cmds["prepare"])
            block_cmds["build"].extend(
                [
                    self.build_base_file_system,
                    self.add_addl_packages,
                    self.add_users,
                    self.add_kmodules,
                    self.add_bt_layer,
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
                    self.add_addl_packages,
                    self.build_archive_prebuilt,
                    self.export_block_package,
                    self._build_validator.save_project_cfg_build,
                ]
            )
            block_cmds["start-container"].extend([self.container_executor.build_container_image, self.start_container])
        elif self.block_cfg.source == "import":
            block_cmds["build"].extend(block_cmds["prepare"])
            block_cmds["build"].extend(
                [
                    self.import_prebuilt,
                    self.add_users,
                    self.add_kmodules,
                    self.add_bt_layer,
                    self.add_pd_layers,
                    self.build_archive,
                    self.export_block_package,
                    self._build_validator.save_project_cfg_build,
                ]
            )
        return block_cmds

    @property
    def _file_system_name(self):
        return f"almalinux{self.block_cfg.project.release}_zynqmp_{self.project_cfg.project.name}"

    def build_base_file_system(self):
        """
        Builds the base root file system.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        mod_base_install_script = self._resources_dir / "mod_base_install.sh"

        # Check whether the base root file system needs to be built
        if not Build_Validator.check_rebuild_bc_timestamp(
            src_search_list=[self._dnf_conf_file, mod_base_install_script],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ) and not self._build_validator.check_rebuild_bc_config(
            keys=[["blocks", self.block_id, "project"], ["project", "name"]]
        ):
            pretty_print.print_build(
                "No need to rebuild the base root file system. No altered source files detected..."
            )
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            self._work_dir.mkdir(parents=True, exist_ok=True)

            if not self._dnf_conf_file.is_file():
                pretty_print.print_error(f"The following dnf configuration file is required: {self._dnf_conf_file}")
                sys.exit(1)

            pretty_print.print_build("Building the base root file system...")

            dnf_base_command = f"dnf -y --nodocs --verbose -c {self._dnf_conf_file} --releasever={self.block_cfg.project.release} --forcearch={self._target_arch} --installroot={self._build_dir} "
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
                        f"{mod_base_install_script} {self._target_arch} {self.block_cfg.project.release} {self._dnf_conf_file} {self._build_dir}",
                    ]
                )
            else:
                pretty_print.print_info(
                    f"File {mod_base_install_script} not found. No user-defined changes are made to the base os."
                )

            # The QEMU binary if only required during build, so delete it if it exists
            base_rootfs_build_commands.append(f"rm -f {self._build_dir}/usr/bin/qemu-aarch64-static")

            # The root user is used in this container. This is necessary in order to build a RootFS image.
            self.container_executor.exec_sh_commands(
                commands=base_rootfs_build_commands,
                dirs_to_mount=[(self._resources_dir, "Z"), (self._work_dir, "Z")],
                print_commands=True,
                run_as_root=True,
                logfile=self._block_temp_dir / "build_base.log",
                output_scrolling=True,
            )

            # Reset timestamps
            self._build_log.del_logged_timestamp(identifier=f"function-add_pd_layers-success")
            self._build_log.del_logged_timestamp(identifier=f"function-add_bt_layer-success")
            self._build_log.del_logged_timestamp(identifier=f"function-add_users-success")

    def add_addl_packages(self):
        """
        Installs additional user defined rpm packages.

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

        # Check whether extra packages are provided
        if not self.block_cfg.project.addl_pkgs:
            pretty_print.print_info(
                f"'{self.block_id} -> project -> addl_pkgs' not specified. No additional rpm packages will be installed."
            )
            return

        # Check whether the extra packages need to be added
        packages_already_added = (
            self._build_log.get_logged_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")
            != 0.0
        )
        if packages_already_added and not self._build_validator.check_rebuild_bc_config(
            keys=[["blocks", self.block_id, "project", "addl_pkgs"]]
        ):
            pretty_print.print_build("No need to install additional packages. No altered source files detected...")
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            if not self._dnf_conf_file.is_file():
                pretty_print.print_error(f"The following dnf configuration file is required: {self._dnf_conf_file}")
                sys.exit(1)

            pretty_print.print_build("Installing additional packages...")

            dnf_base_command = f"dnf -y --nodocs --verbose -c {self._dnf_conf_file} --releasever={self.block_cfg.project.release} --forcearch={self._target_arch} --installroot={self._build_dir} "
            add_packages_commands = [
                # If a QEMU binary exists, it is probably needed to run aarch64 binaries on an x86 system during build. So copy it to build_dir.
                f"if [ -e /usr/bin/qemu-aarch64-static ]; then "
                f"    mkdir -p {self._build_dir}/usr/bin && "
                f"    cp -a /usr/bin/qemu-aarch64-static {self._build_dir}/usr/bin/; "
                f"fi",
                # Update all the installed packages
                dnf_base_command + "update",
                # Installing user defined packages
                dnf_base_command + "install " + " ".join(self.block_cfg.project.addl_pkgs),
                # The QEMU binary if only required during build, so delete it if it exists
                f"rm -f {self._build_dir}/usr/bin/qemu-aarch64-static",
            ]

            # The root user is used in this container. This is necessary in order to build a RootFS image.
            self.container_executor.exec_sh_commands(
                commands=add_packages_commands,
                dirs_to_mount=[(self._resources_dir, "Z"), (self._work_dir, "Z")],
                print_commands=True,
                run_as_root=True,
                logfile=self._block_temp_dir / "install_additional_packages.log",
                output_scrolling=True,
            )

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
        if users_already_added and not self._build_validator.check_rebuild_bc_config(
            keys=[["blocks", self.block_id, "project", "users"]]
        ):
            pretty_print.print_build("No need to add users. No altered source files detected...")
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
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
                commands=add_users_commands,
                dirs_to_mount=[(self._resources_dir, "Z"), (self._work_dir, "Z")],
                print_commands=True,
                run_as_root=True,
            )

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

        if prebuilt:
            archive_name = f"almalinux{self.block_cfg.project.release}_zynqmp_pre-built"
        else:
            archive_name = self._file_system_name

        self._build_archive(archive_name=archive_name, file_extension="tar.xz", tar_compress_param="-I pxz")
