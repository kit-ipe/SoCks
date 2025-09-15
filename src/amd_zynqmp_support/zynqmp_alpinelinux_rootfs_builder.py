import sys
import pathlib
import inspect
import urllib
import shutil

import socks.pretty_print as pretty_print
from socks.build_validator import Build_Validator
from socks.file_downloader import File_Downloader
from abstract_builders.file_system_builder import File_System_Builder
from amd_zynqmp_support.zynqmp_alpinelinux_rootfs_model import ZynqMP_AlpineLinux_RootFS_Model


class ZynqMP_AlpineLinux_RootFS_Builder(File_System_Builder):
    """
    Alpine Linux root file system builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "rootfs",
        block_description: str = "Build an Alpine Linux root file system",
        model_class: type[object] = ZynqMP_AlpineLinux_RootFS_Model,
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
            "vivado": [".*.xsa"],
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
                    self.run_base_install_mod_script,
                    self.add_addl_packages,
                    self.add_addl_ext_packages,
                    self.add_users,
                    self.add_kmodules,
                    self.add_bt_layer,
                    self.add_pd_layers,
                    self.run_concluding_mod_script,
                    self.build_archive,
                    self.export_block_package,
                    self._build_validator.save_project_cfg_build,
                ]
            )
            block_cmds["prebuild"].extend(block_cmds["prepare"])
            block_cmds["prebuild"].extend(
                [
                    self.build_base_file_system,
                    self.run_base_install_mod_script,
                    self.add_addl_packages,
                    self.add_addl_ext_packages,
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
                    self.run_concluding_mod_script,
                    self.build_archive,
                    self.export_block_package,
                    self._build_validator.save_project_cfg_build,
                ]
            )
        return block_cmds

    @property
    def _file_system_name(self):
        return f"alpine_linux_{self.project_cfg.project.type.lower()}_{self.project_cfg.project.name}"

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

        # Check whether the base root file system needs to be built
        if not self._build_validator.check_rebuild_bc_config(
            keys=[["blocks", self.block_id, "project", "repositories"], ["project", "name"]]
        ):
            pretty_print.print_build(
                "No need to rebuild the base root file system. No altered source files detected..."
            )
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            self._work_dir.mkdir(parents=True, exist_ok=True)

            pretty_print.print_build("Building the base root file system...")

            repos_str = " ".join([f"--repository {url}" for url in self.block_cfg.project.repositories])
            apk_base_command = f"apk --no-interactive --arch {self._target_arch} {repos_str} --update-cache --root {self._build_dir} "
            base_rootfs_build_commands = [
                # If a QEMU binary exists, it is probably needed to run aarch64 binaries on an x86 system during build. So copy it to build_dir.
                f"if [ -e /usr/bin/qemu-aarch64-static ]; then "
                f"    mkdir -p {self._build_dir}/usr/bin && "
                f"    cp -a /usr/bin/qemu-aarch64-static {self._build_dir}/usr/bin/; "
                f"fi",
                # Install Meta package for minimal alpine base
                apk_base_command + "--initdb --allow-untrusted add alpine-base",
                # The QEMU binary if only required during build, so delete it if it exists
                f"rm -f {self._build_dir}/usr/bin/qemu-aarch64-static",
            ]

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
            self._build_log.del_logged_timestamp(identifier=f"function-run_base_install_mod_script-success")
            self._build_log.del_logged_timestamp(identifier=f"function-run_concluding_mod_script-success")
            self._build_log.del_logged_timestamp(identifier=f"function-add_pd_layers-success")
            self._build_log.del_logged_timestamp(identifier=f"function-add_bt_layer-success")
            self._build_log.del_logged_timestamp(identifier=f"function-add_users-success")

    def run_base_install_mod_script(self):
        """
        Runs a user-defined shell script to make changes to the base installation.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        repos_str = " ".join([f"--repository {url}" for url in self.block_cfg.project.repositories])
        self._run_mod_script(
            mod_script=self._resources_dir / "mod_base_install.sh",
            mod_script_params=[self._target_arch, f"\"{repos_str}\"", str(self._build_dir)],
        )

    def run_concluding_mod_script(self):
        """
        Runs a user-defined shell script to finalize the creation of the file system.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        repos_str = " ".join([f"--repository {url}" for url in self.block_cfg.project.repositories])
        self._run_mod_script(
            mod_script=self._resources_dir / "conclude_install.sh",
            mod_script_params=[self._target_arch, f"\"{repos_str}\"", str(self._build_dir)],
        )

    def add_addl_packages(self):
        """
        Installs additional user defined apk packages.

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
                f"'{self.block_id} -> project -> addl_pkgs' not specified. No additional apk packages will be installed."
            )
            return

        # Check whether the extra packages need to be added
        packages_already_added = (
            self._build_log.get_logged_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")
            != 0.0
        )
        if packages_already_added and not self._build_validator.check_rebuild_bc_config(
            keys=[["blocks", self.block_id, "project", "addl_pkgs"], ["blocks", self.block_id, "project", "repositories"]]
        ):
            pretty_print.print_build("No need to install additional packages. No altered source files detected...")
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            pretty_print.print_build("Installing additional packages...")

            repos_str = " ".join([f"--repository {url}" for url in self.block_cfg.project.repositories])
            apk_base_command = f"apk --no-interactive --arch {self._target_arch} {repos_str} --update-cache --root {self._build_dir} "
            add_packages_commands = [
                # If a QEMU binary exists, it is probably needed to run aarch64 binaries on an x86 system during build. So copy it to build_dir.
                f"if [ -e /usr/bin/qemu-aarch64-static ]; then "
                f"    mkdir -p {self._build_dir}/usr/bin && "
                f"    cp -a /usr/bin/qemu-aarch64-static {self._build_dir}/usr/bin/; "
                f"fi",
                # Update all the installed packages
                apk_base_command + "upgrade",
                # Installing user defined packages
                apk_base_command + "add " + " ".join(self.block_cfg.project.addl_pkgs),
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

    def add_addl_ext_packages(self):
        """
        Installs additional user defined apk packages from external *.apk files.

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
        if not self.block_cfg.project.addl_ext_pkgs:
            pretty_print.print_info(
                f"'{self.block_id} -> project -> addl_ext_pkgs' not specified. "
                "No additional apk packages will be installed from external *.apk files."
            )
            return

        # Check whether the extra packages need to be added
        packages_already_added = (
            self._build_log.get_logged_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")
            != 0.0
        )
        if packages_already_added and not self._build_validator.check_rebuild_bc_config(
            keys=[["blocks", self.block_id, "project", "addl_ext_pkgs"], ["blocks", self.block_id, "project", "repositories"]]
        ):
            pretty_print.print_build(
                "No need to install additional packages from external *.apk files. No altered source files detected..."
            )
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            pretty_print.print_build("Installing additional packages from external *.apk files...")

            # Clean package directory
            ext_pkgs_dir = self._work_dir / "external_packages"
            shutil.rmtree(path=ext_pkgs_dir, ignore_errors=True)
            ext_pkgs_dir.mkdir(parents=True)

            # Collect package files
            ext_pkgs_to_install = []
            for uri in self.block_cfg.project.addl_ext_pkgs:
                if uri.rpartition(".")[2] != "apk":
                    # The provided file is not an apk package
                    pretty_print.print_error(
                        f"The file specified in '{uri}' in '{self.block_id} -> project -> addl_ext_pkgs' is not an apk package"
                    )
                    sys.exit(1)
                if urllib.parse.urlparse(uri).scheme == "file":
                    # This package is provided locally
                    local_pkg_path = pathlib.Path(urllib.parse.urlparse(uri).path)
                    local_pkg_file = local_pkg_path.name
                    # Check whether the specified file exists
                    if not local_pkg_path.is_file():
                        pretty_print.print_error(
                            f"The package specified in '{self.block_id} -> project -> addl_ext_pkgs' does not exist: '{local_pkg_path}'"
                        )
                        sys.exit(1)
                    # Copy file to work dir
                    shutil.copy(local_pkg_path, ext_pkgs_dir / local_pkg_file)
                elif urllib.parse.urlparse(uri).scheme in ["http", "https"]:
                    # This package needs to be downloaded
                    local_pkg_path = File_Downloader.get_file(url=uri, output_dir=ext_pkgs_dir)
                    local_pkg_file = local_pkg_path.name
                else:
                    raise ValueError(
                        "The following string is not a valid reference to an apk package file: "
                        f"{uri}. Only URI schemes 'https', 'http', and 'file' are supported."
                    )

                # Append file to list of packages
                ext_pkgs_to_install.append(local_pkg_file)

            rel_pkg_paths = ["./" + pkg for pkg in ext_pkgs_to_install]
            repos_str = " ".join([f"--repository {url}" for url in self.block_cfg.project.repositories])
            apk_base_command = f"apk --no-interactive --arch {self._target_arch} {repos_str} --update-cache --root {self._build_dir} "
            add_packages_commands = [
                # If a QEMU binary exists, it is probably needed to run aarch64 binaries on an x86 system during build. So copy it to build_dir.
                f"if [ -e /usr/bin/qemu-aarch64-static ]; then "
                f"    mkdir -p {self._build_dir}/usr/bin && "
                f"    cp -a /usr/bin/qemu-aarch64-static {self._build_dir}/usr/bin/; "
                f"fi",
                # Update all the installed packages
                apk_base_command + "upgrade",
                # Movo to directory with local packages
                f"cd {ext_pkgs_dir}",
                # Installing user defined external packages
                apk_base_command + "add --allow-untrusted " + " ".join(rel_pkg_paths),
                # Movo back to the previous directory
                "cd -",
                # The QEMU binary if only required during build, so delete it if it exists
                f"rm -f {self._build_dir}/usr/bin/qemu-aarch64-static",
            ]

            # The root user is used in this container. This is necessary in order to build a RootFS image.
            self.container_executor.exec_sh_commands(
                commands=add_packages_commands,
                dirs_to_mount=[(self._resources_dir, "Z"), (self._work_dir, "Z")],
                print_commands=True,
                run_as_root=True,
                logfile=self._block_temp_dir / "install_additional_external_packages.log",
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

            # Collect SSH keys
            ssh_keys_temp_dir = self._work_dir / "ssh_keys_temp"
            for user in self.block_cfg.project.users:
                if user.ssh_key:
                    ssh_key_src_file = pathlib.Path("~/.ssh").expanduser() / user.ssh_key
                    # Check if the key exists on the host system
                    if not ssh_key_src_file.is_file():
                        pretty_print.print_error(
                            f"The ssh key '{user.ssh_key}' does not exist in '{ssh_key_src_file.parent}'"
                        )
                        sys.exit(1)

                    # Make SSH key from the host system available in the container
                    if not (ssh_keys_temp_dir / user.ssh_key).is_file():
                        ssh_keys_temp_dir.mkdir(exist_ok=True)
                        shutil.copy(ssh_key_src_file, ssh_keys_temp_dir / user.ssh_key)

            add_users_commands = [
                # If a QEMU binary exists, it is probably needed to run aarch64 binaries on an x86 system during build. So copy it to build_dir.
                f"if [ -e /usr/bin/qemu-aarch64-static ]; then "
                f"    mkdir -p {self._build_dir}/usr/bin && "
                f"    cp -a /usr/bin/qemu-aarch64-static {self._build_dir}/usr/bin/; "
                f"fi; "
                # Make SSH keys from the host system available in the chroot environment
                f"if [ -e {ssh_keys_temp_dir} ]; then "
                f"    rm -rf {self._build_dir}/tmp/{ssh_keys_temp_dir.parts[-1]}; "
                f"    mv {ssh_keys_temp_dir} {self._build_dir}/tmp/; "
                f"fi"
            ]

            for user in self.block_cfg.project.users:
                add_user_str = ""
                if user.name != "root":
                    add_user_str = (
                        add_user_str + f"if id {user.name} &>/dev/null; then deluser --remove-home {user.name}; fi && "
                    )  # Delete user account if it already exists
                    add_user_str = add_user_str + f"adduser -D {user.name} && "
                for group in user.groups:
                    add_user_str = add_user_str + f"addgroup {user.name} {group} && "
                # Escape all $ symbols in the hash. I know this is ugly, but this is the only way I have found
                # to make it work through all the layers of Python, docker, sh and chroot.
                escaped_pw_hash = user.pw_hash.replace("$", "\\\\\\$")
                add_user_str = add_user_str + f"echo \"{user.name}:{escaped_pw_hash}\" | chpasswd -e && "
                if user.ssh_key:
                    add_user_str = (
                        add_user_str + f"HOME_OF_{user.name.upper()}=\$(getent passwd {user.name} | cut -d: -f6) && "
                    )  # Get user home directory in chroot environment
                    add_user_str = add_user_str + f"mkdir -p \${{HOME_OF_{user.name.upper()}}}/.ssh && "
                    add_user_str = (
                        add_user_str
                        + f"cat /tmp/{ssh_keys_temp_dir.parts[-1]}/{user.ssh_key} >> \${{HOME_OF_{user.name.upper()}}}/.ssh/authorized_keys && "
                    )
                # The string should not end with &&
                add_user_str = add_user_str.rstrip(" && ")

                # Execute command string in chroot environment
                add_users_commands.append(f'chroot {self._build_dir} /bin/sh -c "{add_user_str}"')

            # Delete temporary directory with SSH keys
            add_users_commands.append(f"rm -rf {self._build_dir}/tmp/{ssh_keys_temp_dir.parts[-1]}")

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
            archive_name = f"{self._file_system_name}_pre-built"
        else:
            archive_name = self._file_system_name

        self._build_archive(archive_name=archive_name, file_extension="tar.xz", tar_compress_param="-I pixz")
