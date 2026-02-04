import sys
import pathlib
import inspect
import urllib
import shutil

import socks.pretty_print as pretty_print
from socks.build_validator import Build_Validator
from socks.file_downloader import File_Downloader
from abstract_builders.file_system_builder import File_System_Builder


class Debian_RootFS_Builder(File_System_Builder):
    """
    Debian root file system builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        model_class: type[object],
        block_id: str = "rootfs",
        block_description: str = "Build a Debian root file system",
    ):

        super().__init__(
            project_cfg=project_cfg,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
            model_class=model_class,
        )

        self._target_arch = "arm64"

        # Project directories
        self.custom_pkg_src_dir = self._resources_dir / "package_src_trees"
        self.custom_pkg_build_dir = self._work_dir / "custom_packages"

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
        block_cmds = {"prepare": [], "build": [], "prebuild": [], "build-pkgs": [], "clean": [], "start-container": []}
        block_cmds["prepare"].extend(
            [
                self._build_validator.del_project_cfg,
                self.container_executor.build_container_image,
                self.import_dependencies,
                self.container_executor.enable_multiarch,
                self._build_validator.save_project_cfg_prepare,
            ]
        )
        block_cmds["build-pkgs"].extend(block_cmds["prepare"])
        block_cmds["build-pkgs"].extend(
            [
                self.build_custom_packages,
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
                    self.build_custom_packages,
                    self.add_custom_packages,
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
                    self.build_custom_packages,
                    self.add_custom_packages,
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
        return f"debian_{self.block_cfg.project.release}_{self.project_cfg.project.type.lower()}_{self.project_cfg.project.name}"

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
            keys=[
                ["blocks", self.block_id, "project", "release"],
                ["blocks", self.block_id, "project", "mirror"],
                ["project", "name"],
            ]
        ):
            pretty_print.print_build(
                "No need to rebuild the base root file system. No altered source files detected..."
            )
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            self.clean_work()
            self._work_dir.mkdir(parents=True, exist_ok=True)

            pretty_print.print_build("Building the base root file system...")

            base_rootfs_build_commands = [
                # If a QEMU binary exists, it is probably needed to run aarch64 binaries on an x86 system during build. So copy it to build_dir.
                f"if [ -e /usr/bin/qemu-aarch64-static ]; then "
                f"    mkdir -p {self._build_dir}/usr/bin && "
                f"    cp -a /usr/bin/qemu-aarch64-static {self._build_dir}/usr/bin/; "
                f"fi",
                'printf "\nInstall the base os via debootstrap...\n\n"',
                # The 'Minimal Install' group consists of the 'Core' group and optionally the 'Standard' and 'Guest Agents' groups
                f"debootstrap --arch={self._target_arch} {self.block_cfg.project.release} {self._build_dir} {self.block_cfg.project.mirror}",
                # The QEMU binary is only required during build, so delete it if it exists
                f"rm -f {self._build_dir}/usr/bin/qemu-aarch64-static",
            ]

            # The root user is used in this container. This is necessary in order to build a RootFS image.
            self.container_executor.exec_sh_commands(
                commands=base_rootfs_build_commands,
                dirs_to_mount=[(self._resources_dir, "Z"), (self._work_dir, "Z")],
                custom_params=(
                    ["--cap-add=SYS_ADMIN"] if self.project_cfg.external_tools.container_tool == "podman" else []
                ),  # Not sure why podman needs the SYS_ADMIN capability, but without it, debootstrap complains that the file system would be mounted with the 'noexec' option
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

        self._run_mod_script(
            mod_script=self._resources_dir / "mod_base_install.sh",
            mod_script_params=[self._target_arch, self.block_cfg.project.release, str(self._build_dir)],
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

        self._run_mod_script(
            mod_script=self._resources_dir / "conclude_install.sh",
            mod_script_params=[self._target_arch, self.block_cfg.project.release, str(self._build_dir)],
        )

    def build_custom_packages(self):
        """
        Builds custom packages. These packages typically use files generated by other blocks.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check whether custom packages are defined
        if not self.block_cfg.project.custom_pkgs:
            pretty_print.print_info(
                f"'{self.block_id} -> project -> custom_pkgs' not specified. No custom packages will be built."
            )
            return

        # Check whether the custom packages need to be built
        custom_pkgs_already_built = (
            self._build_log.get_logged_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")
            != 0.0
        )
        if (
            custom_pkgs_already_built
            and not Build_Validator.check_rebuild_bc_timestamp(
                src_search_list=[self.custom_pkg_src_dir, self._dependencies_dir],
                out_timestamp=self._build_log.get_logged_timestamp(
                    identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
                ),
            )
            and not self._build_validator.check_rebuild_bc_config(
                keys=[["blocks", self.block_id, "project", "custom_pkgs"]]
            )
        ):
            pretty_print.print_build("No need to build custom packages. No altered source files detected...")
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            # Clean package build directories. This is done in the container, as root privileges are required.
            self.container_executor.exec_sh_commands(
                commands=[f"rm -rf {self.custom_pkg_build_dir} 2> /dev/null || true"],
                dirs_to_mount=[(self._work_dir, "Z")],
                print_commands=True,
                run_as_root=True,
            )

            pretty_print.print_build("Building custom packages...")

            # Copy package source trees to work directory
            self._work_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(self.custom_pkg_src_dir, self.custom_pkg_build_dir)

            build_packages_commands = [
                # If a QEMU binary exists, it is probably needed to run aarch64 binaries on an x86 system during build. So copy it to build_dir.
                f"if [ -e /usr/bin/qemu-aarch64-static ]; then "
                f"    mkdir -p {self._build_dir}/usr/bin && "
                f"    cp -a /usr/bin/qemu-aarch64-static {self._build_dir}/usr/bin/; "
                f"fi",
                # Root should own everything that was copied from the source trees and ends up in the packages
                f"chown -R root:root {self.custom_pkg_build_dir}",
            ]

            # Iterate over all packages and accumulate build commands
            for package in self.block_cfg.project.custom_pkgs:
                pkg_src_tree = self.custom_pkg_src_dir / package.name
                pkg_build_dir = self.custom_pkg_build_dir / package.name

                if not pkg_src_tree.is_dir():
                    pretty_print.print_error(
                        f"No subdirectory for package '{package.name}' in '{self.custom_pkg_src_dir}'"
                    )
                    sys.exit(1)

                if not (pkg_src_tree / "DEBIAN/control").is_file():
                    pretty_print.print_error(
                        f"No 'control' file for package '{package.name}' in '{pkg_src_tree / 'DEBIAN'}'"
                    )
                    sys.exit(1)

                # Iterate over all items from other blocks that are to be included in this package
                for item in package.build_time_files:
                    if item.src_block not in self._block_deps.keys():
                        pretty_print.print_error(
                            f"Source block '{item.src_block}' specified in '{self.block_id} -> project -> "
                            f"custom_pkgs (name: {package.name}) -> build_time_files' is invalid."
                        )
                        sys.exit(1)
                    srcs = (self._dependencies_dir / item.src_block).glob(item.src_name)
                    if not srcs:
                        pretty_print.print_error(
                            f"Source item '{item.src_name}' specified in '{self.block_id} -> project -> "
                            f"custom_pkgs (name: {package.name}) -> build_time_files (src_block: {item.src_block})' "
                            f"could not be found in the block package of source block '{item.src_block}'."
                        )
                        sys.exit(1)
                    build_packages_commands.append(f"mkdir -p {pkg_build_dir}/{item.dest_path}")
                    for src in srcs:
                        build_packages_commands.append(f"cp -r {src} {pkg_build_dir}/{item.dest_path}/{item.dest_name}")
                        if item.dest_owner_group:
                            build_packages_commands.append(
                                f"chown -R {item.dest_owner_group} {pkg_build_dir}/{item.dest_path}/{item.dest_name}"
                            )
                        if item.dest_permissions:
                            build_packages_commands.append(
                                f"chmod -R {item.dest_permissions} {pkg_build_dir}/{item.dest_path}/{item.dest_name}"
                            )

                # Build the package
                build_packages_commands.append(f"dpkg-deb --build {pkg_build_dir}")

            # The QEMU binary is only required during build, so delete it if it exists
            build_packages_commands.append(f"rm -f {self._build_dir}/usr/bin/qemu-aarch64-static")

            # The root user is used in this container. This is necessary in order to build a RootFS image.
            self.container_executor.exec_sh_commands(
                commands=build_packages_commands,
                dirs_to_mount=[(self._dependencies_dir, "Z"), (self._work_dir, "Z")],
                print_commands=True,
                run_as_root=True,
                logfile=self._block_temp_dir / "build_custom_packages.log",
                output_scrolling=True,
            )

    def add_addl_packages(self):
        """
        Installs additional user defined deb packages.

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
                "No additional deb packages will be installed. "
                f"'{self.block_id} -> project -> addl_pkgs' not specified."
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
            pretty_print.print_build("Installing additional packages...")

            addl_pkgs_str = f"apt update && apt install -y " + " ".join(self.block_cfg.project.addl_pkgs)
            add_packages_commands = [
                # If a QEMU binary exists, it is probably needed to run aarch64 binaries on an x86 system during build. So copy it to build_dir.
                f"if [ -e /usr/bin/qemu-aarch64-static ]; then "
                f"    mkdir -p {self._build_dir}/usr/bin && "
                f"    cp -a /usr/bin/qemu-aarch64-static {self._build_dir}/usr/bin/; "
                f"fi",
                # Installing user defined packages
                f'chroot {self._build_dir} /bin/bash -c "{addl_pkgs_str}"',
                # The QEMU binary is only required during build, so delete it if it exists
                f"rm -f {self._build_dir}/usr/bin/qemu-aarch64-static",
            ]

            # The root user is used in this container. This is necessary in order to build a RootFS image.
            self.container_executor.exec_sh_commands(
                commands=add_packages_commands,
                dirs_to_mount=[(self._work_dir, "Z")],
                print_commands=True,
                run_as_root=True,
                logfile=self._block_temp_dir / "install_additional_packages.log",
                output_scrolling=True,
            )

    def add_addl_ext_packages(self):
        """
        Installs additional user defined deb packages from external *.deb files.

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
                "No additional deb packages will be installed from external *.deb files. "
                f"'{self.block_id} -> project -> addl_ext_pkgs' not specified."
            )
            return

        # Create a list of local packages and a list of last modified timestamps of online packages
        # ToDo: This entire collection process of packages should potentially be merged with the collection process when the packages are actually installed.
        local_pkgs = []
        online_pkg_timestamps = []
        for uri in self.block_cfg.project.addl_ext_pkgs:
            if urllib.parse.urlparse(uri).scheme == "file":
                # This package is provided locally
                local_pkg_path = pathlib.Path(urllib.parse.urlparse(uri).path)
                # Append file to list of local packages
                local_pkgs.append(local_pkg_path)
            elif urllib.parse.urlparse(uri).scheme in ["http", "https"]:
                # This package is provided online
                try:
                    online_pkg_timestamps.append(File_Downloader.get_last_modified(url=uri))
                except RuntimeError:
                    pretty_print.print_warning(
                        "Updates to the following package cannot be detected because no 'Last-Modified' field "
                        "could be retrieved from the header. Use a different server or trigger rebuilds "
                        f"manually: {uri}"
                    )

        # Check whether a rebuild is necessary due to updated local packages
        rebuild_bc_local_pkgs = False
        if local_pkgs:
            rebuild_bc_local_pkgs = Build_Validator.check_rebuild_bc_timestamp(
                src_search_list=local_pkgs,
                out_timestamp=self._build_log.get_logged_timestamp(
                    identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
                ),
            )

        # Check whether a rebuild is necessary due to updated online packages
        rebuild_bc_online_pkgs = False
        if online_pkg_timestamps:
            rebuild_bc_online_pkgs = max(online_pkg_timestamps) > self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            )

        # Check whether the extra packages need to be added
        packages_already_added = (
            self._build_log.get_logged_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")
            != 0.0
        )
        if (
            packages_already_added
            and not rebuild_bc_local_pkgs
            and not rebuild_bc_online_pkgs
            and not self._build_validator.check_rebuild_bc_config(
                keys=[["blocks", self.block_id, "project", "addl_ext_pkgs"]]
            )
        ):
            pretty_print.print_build(
                "No need to install additional packages from external *.deb files. No altered source files detected..."
            )
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            pretty_print.print_build("Installing additional packages from external *.deb files...")

            # Clean package directory
            ext_pkgs_dir = self._work_dir / "external_packages"
            shutil.rmtree(path=ext_pkgs_dir, ignore_errors=True)
            ext_pkgs_dir.mkdir(parents=True)

            # Collect package files
            ext_pkgs_to_install = []
            for uri in self.block_cfg.project.addl_ext_pkgs:
                if uri.rpartition(".")[2] != "deb":
                    # The provided file is not a Debian package
                    pretty_print.print_error(
                        f"The file specified in '{uri}' in '{self.block_id} -> project -> addl_ext_pkgs' is not a Debian package"
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
                        "The following string is not a valid reference to a Debian package file: "
                        f"{uri}. Only URI schemes 'https', 'http', and 'file' are supported."
                    )

                # Append file to list of packages
                ext_pkgs_to_install.append(local_pkg_file)

            rel_pkg_paths = ["./" + pkg for pkg in ext_pkgs_to_install]
            addl_pkgs_str = f"apt update && cd /tmp/{ext_pkgs_dir.stem} && apt install --reinstall -y " + " ".join(
                rel_pkg_paths
            )
            add_packages_commands = [
                # If a QEMU binary exists, it is probably needed to run aarch64 binaries on an x86 system during build. So copy it to build_dir.
                f"if [ -e /usr/bin/qemu-aarch64-static ]; then "
                f"    mkdir -p {self._build_dir}/usr/bin && "
                f"    cp -a /usr/bin/qemu-aarch64-static {self._build_dir}/usr/bin/; "
                f"fi",
                # Move external packages to the build dircetory to make them available in chroot
                f"rm -rf {self._build_dir}/tmp/{ext_pkgs_dir.stem}",
                f"mv {ext_pkgs_dir} {self._build_dir}/tmp/",
                # Installing user defined external packages
                f'chroot {self._build_dir} /bin/bash -c "{addl_pkgs_str}"',
                # Remove external packages from tmp dir
                f"rm -rf {self._build_dir}/tmp/{ext_pkgs_dir.stem}",
                # The QEMU binary is only required during build, so delete it if it exists
                f"rm -f {self._build_dir}/usr/bin/qemu-aarch64-static",
            ]

            # The root user is used in this container. This is necessary in order to build a RootFS image.
            self.container_executor.exec_sh_commands(
                commands=add_packages_commands,
                dirs_to_mount=[(self._work_dir, "Z")],
                print_commands=True,
                run_as_root=True,
                logfile=self._block_temp_dir / "install_additional_external_packages.log",
                output_scrolling=True,
            )

    def add_custom_packages(self):
        """
        Installs custom packages that have been built by this block.

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

        # Check whether custom packages are defined
        if not self.block_cfg.project.custom_pkgs:
            pretty_print.print_info(
                "No custom packages will be installed. " f"'{self.block_id} -> project -> custom_pkgs' not specified."
            )
            return

        # Compile list of packages to be installed
        custom_pkgs_to_install = []
        for package in self.block_cfg.project.custom_pkgs:
            if package.install:
                custom_pkgs_to_install.append(f"{package.name}.deb")

        if not custom_pkgs_to_install:
            pretty_print.print_info(
                "No custom packages will be installed. "
                f"No package in '{self.block_id} -> project -> custom_pkgs' marked for installation."
            )
            return

        # Check whether the custom packages need to be added
        packages_already_added = (
            self._build_log.get_logged_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")
            != 0.0
        )
        if (
            packages_already_added
            and not Build_Validator.check_rebuild_bc_timestamp(
                src_search_list=[self.custom_pkg_build_dir],
                out_timestamp=self._build_log.get_logged_timestamp(
                    identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
                ),
            )
            and not self._build_validator.check_rebuild_bc_config(
                keys=[["blocks", self.block_id, "project", "custom_pkgs"]]
            )
        ):
            pretty_print.print_build("No need to install custom packages. No altered source files detected...")
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            pretty_print.print_build("Installing custom packages...")

            # Check whether all packages are available
            for package in custom_pkgs_to_install:
                if not (self.custom_pkg_build_dir / package).is_file():
                    pretty_print.print_error(
                        f"Package '{package}' is to be installed, but it is not available in '{self.custom_pkg_build_dir}'"
                    )
                    sys.exit(1)

            rel_pkg_paths = ["./" + pkg for pkg in custom_pkgs_to_install]
            addl_pkgs_str = f"apt update && cd /tmp/custom_packages && apt install --reinstall -y " + " ".join(
                rel_pkg_paths
            )
            add_packages_commands = [
                # If a QEMU binary exists, it is probably needed to run aarch64 binaries on an x86 system during build. So copy it to build_dir.
                f"if [ -e /usr/bin/qemu-aarch64-static ]; then "
                f"    mkdir -p {self._build_dir}/usr/bin && "
                f"    cp -a /usr/bin/qemu-aarch64-static {self._build_dir}/usr/bin/; "
                f"fi",
                # Move custom packages to the build directory to make them available in chroot
                f"rm -rf {self._build_dir}/tmp/custom_packages",
                f"mkdir -p {self._build_dir}/tmp/custom_packages",
                f"cp {self.custom_pkg_build_dir}/*.deb {self._build_dir}/tmp/custom_packages/",
                # Installing user defined custom packages
                f'chroot {self._build_dir} /bin/bash -c "{addl_pkgs_str}"',
                # Remove custom packages from tmp dir
                f"rm -rf {self._build_dir}/tmp/custom_packages",
                # The QEMU binary is only required during build, so delete it if it exists
                f"rm -f {self._build_dir}/usr/bin/qemu-aarch64-static",
            ]

            # The root user is used in this container. This is necessary in order to build a RootFS image.
            self.container_executor.exec_sh_commands(
                commands=add_packages_commands,
                dirs_to_mount=[(self._work_dir, "Z")],
                print_commands=True,
                run_as_root=True,
                logfile=self._block_temp_dir / "install_custom_packages.log",
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
                        add_user_str + f"if id {user.name} &>/dev/null; then userdel -r {user.name}; fi && "
                    )  # Delete user account if it already exists
                    add_user_str = add_user_str + f"useradd -s /bin/bash -m {user.name} && "
                for group in user.groups:
                    add_user_str = add_user_str + f"usermod -a -G {group} {user.name} && "
                # Escape all $ symbols in the hash. I know this is ugly, but this is the only way I have found
                # to make it work through all the layers of Python, docker, sh and chroot.
                escaped_pw_hash = user.pw_hash.replace("$", "\\\\\\$")
                add_user_str = add_user_str + f"usermod -p {escaped_pw_hash} {user.name} && "
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
                add_users_commands.append(f'chroot {self._build_dir} /bin/bash -c "{add_user_str}"')

            # Delete temporary directory with SSH keys
            add_users_commands.append(f"rm -rf {self._build_dir}/tmp/{ssh_keys_temp_dir.parts[-1]}")

            # The QEMU binary is only required during build, so delete it if it exists
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
