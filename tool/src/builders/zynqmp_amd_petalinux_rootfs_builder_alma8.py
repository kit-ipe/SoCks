import sys
import pathlib
import shutil
import hashlib
import tarfile
import stat
import urllib
import validators

import socks.pretty_print as pretty_print
from socks.shell_command_runners import Shell_Command_Runners
from builders.builder import Builder
from builders.zynqmp_amd_petalinux_rootfs_model import ZynqMP_AMD_PetaLinux_RootFS_Model


class ZynqMP_AMD_PetaLinux_RootFS_Builder_Alma8(Builder):
    """
    AMD PetaLinux root file system builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        project_cfg_files: list,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "rootfs",
        block_description: str = "Build an AMD PetaLinux root file system",
    ):

        super().__init__(
            project_cfg=project_cfg,
            project_cfg_files=project_cfg_files,
            model_class=ZynqMP_AMD_PetaLinux_RootFS_Model,
            socks_dir=socks_dir,
            project_dir=project_dir,
            block_id=block_id,
            block_description=block_description,
        )

        # Find project sources for this block
        self._set_single_prj_src()

        self._rootfs_name = f"petalinux_zynqmp_{self.project_cfg.project.name}"

        # Project directories
        self._mod_dir = self._work_dir / self._rootfs_name
        if self._local_source_dir is not None:
            # Local project sources are used for this block
            self._repo_dir = self._local_source_dir
            self._source_repo_dir = self._local_source_dir
        elif self._source_repo is not None:
            # Online project sources are used for this block
            self._source_repo_dir = (
                self._repo_dir
                / f"{pathlib.Path(urllib.parse.urlparse(url=self._source_repo['url']).path).stem}-{self._source_repo['branch']}"
            )
        else:
            raise ValueError(f"No project source for block '{self.block_id}'")

        # Project files
        # File for version & build info tracking
        self._build_info_file = self._work_dir / "fs_build_info"
        # File for saving the checksum of the Kernel module archive used
        self._source_kmods_md5_file = self._work_dir / "source_kmodules.md5"
        # Repo tool
        self._repo_script = self._repo_dir / "repo"

        # Products of other blocks on which this block depends
        # This dict is used to check whether the imported block packages contain
        # all the required files. Regex can be used to describe the expected files.
        # Optional dependencies can also be listed here. They will be ignored if
        # they are not listed in the project configuration.
        self._block_deps = {"kernel": ["kernel_modules.tar.gz"]}

        # The user can use block commands to interact with the block.
        # Each command represents a list of member functions of the builder class.
        self.block_cmds = {
            "prepare": [],
            "build": [],
            "prebuild": [],
            "clean": [],
            "create-patches": [],
            "start-container": [],
        }
        self.block_cmds["prepare"].extend([self.build_container_image, self.import_dependencies])
        self.block_cmds["clean"].extend(
            [
                self.build_container_image,
                self.clean_download,
                self.clean_work,
                self.clean_repo,
                self.clean_dependencies,
                self.clean_output,
                self.clean_block_temp,
            ]
        )
        if self.block_cfg.source == "build":
            self.block_cmds["prepare"].extend([self.init_repo, self.apply_patches, self.yocto_init])
            self.block_cmds["build"].extend(self.block_cmds["prepare"])
            self.block_cmds["build"].extend(
                [self.build_base_rootfs, self.add_kmodules, self.build_archive, self.export_block_package]
            )
            self.block_cmds["prebuild"].extend(self.block_cmds["prepare"])
            self.block_cmds["prebuild"].extend(
                [self.build_base_rootfs, self.build_archive_prebuilt, self.export_block_package]
            )
            self.block_cmds["create-patches"].extend([self.create_patches])
            self.block_cmds["start-container"].extend([self.build_container_image, self.start_container])
        elif self.block_cfg.source == "import":
            self.block_cmds["build"].extend(self.block_cmds["prepare"])
            self.block_cmds["build"].extend(
                [self.import_prebuilt, self.add_kmodules, self.build_archive, self.export_block_package]
            )

    def init_repo(self):
        """
        Clones and initializes the yocto environment utilizing the Google 'repo'
        script as suggested by AMD.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Skip all operations if the repo already exists
        if self._source_repo_dir.exists():
            pretty_print.print_build("No need to initialize the local repos...")
            return

        self._source_repo_dir.mkdir(parents=True, exist_ok=True)

        pretty_print.print_build("Initializing local repos...")

        # Download the google repo tool
        urllib.request.urlretrieve(
            url="https://storage.googleapis.com/git-repo-downloads/repo", filename=self._repo_script
        )
        # Make repo executable
        self._repo_script.chmod(self._repo_script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        # Initialize repo in the current directory
        Shell_Command_Runners.run_sh_command(
            [
                "printf",
                '"y"',
                "|",
                str(self._repo_script),
                "init",
                "-u",
                self._source_repo["url"],
                "-b",
                self._source_repo["branch"],
            ],
            cwd=self._source_repo_dir,
        )
        # Clone git repos
        Shell_Command_Runners.run_sh_command([str(self._repo_script), "sync"], cwd=self._source_repo_dir)
        # Initialize local branches in all repos
        results = Shell_Command_Runners.get_sh_results([str(self._repo_script), "list"], cwd=self._source_repo_dir)
        for line in results.stdout.splitlines():
            path, colon, project = line.split(" ", 2)
            # Create new branch self._git_local_ref_branch. This branch is used as a reference where all existing patches are applied to the git sources
            Shell_Command_Runners.run_sh_command(
                [str(self._repo_script), "start", self._git_local_ref_branch, project], cwd=self._source_repo_dir
            )
            # Create new branch self._git_local_dev_branch. This branch is used as the local development branch. New patches can be created from this branch.
            Shell_Command_Runners.run_sh_command(
                [str(self._repo_script), "start", self._git_local_dev_branch, project], cwd=self._source_repo_dir
            )

    def create_patches(self):
        """
        Creates patches from commits on self._git_local_dev_branch.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        pretty_print.print_build("Creating patches...")

        # Iterate over all repos and check for new commits
        repos_with_commits = []
        results = Shell_Command_Runners.get_sh_results([str(self._repo_script), "list"], cwd=self._source_repo_dir)
        for line in results.stdout.splitlines():
            path, colon, project = line.split(" ", 2)
            # Check if this repo contains new commits
            result_new_commits = Shell_Command_Runners.get_sh_results(
                [
                    "git",
                    "-C",
                    str(self._source_repo_dir / path),
                    "log",
                    "--cherry-pick",
                    "--oneline",
                    self._git_local_dev_branch,
                    f"^{self._git_local_ref_branch}",
                ]
            )
            if result_new_commits.stdout:
                # This repo contains one or more new commits
                repos_with_commits.append(project)
                # Create patches
                result_new_patches = Shell_Command_Runners.get_sh_results(
                    [
                        "git",
                        "-C",
                        str(self._source_repo_dir / path),
                        "format-patch",
                        "--output-directory",
                        str(self._patch_dir),
                        self._git_local_ref_branch,
                    ]
                )
                # Add newly created patches to self._patch_list_file
                for line in result_new_patches.stdout.splitlines():
                    new_patch = line.rpartition("/")[2]
                    print(f"Patch {new_patch} was created")
                    with self._patch_list_file.open("a") as f:
                        print(f"{project} {new_patch}", file=f, end="\n")
                # Synchronize the branches ref and dev to be able to detect new commits in the future
                Shell_Command_Runners.run_sh_command(
                    ["git", "-C", str(self._source_repo_dir / path), "checkout", self._git_local_ref_branch],
                    visible_lines=0,
                )
                Shell_Command_Runners.run_sh_command(
                    ["git", "-C", str(self._source_repo_dir / path), "merge", self._git_local_dev_branch],
                    visible_lines=0,
                )
                Shell_Command_Runners.run_sh_command(
                    ["git", "-C", str(self._source_repo_dir / path), "checkout", self._git_local_dev_branch],
                    visible_lines=0,
                )

        if not repos_with_commits:
            pretty_print.print_warning("No commits found that can be used as sources for patches.")

    def apply_patches(self):
        """
        This function iterates over all patches listed in self._patch_list_file and
        applies them.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Skip all operations if the patches have already been applied
        if self._patches_applied_flag.exists():
            pretty_print.print_build("No need to apply patches...")
            return

        pretty_print.print_build("Applying patches...")

        if self._patch_list_file.is_file():
            with self._patch_list_file.open("r") as f:
                for line in f:
                    if line:  # If this line in the file is not empty
                        project, patch = line.split(" ", 1)
                        # Get path of this project
                        results = Shell_Command_Runners.get_sh_results(
                            [str(self._repo_script), "list", "-r", project, "-p"], cwd=self._source_repo_dir
                        )
                        path = results.stdout.splitlines()[0]
                        # Apply patch
                        Shell_Command_Runners.run_sh_command(
                            ["git", "-C", str(self._source_repo_dir / path), "am", str(self._patch_dir / patch)]
                        )

                        # Update the branch self._git_local_ref_branch so that it contains the applied patch and is in sync with self._git_local_dev_branch. This is important to be able to create new patches.
                        Shell_Command_Runners.run_sh_command(
                            [str(self._repo_script), "checkout", self._git_local_ref_branch, project],
                            cwd=self._source_repo_dir,
                            visible_lines=0,
                        )
                        Shell_Command_Runners.run_sh_command(
                            ["git", "-C", str(self._source_repo_dir / path), "merge", self._git_local_dev_branch],
                            visible_lines=0,
                        )
                        Shell_Command_Runners.run_sh_command(
                            [str(self._repo_script), "checkout", self._git_local_dev_branch, project],
                            cwd=self._source_repo_dir,
                            visible_lines=0,
                        )

        # Create the flag if it doesn't exist and update the timestamps
        self._patches_applied_flag.touch()

    def yocto_init(self):
        """
        Initializes the yocto project.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Skip all operations if the yocto project is already initialized
        if (self._source_repo_dir / "build").exists():
            pretty_print.print_build("No need to initialize yocto...")
            return

        local_conf_append = self._block_src_dir / "src" / "local.conf.append"

        pretty_print.print_build("Initializing yocto...")

        yocto_init_commands = (
            f"'cd {self._source_repo_dir} && "
            f"source ./setupsdk && "
            f"cat {local_conf_append} >> {self._source_repo_dir}/build/conf/local.conf'"
        )

        self.run_containerizable_sh_command(
            command=yocto_init_commands, dirs_to_mount=[(self._repo_dir, "Z"), (self._block_src_dir, "Z")]
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
        if not ZynqMP_AMD_PetaLinux_RootFS_Builder_Alma8._check_rebuild_required(
            src_search_list=self._project_cfg_files
            + [
                self._block_src_dir / "src",
                self._patch_dir,
                self._source_repo_dir / "sources",
                self._source_repo_dir / "build" / "conf",
                self._source_repo_dir / "build" / "workspace",
            ],
            src_ignore_list=[
                self._source_repo_dir / "sources" / "core" / "bitbake" / "lib" / "bb" / "pysh" / "pyshtables.py"
            ],
            out_search_list=[
                self._source_repo_dir / "build" / "tmp" / "deploy" / "images",
                self._source_repo_dir
                / "build"
                / "tmp"
                / "deploy"
                / "images"
                / "zynqmp-generic"
                / "core-image-minimal-zynqmp-generic.cpio.gz",
                self._source_repo_dir / "sources" / "core" / "bitbake" / "lib" / "bb" / "pysh" / "pyshtables.py",
            ],
        ):
            pretty_print.print_build(
                "No need to rebuild the base root file system. No altered source files detected..."
            )
            return

        self.clean_work()
        self._mod_dir.mkdir(parents=True)

        pretty_print.print_build("Building the base root file system...")

        base_rootfs_build_commands = (
            f"'cd {self._source_repo_dir} && " f"source ./setupsdk && " "bitbake core-image-minimal'"
        )

        self.run_containerizable_sh_command(command=base_rootfs_build_commands, dirs_to_mount=[(self._repo_dir, "Z")])

        extract_rootfs_commands = f"'gunzip -c {self._source_repo_dir}/build/tmp/deploy/images/zynqmp-generic/core-image-minimal-zynqmp-generic.cpio.gz | sh -c \"cd {self._mod_dir}/ && cpio -i\"'"

        # The root user is used in this container. This is necessary in order to build a RootFS image.
        self.run_containerizable_sh_command(
            command=extract_rootfs_commands,
            dirs_to_mount=[(self._repo_dir, "Z"), (self._work_dir, "Z")],
            run_as_root=True,
        )

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
        if not self._mod_dir.is_dir():
            pretty_print.print_error(f"RootFS at {self._mod_dir} not found.")
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

        add_kmodules_commands = (
            f"'cd {self._work_dir} && "
            f"tar -xzf {kmods_archive} && "
            f"chown -R root:root lib && "
            f"chmod -R 000 lib && "
            f"chmod -R u=rwX,go=rX lib && "
            f"rm -rf {self._mod_dir}/lib/modules/* && "
            f"mv lib/modules/* {self._mod_dir}/lib/modules/ && "
            f"rm -rf lib'"
        )

        # The root user is used in this container. This is necessary in order to build a RootFS image.
        self.run_containerizable_sh_command(
            command=add_kmodules_commands,
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
        if not ZynqMP_AMD_PetaLinux_RootFS_Builder_Alma8._check_rebuild_required(
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

            add_build_info_commands = (
                f"'mv {self._build_info_file} {self._mod_dir}/etc/fs_build_info && "
                f"chmod 0444 {self._mod_dir}/etc/fs_build_info'"
            )

            # The root user is used in this container. This is necessary in order to build a RootFS image.
            self.run_containerizable_sh_command(
                command=add_build_info_commands, dirs_to_mount=[(self._work_dir, "Z")], run_as_root=True
            )
        else:
            # Remove existing build information file
            clean_build_info_commands = f"'rm -f {self._build_dir}/etc/fs_build_info'"

            # The root user is used in this container. This is necessary in order to build a RootFS image.
            self.run_containerizable_sh_command(
                command=clean_build_info_commands, dirs_to_mount=[(self._work_dir, "Z")], run_as_root=True
            )

        if prebuilt:
            archive_name = f"petalinux_zynqmp_pre-built"
        else:
            archive_name = self._rootfs_name

        # Tar was tested with three compression options:
        # Option	Size	Duration
        # --xz	872M	real	17m59.080s
        # -I pxz	887M	real	3m43.987s
        # -I pigz	1.3G	real	0m20.747s
        archive_build_commands = (
            f"'cd {self._mod_dir} && "
            f'tar -I pxz --numeric-owner -p -cf  {self._output_dir / f"{archive_name}.tar.xz"} ./ && '
            f"if id {self._host_user} >/dev/null 2>&1; then "
            f'    chown -R {self._host_user}:{self._host_user} {self._output_dir / f"{archive_name}.tar.xz"}; '
            f"fi'"
        )

        # The root user is used in this container. This is necessary in order to build a RootFS image.
        self.run_containerizable_sh_command(
            command=archive_build_commands,
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
        Imports a pre-built root file system.

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
        self._mod_dir.mkdir(parents=True)

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

        extract_pb_rootfs_commands = (
            f"'tar --numeric-owner -p -xf {self._work_dir / prebuilt_rootfs_archive} -C {self._mod_dir}'"
        )

        # The root user is used in this container. This is necessary in order to build a RootFS image.
        self.run_containerizable_sh_command(
            command=extract_pb_rootfs_commands, dirs_to_mount=[(self._work_dir, "Z")], run_as_root=True
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

    def clean_repo(self):
        """
        This function cleans the git repo directory.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        if not self._repo_dir.exists():
            pretty_print.print_clean("No need to clean the repo directory...")
            return

        # Iterate over all repos and check if there are uncommited changes in the git repo
        results = Shell_Command_Runners.get_sh_results([str(self._repo_script), "list"], cwd=self._source_repo_dir)
        for line in results.stdout.splitlines():
            path, colon, project = line.split(" ", 2)
            # Check if this repo contains uncommited changes
            results = Shell_Command_Runners.get_sh_results(
                ["git", "-C", str(self._source_repo_dir / path), "status", "--porcelain"]
            )
            if results.stdout:
                pretty_print.print_warning(
                    f"There are uncommited changes in {self._source_repo_dir / path}. Do you really want to clean this repo? (y/n) ",
                    end="",
                )
                answer = input("")
                if answer.lower() not in ["y", "Y", "yes", "Yes"]:
                    pretty_print.print_clean("Cleaning abborted...")
                    sys.exit(1)

        pretty_print.print_clean("Cleaning repo directory...")

        cleaning_commands = f'"rm -rf {self._repo_dir}/* {self._repo_dir}/.* 2> /dev/null || true"'

        self.run_containerizable_sh_command(command=cleaning_commands, dirs_to_mount=[(self._repo_dir, "Z")])

        # Remove flag
        self._patches_applied_flag.unlink(missing_ok=True)

        # Remove empty repo directory
        self._repo_dir.rmdir()
