import os
import pwd
import pathlib
import importlib.resources
import shutil
import sys
from datetime import datetime
import urllib
import validators
import tarfile
import re
import hashlib
import time
import pydantic
import inspect
import csv
from abc import ABC, abstractmethod

import socks.pretty_print as pretty_print
from socks.shell_executor import Shell_Executor
from socks.container_executor import Container_Executor
from socks.build_validator import Build_Validator
from socks.file_downloader import File_Downloader
from socks.timestamp_logger import Timestamp_Logger
from socks.yaml_editor import YAML_Editor
import abstract_builders


class Builder(ABC):
    """
    Base class for all builder classes
    """

    def __init__(
        self,
        project_cfg: dict,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str,
        block_description: str,
        model_class: type[object],
    ):
        self.block_id = block_id
        self.block_description = block_description
        self.pre_action_warnings = []

        # Initialize block model
        try:
            self.project_cfg = model_class(**project_cfg)
        except pydantic.ValidationError as e:
            for err in e.errors():
                keys = []
                for item in err["loc"]:
                    if isinstance(item, str):
                        # If the item is a string, just append it
                        keys.append(item)
                    if isinstance(item, int):
                        # If the item is an integer, it is an index in a list
                        keys[-1] = f"{keys[-1]}[{item}]"
                pretty_print.print_error(
                    f"The following error occured while analyzing node '{' -> '.join(keys)}' "
                    f"of the project configuration: {err['msg']}"
                )
            sys.exit(1)

        self.block_cfg = getattr(self.project_cfg.blocks, block_id)

        # Find project sources for this block
        # ToDo: Maybe this should be unified and one should merge these four variables and use only two.
        # But I suspect that there will rarely be several project sources and that their interaction is not uniform.
        # That is why I think it is better to keep these variables separate for now
        self._local_source_dir = None
        self._local_source_dirs = []
        self._source_repo = None
        self._source_repos = []
        if hasattr(self.block_cfg.project, "build_srcs"):
            if isinstance(self.block_cfg.project.build_srcs, list):
                self._local_source_dirs, self._source_repos = self._eval_mult_prj_srcs()
            else:
                self._local_source_dir, self._source_repo = self._eval_single_prj_src()

        # Get host user and id (a bit complicated but should work in most Unix environments)
        self._host_user_id = os.getuid()
        self._host_user = pwd.getpwuid(self._host_user_id).pw_name

        # Local git branches
        self._git_local_ref_branch = "__ref"
        self._git_local_dev_branch = "__temp"

        # SoCks directorys
        self._socks_dir = socks_dir
        self._container_dir = self._socks_dir / "container"
        self._builders_dir = pathlib.Path(importlib.resources.files(self.__module__.partition(".")[0]))
        if not (self._builders_dir / "__init__.py").is_file():
            raise ModuleNotFoundError(f"The following directory is not a package: {self._builders_dir}")

        # Project directories
        self._project_dir = project_dir
        self._project_src_dir = self._project_dir / "src"
        self._project_temp_dir = self._project_dir / "temp"
        self._block_src_dir = self._project_src_dir / self.block_id
        self._block_temp_dir = self._project_temp_dir / self.block_id
        self._patch_dir = self._block_src_dir / "patches"
        self._resources_dir = self._block_src_dir / "resources"
        self._download_dir = self._block_temp_dir / "download"
        self._work_dir = self._block_temp_dir / "work"
        self._output_dir = self._block_temp_dir / "output"
        self._dependencies_dir = self._block_temp_dir / "dependencies"
        if self._local_source_dir is not None:
            # Local project sources are used for this block
            self._repo_dir = self._local_source_dir
            self._source_repo_dir = self._local_source_dir
        elif self._source_repo is not None:
            # Online project sources are used for this block
            self._repo_dir = self._block_temp_dir / "repo"
            self._source_repo_dir = self._repo_dir / (
                pathlib.Path(urllib.parse.urlparse(url=self._source_repo["url"]).path).stem
                + "-"
                + self._source_repo["branch"]
            )
        elif self._source_repos or self._local_source_dirs:
            # This block uses several project sources. In this case, the directory structure cannot be
            # completely standardized. The required project directories must be created in the respective builder.
            self._repo_dir = self._block_temp_dir / "repo"
            self._source_repo_dir = None
        else:
            # This block does not need any external sources
            self._repo_dir = self._block_temp_dir / "repo"
            self._source_repo_dir = self._repo_dir / "runtime-generated"

        # Project files
        # File for saving the checksum of the imported, pre-built block package
        self._source_bp_md5_file = self._work_dir / "source_bp.md5"

        # Helpers
        self._build_validator = Build_Validator(
            project_cfg=self.project_cfg, model_class=model_class, block_temp_dir=self._block_temp_dir
        )
        self._build_log = Timestamp_Logger(log_file=self._block_temp_dir / ".build_log.csv")
        self.shell_executor = Shell_Executor()
        self.container_executor = Container_Executor(
            container_tool=self.project_cfg.external_tools.container_tool,
            container_image=self.block_cfg.container.image,
            container_image_tag=self.block_cfg.container.tag,
            container_file=self._container_dir / f"{self.block_cfg.container.image}.containerfile",
            container_log_file=self._project_temp_dir / ".container_log.csv",
        )

    @property
    @abstractmethod
    def _block_deps(self):
        pass

    @property
    @abstractmethod
    def block_cmds(self):
        pass

    def _eval_single_prj_src(self) -> tuple[pathlib.Path, dict]:
        """
        Process the source section of a block with a single source.

        Args:
            None

        Returns:
            None

        Raises:
            ValueError:
                If the block configuration does not contain a valid reference to a block project source
        """

        local_source_dir = None
        source_repo = None

        if urllib.parse.urlparse(self.block_cfg.project.build_srcs.source).scheme == "file":
            # Local project sources are used for this block
            local_source_dir = pathlib.Path(urllib.parse.urlparse(self.block_cfg.project.build_srcs.source).path)
            if not local_source_dir.is_dir():
                pretty_print.print_error(
                    f"The following setting in blocks/{self.block_id}/project/build_srcs/source does not point to a directory: {self.block_cfg.project.build_srcs.source}"
                )
                sys.exit(1)
            self.pre_action_warnings.append(
                f"The following local project source will be used for this block: {local_source_dir}. "
                "SoCks will operate on this directory, create local branches, apply patches, build binaries, etc."
            )
        elif validators.url(self.block_cfg.project.build_srcs.source):
            # The sources must be downloaded from git
            if self.block_cfg.project.build_srcs.branch is None:
                pretty_print.print_error(
                    f"It is necessary to specify a branch for each git repo, but no branch was specified for: {self.block_cfg.project.build_srcs.source}"
                )
                sys.exit(1)
            else:
                source_repo = {
                    "url": self.block_cfg.project.build_srcs.source,
                    "branch": self.block_cfg.project.build_srcs.branch,
                }
        else:
            raise ValueError(
                "The following string is not a valid reference to a block project source: "
                f"{self.block_cfg.project.build_srcs.source}. Only URI schemes 'https', 'http', 'ssh', and 'file' "
                "are supported."
            )

        return local_source_dir, source_repo

    def _eval_mult_prj_srcs(self) -> tuple[list[pathlib.Path], list[dict]]:
        """
        Process the source section of a block with multiple sources.

        Args:
            None

        Returns:
            None

        Raises:
            ValueError:
                If the block configuration does not contain a valid reference to a block project source
        """

        local_source_dirs = []
        source_repos = []

        for index in range(len(self.block_cfg.project.build_srcs)):
            if urllib.parse.urlparse(self.block_cfg.project.build_srcs[index].source).scheme == "file":
                # This is an external local project source
                local_source_dirs.append(
                    pathlib.Path(urllib.parse.urlparse(self.block_cfg.project.build_srcs[index].source).path)
                )
                if not local_source_dirs[-1].is_dir():
                    pretty_print.print_error(
                        f"The following setting in blocks/{self.block_id}/project/build_srcs/source[{index}] does not point to a directory: {self.block_cfg.project.build_srcs[index].source}"
                    )
                    sys.exit(1)
                self.pre_action_warnings.append(
                    f"The following local project source will be used for this block: {local_source_dirs[-1]}. "
                    "SoCks will operate on this directory, create local branches, apply patches, build binaries, etc."
                )
            elif validators.url(self.block_cfg.project.build_srcs[index].source):
                # This source must be downloaded from git
                if self.block_cfg.project.build_srcs[index].branch is None:
                    pretty_print.print_error(
                        f"It is necessary to specify a branch for each git repo, but no branch was specified for: {self.block_cfg.project.build_srcs[index].source}"
                    )
                    sys.exit(1)
                else:
                    source_repos.append(
                        {
                            "url": self.block_cfg.project.build_srcs[index].source,
                            "branch": self.block_cfg.project.build_srcs[index].branch,
                        }
                    )
            else:
                raise ValueError(
                    "The following string is not a valid reference to a block project source: "
                    f"{self.block_cfg.project.build_srcs[index].source}. Only URI schemes 'https', 'http', 'ssh', and 'file' "
                    "are supported."
                )

        return local_source_dirs, source_repos

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

        # Check whether the user has modified the patches since they were applied
        patches_already_added = (
            self._build_log.get_logged_timestamp(identifier=f"function-apply_patches-success") != 0.0
        )
        if (
            self._patch_dir.exists()
            and patches_already_added
            and Build_Validator.check_rebuild_bc_timestamp(
                src_search_list=[self._patch_dir],
                out_timestamp=self._build_log.get_logged_timestamp(identifier=f"function-apply_patches-success"),
            )
        ):
            pretty_print.print_error(
                f"It seems that the patches for block '{self.block_id}' have changed since "
                f"they were applied. This is an unexpected state. Please clean and rebuild block '{self.block_id}'."
            )
            sys.exit(1)

    def _compose_build_info(self) -> str:
        """
        Compose a string with build information.

        Args:
            None

        Returns:
            String containing the build information.

        Raises:
            None
        """

        build_info = ""

        # Use the git command to collect information, if possible
        if (
            self.shell_executor.get_sh_results(
                command=["git", "-C", str(self._project_dir), "rev-parse", "--is-inside-work-tree"], check=False
            ).returncode
            == 0
        ):
            # The project directory is a git directory
            results = self.shell_executor.get_sh_results(["git", "-C", str(self._project_dir), "rev-parse", "HEAD"])
            build_info = build_info + f"GIT_COMMIT_SHA: {results.stdout.splitlines()[0]}\n"

            results = self.shell_executor.get_sh_results(
                ["git", "-C", str(self._project_dir), "rev-parse", "--abbrev-ref", "HEAD"]
            )
            git_ref_name = results.stdout.splitlines()[0]
            if git_ref_name == "HEAD":
                results = self.shell_executor.get_sh_results(
                    ["git", "-C", str(self._project_dir), "describe", "--exact-match", git_ref_name], check=False
                )
                if results.returncode == 0:
                    git_tag_name = results.stdout.splitlines()[0]
                    build_info = build_info + f"GIT_TAG_NAME: {git_tag_name}\n"
            else:
                build_info = build_info + f"GIT_BRANCH_NAME: {git_ref_name}\n"

            results = self.shell_executor.get_sh_results(["git", "-C", str(self._project_dir), "status", "--porcelain"])
            if results.stdout:
                build_info = build_info + "GIT_IS_REPO_CLEAN: false\n\n"
            else:
                build_info = build_info + "GIT_IS_REPO_CLEAN: true\n\n"

        # Collect information for which the git command is not required
        current_time = time.time()
        if os.environ.get("GITLAB_CI") == "true":
            build_info = build_info + "BUILD_TYPE: gitlab\n"
            build_info = (
                build_info
                + f'BUILD_TIMESTAMP: {int(current_time)}   # {time.strftime("%Y-%m-%d %H:%M:%S (UTC)", time.gmtime(current_time))}\n'
            )
            build_info = build_info + f'GITLAB_CI_SERVER_URL: {os.environ.get("CI_SERVER_URL")}\n'
            build_info = build_info + f'GITLAB_CI_PROJECT_PATH: {os.environ.get("CI_PROJECT_PATH")}\n'
            build_info = build_info + f'GITLAB_CI_PROJECT_ID: {os.environ.get("CI_PROJECT_ID")}\n'
            build_info = build_info + f'GITLAB_CI_PIPELINE_ID: {os.environ.get("CI_PIPELINE_ID")}\n'
            build_info = build_info + f'GITLAB_CI_JOB_ID: {os.environ.get("CI_JOB_ID")}\n'
        else:
            build_info = build_info + "BUILD_TYPE: manual\n"
            build_info = (
                build_info
                + f'BUILD_TIMESTAMP: {int(current_time)}   # {time.strftime("%Y-%m-%d %H:%M:%S (UTC)", time.gmtime(current_time))}\n'
            )
            results = self.shell_executor.get_sh_results(["hostname"])
            build_info = build_info + f"MANUAL_BUILD_HOST: {results.stdout.splitlines()[0]}\n"
            results = self.shell_executor.get_sh_results(["id", "-un"])
            build_info = build_info + f"MANUAL_BUILD_USER: {results.stdout.splitlines()[0]}\n"

        return build_info

    def init_repo(self):
        """
        Clones and initializes the git repo.

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
            pretty_print.print_build("No need to initialize the local repo...")
            return

        if self._source_repo is not None and not isinstance(self._source_repo, dict):
            # ToDo: Maybe at some point this function should support initializing multiple repos as well, but I am not sure yet if this is really needed
            pretty_print.print_error(
                f"This function expects a single object and not an array in blocks/{self.block_id}/project/build_srcs."
            )
            sys.exit(1)

        pretty_print.print_build("Initializing local repo...")

        self.clean_output()
        self._output_dir.mkdir(parents=True)

        # Check if the source code of this block project is online and needs to be downloaded
        if self._source_repo is not None:
            self.clean_repo()
            self._repo_dir.mkdir(parents=True)
            # Clone the repo
            self.shell_executor.exec_sh_command(
                [
                    "git",
                    "clone",
                    "--recursive",
                    "--depth 1",
                    "--shallow-submodules",
                    "--branch",
                    self._source_repo["branch"],
                    self._source_repo["url"],
                    str(self._source_repo_dir),
                ]
            )

        results = self.shell_executor.get_sh_results(["git", "-C", str(self._source_repo_dir), "branch", "-a"])
        if not (
            f"  {self._git_local_ref_branch}" in results.stdout.splitlines()
            or f"* {self._git_local_ref_branch}" in results.stdout.splitlines()
        ):
            # Create new branch self._git_local_ref_branch. This branch is used as a reference where all existing patches are applied to the git sources
            self.shell_executor.exec_sh_command(
                ["git", "-C", str(self._source_repo_dir), "switch", "-c", self._git_local_ref_branch]
            )
        if not (
            f"  {self._git_local_dev_branch}" in results.stdout.splitlines()
            or f"* {self._git_local_dev_branch}" in results.stdout.splitlines()
        ):
            # Create new branch self._git_local_dev_branch. This branch is used as the local development branch. New patches can be created from this branch.
            self.shell_executor.exec_sh_command(
                ["git", "-C", str(self._source_repo_dir), "switch", "-c", self._git_local_dev_branch]
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

        # Only create patches if there are commits on branch self._git_local_dev_branch that are not on branch self._git_local_dev_branch.
        result_new_commits = self.shell_executor.get_sh_results(
            [
                "git",
                "-C",
                str(self._source_repo_dir),
                "log",
                "--cherry-pick",
                "--oneline",
                self._git_local_dev_branch,
                f"^{self._git_local_ref_branch}",
            ]
        )

        if not result_new_commits.stdout:
            pretty_print.print_warning("No commits found that can be used as sources for patches.")
            return

        pretty_print.print_build("Creating patches...")

        # Create patches
        result_new_patches = self.shell_executor.get_sh_results(
            [
                "git",
                "-C",
                str(self._source_repo_dir),
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
            # Add patch to project configuration file
            # ToDo: Maybe the main project configuration file should not be hard coded here
            YAML_Editor.append_list_entry(
                file=self._project_dir / "project.yml",
                keys=["blocks", self.block_id, "project", "patches"],
                data=new_patch,
            )
            # Add patch to currently used project configuration
            if self.block_cfg.project.patches == None:
                self.block_cfg.project.patches = [new_patch]
            else:
                self.block_cfg.project.patches.append(new_patch)

        # Synchronize the branches ref and dev to be able to detect new commits in the future
        self.shell_executor.exec_sh_command(
            ["git", "-C", str(self._source_repo_dir), "checkout", self._git_local_ref_branch], visible_lines=0
        )
        self.shell_executor.exec_sh_command(
            ["git", "-C", str(self._source_repo_dir), "merge", self._git_local_dev_branch], visible_lines=0
        )
        self.shell_executor.exec_sh_command(
            ["git", "-C", str(self._source_repo_dir), "checkout", self._git_local_dev_branch], visible_lines=0
        )

        # Add patches applied tag or update the timestamp, because the newly created patches have already been
        # applied and SoCks should not try to apply them again the next time it is called.
        self._build_log.log_timestamp(identifier=f"function-apply_patches-success")

    def apply_patches(self):
        """
        This function iterates over all patches listed in the project configuration file and applies them to the repo.

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

            for patch in self.block_cfg.project.patches:
                if not (self._patch_dir / patch).is_file():
                    pretty_print.print_error(
                        f"Patch '{patch}' specified in 'blocks -> {self.block_id} -> project -> patches' does not exist in {self._patch_dir}"
                    )
                    sys.exit(1)

                # Apply patch
                self.shell_executor.exec_sh_command(
                    ["git", "-C", str(self._source_repo_dir), "am", "--ignore-whitespace", str(self._patch_dir / patch)]
                )

            # Update the branch self._git_local_ref_branch so that it contains the applied patches and is in sync with self._git_local_dev_branch. This is important to be able to create new patches.
            self.shell_executor.exec_sh_command(
                ["git", "-C", str(self._source_repo_dir), "checkout", self._git_local_ref_branch], visible_lines=0
            )
            self.shell_executor.exec_sh_command(
                ["git", "-C", str(self._source_repo_dir), "merge", self._git_local_dev_branch], visible_lines=0
            )
            self.shell_executor.exec_sh_command(
                ["git", "-C", str(self._source_repo_dir), "checkout", self._git_local_dev_branch], visible_lines=0
            )

    def _download_prebuilt(self):
        """
        Download pre-built files.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Get timestamp of the file online
        last_mod_online_timestamp = File_Downloader.get_last_modified(url=self.block_cfg.project.import_src)

        # Get timestamp of the downloaded file, if any
        last_mod_local_timestamp = 0
        if self._download_dir.is_dir():
            items = list(self._download_dir.iterdir())
            if len(items) == 1:
                last_mod_local_timestamp = items[0].stat().st_mtime
            elif len(items) != 0:
                pretty_print.print_error(
                    f"There is more than one item in {self._download_dir}\nPlease empty the directory"
                )
                sys.exit(1)

        # Check if the file needs to be downloaded
        if last_mod_local_timestamp > last_mod_online_timestamp:
            pretty_print.print_build("No need to download pre-built files...")
            return

        self.clean_download()
        self._download_dir.mkdir(parents=True)

        pretty_print.print_build("Downloading archive with pre-built files...")

        # Download the file
        File_Downloader.get_file(url=self.block_cfg.project.import_src, output_dir=self._download_dir)

    def import_prebuilt(self):
        """
        Imports a pre-built block package. If a file URI is provided, this local block package is imported. If a http or
        https URI is provided, the file is downloaded.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Get path of the pre-built block package
        if self.block_cfg.project.import_src is None:
            pretty_print.print_error(
                f"The property blocks/{self.block_id}/project/pre-built is required to "
                "import the block, but it is not set."
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

        # Check whether the file to be imported exists
        if not prebuilt_block_package.is_file():
            pretty_print.print_error(
                f"Unable to import block package. The following file does not exist: {prebuilt_block_package}"
            )
            sys.exit(1)

        # Check whether the file is a supported archive
        if not prebuilt_block_package.name.endswith(("tar.gz", "tgz", "tar.xz", "txz")):
            pretty_print.print_error(
                f"Unable to import block package. The type of this archive is not supported: '{prebuilt_block_package.name}'"
            )
            sys.exit(1)

        # Calculate md5 of the provided file
        md5_new_file = hashlib.md5(prebuilt_block_package.read_bytes()).hexdigest()
        # Read md5 of previously used file, if any
        md5_existsing_file = 0
        if self._source_bp_md5_file.is_file():
            with self._source_bp_md5_file.open("r") as f:
                md5_existsing_file = f.read()

        # Check if the pre-built block package needs to be imported
        if md5_existsing_file == md5_new_file:
            pretty_print.print_build(
                "No need to import the pre-built block package. No altered source files detected..."
            )
            return

        self.clean_output()
        self._output_dir.mkdir(parents=True)
        self._work_dir.mkdir(parents=True, exist_ok=True)

        pretty_print.print_build("Importing pre-built block package...")

        # Import block package
        imported_block_package = self._output_dir / (
            f"bp_{self.block_id}_import" + "".join(prebuilt_block_package.suffixes)
        )
        shutil.copy(prebuilt_block_package, imported_block_package)

        # Extract pre-built files
        with tarfile.open(imported_block_package, "r:*") as archive:
            # Extract all contents to the output directory
            archive.extractall(path=self._output_dir)

        # Save checksum in file
        with self._source_bp_md5_file.open("w") as f:
            print(md5_new_file, file=f, end="")

    def export_block_package(self):
        """
        Exports the block package that contains all output products of this block.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        block_pkg_path = self._output_dir / f"bp_{self.block_id}_{self.project_cfg.project.name}_{timestamp}.tar.gz"

        # Check whether there is something to export
        if not self._output_dir.is_dir() or not any(self._output_dir.iterdir()):
            pretty_print.print_error(
                f"Unable to export block package. The following director does not exist or is empty: {self._output_dir}"
            )
            sys.exit(1)

        # Check whether a package needs to be created
        if not Build_Validator.check_rebuild_bc_timestamp(
            src_search_list=[self._output_dir],
            src_ignore_list=[block_pkg_path],
            out_timestamp=self._build_log.get_logged_timestamp(
                identifier=f"function-{inspect.currentframe().f_code.co_name}-success"
            ),
        ) and not self._build_validator.check_rebuild_bc_config(keys=[["project", "name"]]):
            pretty_print.print_build("No need to export block package. No altered source files detected...")
            return

        with self._build_log.timestamp(identifier=f"function-{inspect.currentframe().f_code.co_name}-success"):
            # Delete old block package
            old_block_pkgs = list(self._output_dir.glob(f"bp_{self.block_id}_*.tar.gz"))
            for old_pkg in old_block_pkgs:
                old_pkg.unlink(missing_ok=True)

            pretty_print.print_build("Exporting block package...")

            # Export block package
            with tarfile.open(block_pkg_path, "w:gz") as archive:
                for file in self._output_dir.iterdir():
                    if not file.samefile(block_pkg_path):
                        archive.add(file.resolve(strict=True), arcname=file.name)

    def import_dependencies(self):
        """
        Imports all dependencies needed to build this block.
        Dependencies are block backages exported from other blocks.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        for dependency in self.block_cfg.project.dependencies.model_fields:
            block_pkg_cfg_str = getattr(self.block_cfg.project.dependencies, dependency)
            if block_pkg_cfg_str is None:
                continue

            block_pkgs_parent = (self._project_dir / block_pkg_cfg_str).parent
            block_pkgs_name = (self._project_dir / block_pkg_cfg_str).name
            block_pkgs = list(block_pkgs_parent.glob(block_pkgs_name))

            # Check if there is more than one block package in the directory
            if len(block_pkgs) != 1:
                pretty_print.print_error(f"Not exactly one block package that matches '{block_pkg_cfg_str}'")
                sys.exit(1)

            block_pkg_path = block_pkgs[0]
            import_path = self._dependencies_dir / dependency
            block_pkg_md5_file = self._dependencies_dir / f"block_pkg_{dependency}.md5"

            # Check whether the file to be imported exists
            if not block_pkg_path.is_file():
                pretty_print.print_error(
                    f"Unable to import block package. The following file does not exist: {block_pkg_path}"
                )
                sys.exit(1)

            # Check whether the file is a tar.gz archive
            if not block_pkg_path.name.endswith(("tar.gz", "tgz", "tar.xz", "txz")):
                pretty_print.print_error(
                    f"Unable to import block package. The type of this archive is not supported: '{block_pkg_path.name}'"
                )
                sys.exit(1)

            # Calculate md5 of the provided block package
            md5_new_file = hashlib.md5(block_pkg_path.read_bytes()).hexdigest()
            # Read md5 of previously imported block package, if any
            md5_existsing_file = 0
            if block_pkg_md5_file.is_file():
                with block_pkg_md5_file.open("r") as f:
                    md5_existsing_file = f.read()

            # Check whether this dependencie needs to be imported
            if md5_existsing_file == md5_new_file:
                pretty_print.print_build(
                    f"No need to import block package {block_pkg_path.name}. No altered source files detected..."
                )
                continue

            # Clean directory of this dependency
            self.clean_dependencies(dependency=dependency)
            import_path.mkdir(parents=True, exist_ok=True)

            pretty_print.print_build(f"Importing block package {block_pkg_path.name}...")

            # Import block package
            with tarfile.open(block_pkg_path, "r:*") as archive:
                # Check whether all expected files are included
                content = archive.getnames()
                for pattern in self._block_deps[dependency]:
                    matched_files = [file for file in content if re.fullmatch(pattern=pattern, string=file)]
                    # A file is missing if no file matches the pattern
                    if not matched_files:
                        pretty_print.print_error(
                            f"The block package {block_pkg_path} does not contain a file that matches the regex {pattern}"
                        )
                        sys.exit(1)
                # Extract all contents to the output directory
                archive.extractall(path=import_path)

            # Save checksum in file
            with block_pkg_md5_file.open("w") as f:
                print(md5_new_file, file=f, end="")

    def start_container(self):
        """
        Starts an interactive container with which the block can be built.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        potential_mounts = [
            (self._dependencies_dir, "Z"),
            (self._repo_dir, "Z"),
            (self._block_src_dir, "Z"),
            (self._work_dir, "Z"),
            (self._output_dir, "Z"),
        ]

        self.container_executor.start_container(potential_mounts=potential_mounts)

    def _run_menuconfig(self, menuconfig_commands: list[str]):
        """
        Opens the menuconfig tool to enable interactive configuration of the project.

        Args:
            menuconfig_commands:
                The commands to be executed in a container to configure the Linux kernel or U-Boot interactively.

        Returns:
            None

        Raises:
            None
        """

        if not self._source_repo_dir.is_dir():
            pretty_print.print_error(f"No local sources found in {self._source_repo_dir}")
            sys.exit(1)

        pretty_print.print_build("Opening configuration menu...")

        self.container_executor.exec_sh_commands(commands=menuconfig_commands, dirs_to_mount=[(self._repo_dir, "Z")])

    def _prep_clean_srcs(self, prep_srcs_commands: list[str]):
        """
        This function is intended to create a new, clean Linux kernel or U-Boot project.
        After the creation of the project you should create a patch that includes .gitignore and .config.

        Args:
            menuconfig_commands:
                The commands to be executed in a container to prepare a clean project.

        Returns:
            None

        Raises:
            None
        """

        if not self._source_repo_dir.is_dir():
            pretty_print.print_error(f"No local sources found in {self._source_repo_dir}")
            sys.exit(1)

        if (self._source_repo_dir / ".config").is_file():
            pretty_print.print_error(f'Configuration file already exists in {self._source_repo_dir / ".config"}')
            sys.exit(1)

        pretty_print.print_build(f"Preparing clean sources...")

        self.container_executor.exec_sh_commands(
            commands=prep_srcs_commands,
            dirs_to_mount=[(self._repo_dir, "Z")],
            print_commands=True,
        )

    def create_proj_cfg_patch(self):
        """
        This function checks whether there are already git patches for this block and,
        if not, generates an architecture specific configuration patch. This is only possible
        for blocks that have a definition of the function prep_clean_srcs.

        Args:
            None

        Returns:
            None

        Raises:
            AttributeError:
                If the object does not have the method 'prep_clean_srcs'
        """

        if not hasattr(self, "prep_clean_srcs"):
            raise AttributeError(
                f"Object of type {self.__class__.__name__} does not have the expected method 'prep_clean_srcs'"
            )

        # If there are already patches, there is nothing to do
        if self._patch_dir.is_dir():
            return

        # Check if there are uncommited changes in the git repo
        results = self.shell_executor.get_sh_results(["git", "-C", str(self._source_repo_dir), "status", "--porcelain"])
        if results.stdout:
            pretty_print.print_error(
                f"Unable to create architecture specific configuration patch, "
                f"because there are uncommited changes in {self._source_repo_dir}. "
                f"Please commit the changes or clean this block ({self.block_id})."
            )
            sys.exit(1)

        # Prepare clean sources and create patch
        self.prep_clean_srcs()
        pretty_print.print_build("Creating a commit with the clean sources...")
        self.shell_executor.exec_sh_command(["git", "-C", str(self._source_repo_dir), "add", "."])
        self.shell_executor.exec_sh_command(
            ["git", "-C", str(self._source_repo_dir), "commit", "-m", "'Add default config'"]
        )
        self.create_patches()

    def _import_src_tpl(self, template: pathlib.Path):
        """
        Imports the provided source template.

        Args:
            template:
                The source template to be imported

        Returns:
            None

        Raises:
            ValueError:
                If the CSV file that describes the patches has more than one column
        """

        # Import template
        pretty_print.print_build(f"Importing template '{template.name.split('.')[0]}' into the project...")
        self._block_src_dir.mkdir(parents=True)
        with tarfile.open(template, "r:*") as archive:
            # Extract all contents to the output directory
            archive.extractall(path=self._block_src_dir)

        # Import patches into the project configuration file
        try:
            patches_file = self._patch_dir / "patches.csv"
            with open(patches_file, mode="r", newline="") as file:
                reader = csv.reader(file)
                patches = list(reader)

            # Check the entire file before anything is done
            for patch in patches:
                if len(patch) != 1:
                    raise ValueError(f"File '{patches_file}' has more than one column")

            for patch in patches:
                # Add patch to project configuration file
                # ToDo: Maybe the main project configuration file should not be hard coded here
                YAML_Editor.append_list_entry(
                    file=self._project_dir / "project.yml",
                    keys=["blocks", self.block_id, "project", "patches"],
                    data=patch[0],
                )
                # Add patch to currently used project configuration
                if self.block_cfg.project.patches == None:
                    self.block_cfg.project.patches = [patch[0]]
                else:
                    self.block_cfg.project.patches.append(patch[0])

            os.remove(patches_file)
        except FileNotFoundError:
            pass

    def import_req_src_tpl(self):
        """
        This function checks whether there are already sources for this block
        and, if not, asks the user to import a source code template.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # If there are already sources, there is nothing to do
        if self._block_src_dir.is_dir():
            return

        # Check if there are source templates that can be imported for this builder
        templates = list(
            (self._builders_dir / "templates" / "block_srcs" / self.__class__.__name__.lower()).glob("*.tar.gz")
        )
        if not templates:
            pretty_print.print_error(
                f"Block '{self.block_id}' requires source files, "
                f"but the following directory is missing: {self._block_src_dir}"
            )
            sys.exit(1)

        # Let the user select a template
        pretty_print.print_warning(
            f"Block '{self.block_id}' requires source files, but none were found. "
            "Please select one of the following templates:\n"
        )
        for i, item in enumerate(templates):
            print(f"{i + 1}) {item.name.split('.')[0]}")

        try:
            while True:
                choice = input("\nEnter number: ")

                if not re.fullmatch(pattern="\d+", string=choice) or not 0 < int(choice) <= len(templates):
                    print("Invalid choice, please try again.")
                    continue

                choice = int(choice) - 1
                break
        except KeyboardInterrupt:
            print()
            exit(1)

        self._import_src_tpl(template=templates[choice])

    def import_opt_src_tpl(self):
        """
        This function checks whether there are already sources for this block
        and, if not, offers the user to import an optional source code template.
        To avoid bothering the user with this question with every build, it is
        only asked if there are no temp files for this block yet.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # If there are already sources or temp files, there is nothing to do
        if self._block_src_dir.is_dir() or self._block_temp_dir.is_dir():
            return

        # Check if there are source templates that can be imported for this builder
        templates = list(
            (self._builders_dir / "templates" / "block_srcs" / self.__class__.__name__.lower()).glob("*.tar.gz")
        )
        if not templates:
            return

        # Let the user select a template
        pretty_print.print_info(
            f"Optional templates are available for block '{self.block_id}'. "
            "Please select one of the following options:\n"
        )
        print(f"1) no template")
        for i, item in enumerate(templates):
            print(f"{i + 2}) {item.name.split('.')[0]}")

        try:
            while True:
                choice = input("\nEnter number: ")

                if not re.fullmatch(pattern="\d+", string=choice) or not 0 < int(choice) <= len(templates) + 1:
                    print("Invalid choice, please try again.")
                    continue

                choice = int(choice) - 2
                break
        except KeyboardInterrupt:
            print()
            exit(1)

        if choice == -1:
            # The user has chosen not to use a template
            pretty_print.print_build(f"No template will be imported...")
            return
        else:
            self._import_src_tpl(template=templates[choice])

    def clean_repo(self, as_root: bool = False):
        """
        This function cleans the git repo directory.

        Args:
            as_root:
                Set to True if the working directory is to be cleaned by the root user.

        Returns:
            None

        Raises:
            None
        """

        if not str(self._repo_dir).startswith(str(self._block_temp_dir)):
            pretty_print.print_clean(
                f"An external project directory is used for block '{self.block_id}'. It will not be cleaned."
            )
            return

        if not self._repo_dir.exists():
            pretty_print.print_clean("No need to clean the repo directory...")
            return

        if self._source_repo_dir is not None and self._source_repo_dir.exists():
            # Check if there are uncommited changes in the git repo
            results = self.shell_executor.get_sh_results(
                ["git", "-C", str(self._source_repo_dir), "status", "--porcelain"]
            )
            if results.stdout:
                pretty_print.print_warning(
                    f"There are uncommited changes in {self._source_repo_dir}. Do you really want to clean this repo? (y/n) ",
                    end="",
                )
                answer = input("")
                if answer.lower() not in ["y", "Y", "yes", "Yes"]:
                    pretty_print.print_clean("Cleaning abborted...")
                    sys.exit(1)

        if as_root:
            pretty_print.print_clean("Cleaning repo directory as root user...")
        else:
            pretty_print.print_clean("Cleaning repo directory...")

        cleaning_commands = [f"rm -rf {self._repo_dir}/* {self._repo_dir}/.* 2> /dev/null || true"]

        self.container_executor.exec_sh_commands(
            commands=cleaning_commands, dirs_to_mount=[(self._repo_dir, "Z")], run_as_root=as_root
        )

        # Remove empty repo directory
        self._repo_dir.rmdir()

        # Reset timestamps
        self._build_log.del_logged_timestamp(identifier=f"function-apply_patches-success")

    def clean_output(self):
        """
        This function cleans the output directory.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        if not self._output_dir.exists():
            pretty_print.print_clean("No need to clean the output directory...")
            return

        pretty_print.print_clean("Cleaning output directory...")

        cleaning_commands = [f"rm -rf {self._output_dir}/* {self._output_dir}/.* 2> /dev/null || true"]

        self.container_executor.exec_sh_commands(commands=cleaning_commands, dirs_to_mount=[(self._output_dir, "Z")])

        # Remove empty output directory
        self._output_dir.rmdir()

    def clean_work(self, as_root: bool = False):
        """
        This function cleans the work directory.

        Args:
            as_root:
                Set to True if the working directory is to be cleaned by the root user.

        Returns:
            None

        Raises:
            None
        """

        if not self._work_dir.exists():
            pretty_print.print_clean("No need to clean the work directory...")
            return

        if as_root:
            pretty_print.print_clean("Cleaning work directory as root user...")
        else:
            pretty_print.print_clean("Cleaning work directory...")

        cleaning_commands = [f"rm -rf {self._work_dir}/* {self._work_dir}/.* 2> /dev/null || true"]

        self.container_executor.exec_sh_commands(
            commands=cleaning_commands, dirs_to_mount=[(self._work_dir, "Z")], run_as_root=as_root
        )

        # Remove empty work directory
        self._work_dir.rmdir()

    def clean_download(self):
        """
        This function cleans the download directory.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        if not self._download_dir.exists():
            pretty_print.print_clean("No need to clean the download directory...")
            return

        pretty_print.print_clean("Cleaning download directory...")

        cleaning_commands = [f"rm -rf {self._download_dir}/* {self._download_dir}/.* 2> /dev/null || true"]

        self.container_executor.exec_sh_commands(commands=cleaning_commands, dirs_to_mount=[(self._download_dir, "Z")])

        # Remove empty download directory
        self._download_dir.rmdir()

    def clean_dependencies(self, dependency: str = ""):
        """
        This function cleans the dependencies directory.

        Args:
            dependency:
                The dependency to be cleaned. If not specified, all dependencies are cleaned.

        Returns:
            None

        Raises:
            None
        """

        if not (self._dependencies_dir / dependency).exists():
            if dependency == "":
                pretty_print.print_clean("No need to clean the dependencies directory...")
            else:
                pretty_print.print_clean(f"No need to clean the dependencies subdirectory {dependency}...")
            return

        if dependency == "":
            pretty_print.print_clean("Cleaning dependencies directory...")
        else:
            pretty_print.print_clean(f"Cleaning dependencies subdirectory {dependency}...")

        cleaning_commands = [
            f"rm -rf {self._dependencies_dir}/{dependency}/* "
            f"{self._dependencies_dir}/{dependency}/.* 2> /dev/null || true"
        ]

        self.container_executor.exec_sh_commands(
            commands=cleaning_commands, dirs_to_mount=[(self._dependencies_dir, "Z")]
        )

        # Remove empty download directory
        if dependency == "":
            self._dependencies_dir.rmdir()

    def clean_block_temp(self):
        """
        This function cleans the temp directory of a block.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        if not self._block_temp_dir.exists():
            pretty_print.print_clean(f"No need to clean the temp directory of block {self.block_id}...")
            return

        pretty_print.print_clean(f"Cleaning temp directory of block {self.block_id}...")

        cleaning_commands = [f"rm -rf {self._block_temp_dir}/* {self._block_temp_dir}/.* 2> /dev/null || true"]

        self.container_executor.exec_sh_commands(
            commands=cleaning_commands, dirs_to_mount=[(self._block_temp_dir, "Z")]
        )

        # Remove empty temp directory
        self._block_temp_dir.rmdir()
