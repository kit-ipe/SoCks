import sys
import pathlib
import stat
import urllib
import inspect
import os
import csv

import socks.pretty_print as pretty_print
from socks.build_validator import Build_Validator
from socks.yaml_editor import YAML_Editor
from abstract_builders.file_system_builder import File_System_Builder
from amd_zynqmp_support.zynqmp_amd_petalinux_rootfs_model import (
    ZynqMP_AMD_PetaLinux_RootFS_Model,
    ZynqMP_AMD_PetaLinux_RootFS_Patch_Model,
)


class ZynqMP_AMD_PetaLinux_RootFS_Builder(File_System_Builder):
    """
    AMD PetaLinux root file system builder class
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str = "rootfs",
        block_description: str = "Build an AMD PetaLinux root file system",
        model_class: type[object] = ZynqMP_AMD_PetaLinux_RootFS_Model,
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
        # Repo tool
        self._repo_script = self._repo_dir / "repo"

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
            ] + [self.init_repo, self.apply_patches, self.yocto_init, self._build_validator.save_project_cfg_prepare]
            block_cmds["build"].extend(block_cmds["prepare"])
            block_cmds["build"].extend(
                [
                    self.build_base_file_system,
                    self.add_kmodules,
                    self.build_archive,
                    self.export_block_package,
                    self._build_validator.save_project_cfg_build,
                ]
            )
            block_cmds["prebuild"].extend(block_cmds["prepare"])
            block_cmds["prebuild"].extend(
                [
                    self.build_base_file_system,
                    self.build_archive_prebuilt,
                    self.export_block_package,
                    self._build_validator.save_project_cfg_build,
                ]
            )
            block_cmds["create-patches"].extend([self.create_patches])
            block_cmds["start-container"].extend([self.container_executor.build_container_image, self.start_container])
        elif self.block_cfg.source == "import":
            block_cmds["build"].extend(block_cmds["prepare"])
            block_cmds["build"].extend(
                [
                    self.import_prebuilt,
                    self.add_kmodules,
                    self.build_archive,
                    self.export_block_package,
                    self._build_validator.save_project_cfg_build,
                ]
            )
        return block_cmds

    @property
    def _file_system_name(self):
        return f"petalinux_zynqmp_{self.project_cfg.project.name}"

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

        try:
            super().validate_srcs()
        except ValueError:
            # This exception is expected for this block, as the file that lists all patches must have two columns here
            # Import patches into the project configuration file
            patches_file = self._patch_dir / "patches.csv"
            with open(patches_file, mode="r", newline="") as file:
                reader = csv.reader(file)
                patches = list(reader)

            # Check the entire file before anything is done
            for patch in patches:
                if len(patch) != 2:
                    raise ValueError(f"File '{patches_file}' does not have two complete columns")

            for patch in patches:
                # Add patch to project configuration file
                # ToDo: Maybe the main project configuration file should not be hard coded here
                YAML_Editor.append_list_entry(
                    file=self._project_dir / "project.yml",
                    keys=["blocks", self.block_id, "project", "patches"],
                    data={"project": patch[0], "patch": patch[1]},
                )
                # Add patch to currently used project configuration
                if self.block_cfg.project.patches == None:
                    self.block_cfg.project.patches = [
                        ZynqMP_AMD_PetaLinux_RootFS_Patch_Model(project=patch[0], patch=patch[1])
                    ]
                else:
                    self.block_cfg.project.patches.append(
                        ZynqMP_AMD_PetaLinux_RootFS_Patch_Model(project=patch[0], patch=patch[1])
                    )

            os.remove(patches_file)

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

        # Skip all operations if the repo config hasn't changed
        if not self._build_validator.check_rebuild_bc_config(
            keys=[["blocks", self.block_id, "project", "build_srcs"]], accept_prep=True
        ):
            pretty_print.print_build("No need to initialize the local repos...")
            return

        self.clean_output()
        self._output_dir.mkdir(parents=True)
        self.clean_repo()
        self._source_repo_dir.mkdir(parents=True)

        pretty_print.print_build("Initializing local repos...")

        # Download the google repo tool
        urllib.request.urlretrieve(
            url="https://storage.googleapis.com/git-repo-downloads/repo", filename=self._repo_script
        )
        # Make repo executable
        self._repo_script.chmod(self._repo_script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        # Initialize repo in the current directory
        self.shell_executor.exec_sh_command(
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
        self.shell_executor.exec_sh_command([str(self._repo_script), "sync"], cwd=self._source_repo_dir)
        # Initialize local branches in all repos
        results = self.shell_executor.get_sh_results([str(self._repo_script), "list"], cwd=self._source_repo_dir)
        for line in results.stdout.splitlines():
            path, colon, project = line.split(" ", 2)
            # Create new branch self._git_local_ref_branch. This branch is used as a reference where all existing patches are applied to the git sources
            self.shell_executor.exec_sh_command(
                [str(self._repo_script), "start", self._git_local_ref_branch, project], cwd=self._source_repo_dir
            )
            # Create new branch self._git_local_dev_branch. This branch is used as the local development branch. New patches can be created from this branch.
            self.shell_executor.exec_sh_command(
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
        results = self.shell_executor.get_sh_results([str(self._repo_script), "list"], cwd=self._source_repo_dir)
        for line in results.stdout.splitlines():
            path, colon, project = line.split(" ", 2)
            # Check if this repo contains new commits
            result_new_commits = self.shell_executor.get_sh_results(
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
                result_new_patches = self.shell_executor.get_sh_results(
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
                # Add newly created patches to the project configuration file
                for line in result_new_patches.stdout.splitlines():
                    new_patch = line.rpartition("/")[2]
                    pretty_print.print_info(f"Patch {new_patch} was created")
                    # ToDo: Maybe the main project configuration file should not be hard coded here
                    YAML_Editor.append_list_entry(
                        file=self._project_dir / "project.yml",
                        keys=["blocks", self.block_id, "project", "patches"],
                        data={"project": project, "patch": new_patch},
                    )
                    # Add patch to currently used project configuration
                    if self.block_cfg.project.patches == None:
                        self.block_cfg.project.patches = [
                            ZynqMP_AMD_PetaLinux_RootFS_Patch_Model(project=project, patch=new_patch)
                        ]
                    else:
                        self.block_cfg.project.patches.append(
                            ZynqMP_AMD_PetaLinux_RootFS_Patch_Model(project=project, patch=new_patch)
                        )
                # Synchronize the branches ref and dev to be able to detect new commits in the future
                self.shell_executor.exec_sh_command(
                    ["git", "-C", str(self._source_repo_dir / path), "checkout", self._git_local_ref_branch],
                    visible_lines=0,
                )
                self.shell_executor.exec_sh_command(
                    ["git", "-C", str(self._source_repo_dir / path), "merge", self._git_local_dev_branch],
                    visible_lines=0,
                )
                self.shell_executor.exec_sh_command(
                    ["git", "-C", str(self._source_repo_dir / path), "checkout", self._git_local_dev_branch],
                    visible_lines=0,
                )

        if not repos_with_commits:
            pretty_print.print_warning("No commits found that can be used as sources for patches.")
            return

        # Update the timestamp of the patches applied tag, if it exists. Otherwise, SoCks assumes
        # that the user has modified the patches since they were applied.
        patches_already_added = (
            self._build_log.get_logged_timestamp(identifier=f"function-apply_patches-success") != 0.0
        )
        if patches_already_added:
            self._build_log.log_timestamp(identifier=f"function-apply_patches-success")

    def apply_patches(self):
        """
        This function iterates over all patches listed in the project configuration file and applies them.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Skip all operations if no patches are provided or if the patches have already been applied
        patches_already_added = (
            self._build_log.get_logged_timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success")
            != 0.0
        )
        if self.block_cfg.project.patches == None or patches_already_added:
            pretty_print.print_build("No need to apply patches...")
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            pretty_print.print_build("Applying patches...")

            for item in self.block_cfg.project.patches:
                project = item.project
                patch = item.patch
                if not (self._patch_dir / patch).is_file():
                    pretty_print.print_error(
                        f"Patch '{patch}' specified in 'blocks -> {self.block_id} -> project -> patches' "
                        f"does not exist in {self._patch_dir}/"
                    )
                    sys.exit(1)

                # Get path of this project
                results = self.shell_executor.get_sh_results(
                    [str(self._repo_script), "list", "-r", project, "-p"], cwd=self._source_repo_dir
                )
                path = results.stdout.splitlines()[0]
                # Apply patch
                self.shell_executor.exec_sh_command(
                    ["git", "-C", str(self._source_repo_dir / path), "am", str(self._patch_dir / patch)]
                )

                # Update the branch self._git_local_ref_branch so that it contains the applied patch and is in
                # sync with self._git_local_dev_branch. This is important to be able to create new patches.
                self.shell_executor.exec_sh_command(
                    [str(self._repo_script), "checkout", self._git_local_ref_branch, project],
                    cwd=self._source_repo_dir,
                    visible_lines=0,
                )
                self.shell_executor.exec_sh_command(
                    ["git", "-C", str(self._source_repo_dir / path), "merge", self._git_local_dev_branch],
                    visible_lines=0,
                )
                self.shell_executor.exec_sh_command(
                    [str(self._repo_script), "checkout", self._git_local_dev_branch, project],
                    cwd=self._source_repo_dir,
                    visible_lines=0,
                )

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

        local_conf_append = self._resources_dir / "local.conf.append"

        pretty_print.print_build("Initializing yocto...")

        yocto_init_commands = [
            f"cd {self._source_repo_dir}",
            f"source ./setupsdk",
            f"cat {local_conf_append} >> {self._source_repo_dir}/build/conf/local.conf",
        ]

        self.container_executor.exec_sh_commands(
            commands=yocto_init_commands, dirs_to_mount=[(self._repo_dir, "Z"), (self._block_src_dir, "Z")]
        )

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
        if not Build_Validator.check_rebuild_bc_timestamp(
            src_search_list=[
                self._resources_dir,
                self._source_repo_dir / "sources",
                self._source_repo_dir / "build" / "conf",
                self._source_repo_dir / "build" / "workspace",
            ],
            src_ignore_list=[
                self._source_repo_dir / "sources" / "core" / "bitbake" / "lib" / "bb" / "pysh" / "pyshtables.py"
            ],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ) and not self._build_validator.check_rebuild_bc_config(keys=[["project", "name"]]):
            pretty_print.print_build(
                "No need to rebuild the base root file system. No altered source files detected..."
            )
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            self.clean_work()
            self._build_dir.mkdir(parents=True)

            pretty_print.print_build("Building the base root file system...")

            base_rootfs_build_commands = [
                f"cd {self._source_repo_dir}",
                "source ./setupsdk",
                "bitbake core-image-minimal",
            ]

            self.container_executor.exec_sh_commands(
                commands=base_rootfs_build_commands,
                dirs_to_mount=[(self._repo_dir, "Z")],
                print_commands=True,
            )

            extract_rootfs_commands = [
                f'gunzip -c {self._source_repo_dir}/build/tmp/deploy/images/zynqmp-generic/core-image-minimal-zynqmp-generic.cpio.gz | sh -c "cd {self._build_dir}/ && cpio -i"'
            ]

            # The root user is used in this container. This is necessary in order to build a RootFS image.
            self.container_executor.exec_sh_commands(
                commands=extract_rootfs_commands,
                dirs_to_mount=[(self._repo_dir, "Z"), (self._work_dir, "Z")],
                run_as_root=True,
            )

    def build_archive(self, prebuilt: bool = False):
        """
        Packs the entire rootfs in an archive.

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
            archive_name = f"petalinux_zynqmp_pre-built"
        else:
            archive_name = self._file_system_name

        self._build_archive(archive_name=archive_name, file_extension="tar.xz", tar_compress_param="-I pxz")

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
        results = self.shell_executor.get_sh_results([str(self._repo_script), "list"], cwd=self._source_repo_dir)
        for line in results.stdout.splitlines():
            path, colon, project = line.split(" ", 2)
            # Skip, if the directory does not exist
            if not (self._source_repo_dir / path).is_dir():
                continue
            # Check if this repo contains uncommited changes
            results = self.shell_executor.get_sh_results(
                ["git", "-C", str(self._source_repo_dir / path), "status", "--porcelain"]
            )
            if results.stdout:
                pretty_print.print_warning(
                    f"There are uncommited changes in {self._source_repo_dir / path}/. Do you really want to clean this repo? (y/n) ",
                    end="",
                )
                answer = input("")
                if answer.lower() not in ("y", "yes"):
                    pretty_print.print_clean("Cleaning abborted...")
                    sys.exit(1)

        pretty_print.print_clean("Cleaning repo directory...")

        cleaning_commands = [f"rm -rf {self._repo_dir}/* {self._repo_dir}/.* 2> /dev/null || true"]

        self.container_executor.exec_sh_commands(commands=cleaning_commands, dirs_to_mount=[(self._repo_dir, "Z")])

        # Remove empty repo directory
        self._repo_dir.rmdir()
