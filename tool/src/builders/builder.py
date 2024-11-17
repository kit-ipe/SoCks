import typing
import os
import pathlib
import shutil
import sys
import datetime
from dateutil import parser
import urllib
import requests
import validators
import tqdm
import tarfile
import re
import hashlib
import time
import pydantic

import socks.pretty_print as pretty_print
from socks.shell_command_runners import Shell_Command_Runners
from socks.containerization import Containerization


class Builder(Containerization):
    """
    Base class for all builder classes
    """

    def __init__(
        self,
        project_cfg: dict,
        project_cfg_files: list,
        model_class,
        socks_dir: pathlib.Path,
        project_dir: pathlib.Path,
        block_id: str,
        block_description: str,
    ):
        self.block_id = block_id
        self.block_description = block_description
        self.pre_build_warnings = []

        # Initialize block model
        try:
            self.project_cfg = model_class(**project_cfg)
        except pydantic.ValidationError as e:
            for err in e.errors():
                pretty_print.print_error(f"{err['msg']} when analyzing {' -> '.join(err['loc'])}")
            sys.exit(1)

        self.block_cfg = getattr(self.project_cfg.blocks, block_id)

        # Find project sources for this block
        if hasattr(self.block_cfg.project, "build_srcs"):
            if isinstance(self.block_cfg.project.build_srcs, list):
                self._local_source_dirs, self._source_repos = self._eval_mult_prj_srcs()
            else:
                self._local_source_dir, self._source_repo = self._eval_single_prj_src()

        # Host user
        self._host_user = os.getlogin()
        self._host_user_id = os.getuid()

        # Local git branches
        self._git_local_ref_branch = "__ref"
        self._git_local_dev_branch = "__temp"

        # SoCks directorys (ToDo: If there is more like this needed outside of the blocks, maybe there should be a SoCks or tool class)
        self._socks_dir = socks_dir
        self._container_dir = self._socks_dir / "container"

        # Project directories
        self._project_dir = project_dir
        self._project_src_dir = self._project_dir / "src"
        self._project_temp_dir = self._project_dir / "temp"
        self._block_src_dir = self._project_src_dir / self.block_id
        self._block_temp_dir = self._project_temp_dir / self.block_id
        self._patch_dir = self._block_src_dir / "patches"
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
                pathlib.Path(urllib.parse.urlparse(url=self._source_repo['url']).path).stem
                + "-"
                + self._source_repo['branch'])
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
        # A list of all project configuration files used. These files should only be used to determine whether a rebuild is necessary!
        self._project_cfg_files = project_cfg_files
        # ASCII file with all patches in the order in which they are to be applied
        self._patch_list_file = self._patch_dir / "patches.cfg"
        # Flag to remember if patches have already been applied
        self._repo_init_done_flag = self._block_temp_dir / ".repoinitdone"
        # Flag to remember if patches have already been applied
        self._patches_applied_flag = self._block_temp_dir / ".patchesapplied"
        # File for saving the checksum of the imported, pre-built block package
        self._source_pb_md5_file = self._work_dir / "source_pb.md5"

        # Containerization
        container_image = f"{self.block_cfg.container.image}:{self.block_cfg.container.tag}"
        super().__init__(
            container_tool=self.project_cfg.external_tools.container_tool,
            container_image=container_image,
            container_file=self._container_dir / f"{container_image}.containerfile",
        )

    @staticmethod
    def _find_last_modified_file(
        search_list: typing.List[pathlib.Path], ignore_list: typing.List[pathlib.Path] = None
    ) -> typing.Optional[pathlib.Path]:
        """
        Find the last modified file in a list of directories, whereby files and directories can be ignored.

        Args:
            search_list:
                List of directories and files to be searched for the most
                recently modified file.
            ignore_list:
                List of directories and files to be ignored when searching
                for the most recently modified file.

        Returns:
            The most recently modified file.

        Raises:
            None
        """

        # Initialize variables to keep track of the most recently modified file
        latest_file = None
        latest_mtime = 0

        # Convert the ignore list to absolute paths for comparison
        if ignore_list:
            ignore_list = {p.resolve() for p in ignore_list}

        for search_path in search_list:
            # Handle file or symlink
            if search_path.is_file() or search_path.is_symlink():
                file_path = search_path.resolve()

                # Skip if the file is in the ignore list
                if ignore_list:
                    if file_path in ignore_list:
                        continue

                # Skip broken symlinks
                if file_path.is_symlink() and not file_path.exists():
                    continue

                # Get the modification time of the file
                file_mtime = file_path.stat(follow_symlinks=False).st_mtime

                # Update if this file is more recently modified
                if file_mtime > latest_mtime:
                    latest_mtime = file_mtime
                    latest_file = file_path

                continue

            # Handle directory, including its subdirectories
            for dir_path, dir_names, file_names in os.walk(
                search_path
            ):  # ToDo: In Python 3.12 there should be a pathlib Version of walk
                current_dir = pathlib.Path(dir_path).resolve()

                # Skip if the current directory is in the ignore list
                if ignore_list:
                    if current_dir in ignore_list:
                        continue

                # Remove any subdirectories that are in the ignore list to prevent descending into them
                if ignore_list:
                    dir_names[:] = [d for d in dir_names if (current_dir / d).resolve() not in ignore_list]

                # Iterate over files in the current directory
                for filename in file_names:
                    file_path = current_dir / filename

                    # Skip if the file is in the ignore list
                    if ignore_list:
                        if file_path in ignore_list:
                            continue

                    # Skip broken symlinks
                    if file_path.is_symlink() and not file_path.exists():
                        continue

                    # Get the modification time of the file
                    file_mtime = file_path.stat(follow_symlinks=False).st_mtime

                    # Update if this file is more recently modified
                    if file_mtime > latest_mtime:
                        latest_mtime = file_mtime
                        latest_file = file_path

        return latest_file

    @staticmethod
    def _check_rebuild_required(
        src_search_list: typing.List[pathlib.Path],
        src_ignore_list: typing.List[pathlib.Path] = None,
        out_search_list: typing.List[pathlib.Path] = None,
        out_ignore_list: typing.List[pathlib.Path] = None,
    ) -> bool:
        """
        Check whether some file(s) needs to be rebuilt.

        Args:
            src_search_list:
                List of directories and files to be searched for the most
                recently modified source file.
            src_ignore_list:
                List of directories and files to be ignored when searching
                for the most recently modified source file.
            out_search_list:
                List of directories and files to be searched for the most
                recently modified output file.
            out_ignore_list:
                List of directories and files to be ignored when searching
                for the most recently modified output file.

        Returns:
            True if a rebuild is required, i.e. if the source files are newer
            than the output files. False if a rebuild is not required, i.e.
            if the output files are newer than the source files.

        Raises:
            None
        """

        # Remove non-existing files and directories
        if src_search_list:
            src_search_list = [path for path in src_search_list if path.exists()]
        if src_ignore_list:
            src_ignore_list = [path for path in src_ignore_list if path.exists()]
        if out_search_list:
            out_search_list = [path for path in out_search_list if path.exists()]
        if out_ignore_list:
            out_ignore_list = [path for path in out_ignore_list if path.exists()]

        # Find last modified source file
        latest_src_file = Builder._find_last_modified_file(search_list=src_search_list, ignore_list=src_ignore_list)

        # Find last modified output file
        if out_search_list:
            latest_out_file = Builder._find_last_modified_file(search_list=out_search_list, ignore_list=out_ignore_list)
        else:
            latest_out_file = None

        # If there are source and output files, check whether a rebuild is required
        if latest_src_file and latest_out_file:
            return (
                latest_src_file.stat(follow_symlinks=False).st_mtime
                > latest_out_file.stat(follow_symlinks=False).st_mtime
            )

        # A rebuild is required if source or output files are missing
        else:
            return True

    @staticmethod
    def _check_rebuild_required_faster(
        src_search_list: typing.List[pathlib.Path],
        src_ignore_list: typing.List[pathlib.Path] = None,
        out_search_list: typing.List[pathlib.Path] = None,
        out_ignore_list: typing.List[pathlib.Path] = None,
    ) -> bool:
        """
        Check whether some file(s) needs to be rebuilt.

        Args:
            src_search_list:
                List of directories and files to be searched for the most
                recently modified source file.
            src_ignore_list:
                List of directories and files to be ignored when searching
                for the most recently modified source file.
            out_search_list:
                List of directories and files to be searched for the most
                recently modified output file.
            out_ignore_list:
                List of directories and files to be ignored when searching
                for the most recently modified output file.

        Returns:
            True if a rebuild is required, i.e. if the source files are newer
            than the output files. False if a rebuild is not required, i.e.
            if the output files are newer than the source files.

        Raises:
            None
        """

        # Find last modified source file
        src_search_str = " ".join(list(map(str, src_search_list)))
        if src_ignore_list:
            src_ignore_str = f'\( -path {" -prune -o -path ".join(list(map(str, src_ignore_list)))} -prune \) -o'
        else:
            src_ignore_str = ""

        results = Shell_Command_Runners.get_sh_results(
            [
                "find",
                src_search_str,
                src_ignore_str,
                "\( -type f -o -type l \) -print0",
                "2>",
                "/dev/null",
                "|",
                "xargs",
                "-0",
                "stat",
                "-L",
                "--format",
                "'%Y'",
                "2>",
                "/dev/null",
                "|",
                "sort",
                "-nr",
            ]
        )
        latest_src_mod = results.stdout.splitlines()[0]

        # Find last modified output file
        out_search_str = " ".join(list(map(str, out_search_list)))
        if out_ignore_list:
            out_ignore_str = f'\( -path {" -prune -o -path ".join(list(map(str, out_ignore_list)))} -prune \) -o'
        else:
            out_ignore_str = ""

        results = Shell_Command_Runners.get_sh_results(
            [
                "find",
                out_search_str,
                out_ignore_str,
                "\( -type f -o -type l \) -print0",
                "2>",
                "/dev/null",
                "|",
                "xargs",
                "-0",
                "stat",
                "-L",
                "--format",
                "'%Y'",
                "2>",
                "/dev/null",
                "|",
                "sort",
                "-nr",
            ]
        )
        latest_out_mod = results.stdout.splitlines()[0]

        # If there are source and output files, check whether a rebuild is required
        if latest_src_mod and latest_out_mod:
            return int(latest_src_mod) > int(latest_out_mod)

        # A rebuild is required if source or output files are missing
        else:
            return True

    def _eval_single_prj_src(self) -> typing.Tuple[pathlib.Path, dict]:
        """
        Process the source section of a block with a single source.

        Args:
            None

        Returns:
            None

        Raises:
            ValueError: If the block configuration does not contain a valid reference to a block project source
        """

        if urllib.parse.urlparse(self.block_cfg.project.build_srcs.source).scheme == "file":
            # Local project sources are used for this block
            local_source_dir = pathlib.Path(urllib.parse.urlparse(self.block_cfg.project.build_srcs.source).path)
            if not local_source_dir.is_dir():
                pretty_print.print_error(
                    f"The following setting in blocks/{self.block_id}/project/build_srcs/source does not point to a directory: {self.block_cfg.project.build_srcs.source}"
                )
                sys.exit(1)
            self.pre_build_warnings.append(
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
                source_repo = {"url": self.block_cfg.project.build_srcs.source, "branch": self.block_cfg.project.build_srcs.branch}
        else:
            raise ValueError(
                "The following string is not a valid reference to a block project source: "
                f"{self.block_cfg.project.build_srcs.source}. Only URI schemes 'https', 'http', 'ssh', and 'file' "
                "are supported."
            )

        return local_source_dir, source_repo

    def _eval_mult_prj_srcs(self) -> typing.Tuple[typing.List[pathlib.Path], typing.List[dict]]:
        """
        Process the source section of a block with multiple sources.

        Args:
            None

        Returns:
            None

        Raises:
            ValueError: If the block configuration does not contain a valid reference to a block project source
        """

        source_repos = []
        local_source_dirs = []

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
                self.pre_build_warnings.append(
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
                        {"url": self.block_cfg.project.build_srcs[index].source, "branch": self.block_cfg.project.build_srcs[index].branch}
                    )
            else:
                raise ValueError(
                    "The following string is not a valid reference to a block project source: "
                    f"{self.block_cfg.project.build_srcs[index].source}. Only URI schemes 'https', 'http', 'ssh', and 'file' "
                    "are supported."
                )

        return local_source_dirs, source_repos

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

        results = Shell_Command_Runners.get_sh_results(["git", "-C", str(self._project_dir), "rev-parse", "HEAD"])
        build_info = build_info + f"GIT_COMMIT_SHA: {results.stdout.splitlines()[0]}\n"

        results = Shell_Command_Runners.get_sh_results(
            ["git", "-C", str(self._project_dir), "rev-parse", "--abbrev-ref", "HEAD"]
        )
        git_ref_name = results.stdout.splitlines()[0]
        if git_ref_name == "HEAD":
            results = Shell_Command_Runners.get_sh_results(
                ["git", "-C", str(self._project_dir), "describe", "--exact-match", git_ref_name]
            )
            git_tag_name = results.stdout.splitlines()[0]
            if results.returncode == 0:
                build_info = build_info + f"GIT_TAG_NAME: {git_tag_name}\n"
        else:
            build_info = build_info + f"GIT_BRANCH_NAME: {git_ref_name}\n"

        results = Shell_Command_Runners.get_sh_results(["git", "-C", str(self._project_dir), "status", "--porcelain"])
        if results.stdout:
            build_info = build_info + "GIT_IS_REPO_CLEAN: false\n\n"
        else:
            build_info = build_info + "GIT_IS_REPO_CLEAN: true\n\n"

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
            results = Shell_Command_Runners.get_sh_results(["hostname"])
            build_info = build_info + f"MANUAL_BUILD_HOST: {results.stdout.splitlines()[0]}\n"
            results = Shell_Command_Runners.get_sh_results(["id", "-un"])
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

        # Skip all operations if the repo has already been initialized
        if self._repo_init_done_flag.exists():
            pretty_print.print_build("No need to initialize the local repo...")
            return

        if self._source_repo is not None and not isinstance(self._source_repo, dict):
            # ToDo: Maybe at some point this function should support initializing multiple repos as well, but I am not sure yet if this is really needed
            pretty_print.print_error(
                f"This function expects a single object and not an array in blocks/{self.block_id}/project/build_srcs."
            )
            sys.exit(1)

        pretty_print.print_build("Initializing local repo...")

        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Check if the source code of this block project is online and needs to be downloaded
        if self._source_repo is not None:
            self._repo_dir.mkdir(parents=True, exist_ok=True)
            # Clone the repo
            Shell_Command_Runners.run_sh_command(
                [
                    "git",
                    "clone",
                    "--recursive",
                    "--branch",
                    self._source_repo["branch"],
                    self._source_repo["url"],
                    str(self._source_repo_dir),
                ]
            )

        results = Shell_Command_Runners.get_sh_results(["git", "-C", str(self._source_repo_dir), "branch", "-a"])
        if not (
            f"  {self._git_local_ref_branch}" in results.stdout.splitlines()
            or f"* {self._git_local_ref_branch}" in results.stdout.splitlines()
        ):
            print("In if")
            # Create new branch self._git_local_ref_branch. This branch is used as a reference where all existing patches are applied to the git sources
            Shell_Command_Runners.run_sh_command(
                ["git", "-C", str(self._source_repo_dir), "switch", "-c", self._git_local_ref_branch]
            )
        if not (
            f"  {self._git_local_dev_branch}" in results.stdout.splitlines()
            or f"* {self._git_local_dev_branch}" in results.stdout.splitlines()
        ):
            # Create new branch self._git_local_dev_branch. This branch is used as the local development branch. New patches can be created from this branch.
            Shell_Command_Runners.run_sh_command(
                ["git", "-C", str(self._source_repo_dir), "switch", "-c", self._git_local_dev_branch]
            )

        # Create the flag if it doesn't exist and update the timestamps
        self._repo_init_done_flag.touch()

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
        result_new_commits = Shell_Command_Runners.get_sh_results(
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
        result_new_patches = Shell_Command_Runners.get_sh_results(
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
        # Add newly created patches to self._patch_list_file
        for line in result_new_patches.stdout.splitlines():
            new_patch = line.rpartition("/")[2]
            print(f"Patch {new_patch} was created")
            with self._patch_list_file.open("a") as f:
                print(new_patch, file=f, end="\n")
        # Synchronize the branches ref and dev to be able to detect new commits in the future
        Shell_Command_Runners.run_sh_command(
            ["git", "-C", str(self._source_repo_dir), "checkout", self._git_local_ref_branch], visible_lines=0
        )
        Shell_Command_Runners.run_sh_command(
            ["git", "-C", str(self._source_repo_dir), "merge", self._git_local_dev_branch], visible_lines=0
        )
        Shell_Command_Runners.run_sh_command(
            ["git", "-C", str(self._source_repo_dir), "checkout", self._git_local_dev_branch], visible_lines=0
        )

    def apply_patches(self):
        """
        This function iterates over all patches listed in self._patch_list_file and
        applies them to the repo.

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
                for patch in f:
                    if patch:  # If this line in the file is not empty
                        # Apply patch
                        Shell_Command_Runners.run_sh_command(
                            ["git", "-C", str(self._source_repo_dir), "am", str(self._patch_dir / patch)]
                        )

        # Update the branch self._git_local_ref_branch so that it contains the applied patches and is in sync with self._git_local_dev_branch. This is important to be able to create new patches.
        Shell_Command_Runners.run_sh_command(
            ["git", "-C", str(self._source_repo_dir), "checkout", self._git_local_ref_branch], visible_lines=0
        )
        Shell_Command_Runners.run_sh_command(
            ["git", "-C", str(self._source_repo_dir), "merge", self._git_local_dev_branch], visible_lines=0
        )
        Shell_Command_Runners.run_sh_command(
            ["git", "-C", str(self._source_repo_dir), "checkout", self._git_local_dev_branch], visible_lines=0
        )

        # Create the flag if it doesn't exist and update the timestamps
        self._patches_applied_flag.touch()

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

        # Progress callback function to show a status bar
        def download_progress(block_num, block_size, total_size):
            if download_progress.t is None:
                download_progress.t = tqdm.tqdm(total=total_size, unit="B", unit_scale=True, unit_divisor=1024)
            downloaded = block_num * block_size
            download_progress.t.update(downloaded - download_progress.t.n)

        # Send a HEAD request to get the HTTP headers
        response = requests.head(self.block_cfg.project.import_src, allow_redirects=True)

        if response.status_code == 404:
            # File not found
            pretty_print.print_error(
                f"The following file could not be downloaded: {self.block_cfg.project.import_src}\nStatus code {response.status_code} (File not found)"
            )
            sys.exit(1)
        elif response.status_code != 200:
            # Unexpected status code
            pretty_print.print_error(
                f"The following file could not be downloaded: {self.block_cfg.project.import_src}\nUnexpected status code {response.status_code}"
            )
            sys.exit(1)

        # Get timestamp of the file online
        last_mod_online = response.headers.get("Last-Modified")
        if last_mod_online:
            last_mod_online_timestamp = parser.parse(last_mod_online).timestamp()
        else:
            pretty_print.print_error(f"No 'Last-Modified' header found for {self.block_cfg.project.import_src}")
            sys.exit(1)

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
        download_progress.t = None
        filename = self.block_cfg.project.import_src.rpartition("/")[2]
        urllib.request.urlretrieve(
            url=self.block_cfg.project.import_src, filename=self._download_dir / filename, reporthook=download_progress
        )
        if download_progress.t:
            download_progress.t.close()

    def import_prebuilt(self):
        """
        Imports a pre-built block package. If a file URI is provided, this directory is used locally. If a http or
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
                pretty_print.print_error(f"Not exactly one file in {self._download_dir}.")
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

        # Copy block package
        shutil.copy(prebuilt_block_package, self._output_dir / prebuilt_block_package.name)

        # Extract pre-built files
        with tarfile.open(self._output_dir / prebuilt_block_package.name, "r:*") as archive:
            # Extract all contents to the output directory
            archive.extractall(path=self._output_dir)

        # Save checksum in file
        with self._source_pb_md5_file.open("w") as f:
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

        block_pkg_path = self._output_dir / f"{self.block_id}.tar.gz"

        # Check whether there is something to export
        if not self._output_dir.is_dir() or not any(self._output_dir.iterdir()):
            pretty_print.print_error(
                f"Unable to export block package. The following director does not exist or is empty: {self._output_dir}"
            )
            sys.exit(1)

        # Check whether a package needs to be created
        if not Builder._check_rebuild_required(
            src_search_list=self._project_cfg_files + [self._output_dir],
            src_ignore_list=[block_pkg_path],
            out_search_list=[block_pkg_path],
        ):
            pretty_print.print_build("No need to export block package. No altered source files detected...")
            return

        block_pkg_path.unlink(missing_ok=True)

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
            block_pkg_rel_path = getattr(self.block_cfg.project.dependencies, dependency)
            if block_pkg_rel_path is None:
                continue
            block_pkg_path = self._project_dir / block_pkg_rel_path
            import_path = self._dependencies_dir / dependency
            block_pkg_md5_file = self._dependencies_dir / f"block_pkg_{dependency}.md5"

            # Check whether the file to be imported exists
            if not block_pkg_path.is_file():
                pretty_print.print_error(
                    f"Unable to import block package. The following file does not exist: {block_pkg_path}"
                )
                sys.exit(1)

            # Check whether the file is a tar.gz archive
            if block_pkg_path.name.partition(".")[2] != "tar.gz":
                pretty_print.print_error(
                    f'Unable to import block package. The following archive type is not supported: {block_pkg_path.name.partition(".")[2]}'
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

        super().start_container(potential_mounts=potential_mounts)

    def _run_menuconfig(self, menuconfig_commands: typing.List[str]):
        """
        Opens the menuconfig tool to enable interactive configuration of the project.

        Args:
            menuconfig_commands:
                The commands to be executed in a container to configure U-Boot interactively.

        Returns:
            None

        Raises:
            None
        """

        if not self._source_repo_dir.is_dir():
            pretty_print.print_error(f"No local sources found in {self._source_repo_dir}")
            sys.exit(1)

        pretty_print.print_build("Opening configuration menu...")

        self.run_containerizable_sh_command(
            commands=menuconfig_commands, dirs_to_mount=[(self._repo_dir, "Z"), (self._output_dir, "Z")]
        )

    def _prep_clean_srcs(self, prep_srcs_commands: typing.List[str]):
        """
        This function is intended to create a new, clean Linux kernel or U-Boot project. After the creation of the project you should create a patch that includes .gitignore and .config.

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

        self.run_containerizable_sh_command(
            commands=prep_srcs_commands, dirs_to_mount=[(self._repo_dir, "Z"), (self._output_dir, "Z")]
        )

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

        if not str(self._repo_dir).startswith(str(self._block_temp_dir)):
            pretty_print.print_clean(
                f"An external project directory is used for block '{self.block_id}'. It will not be cleaned."
            )
            return

        if not self._repo_dir.exists():
            pretty_print.print_clean("No need to clean the repo directory...")
            return

        # Check if there are uncommited changes in the git repo
        results = Shell_Command_Runners.get_sh_results(
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

        pretty_print.print_clean("Cleaning repo directory...")

        cleaning_commands = [f"rm -rf {self._repo_dir}/* {self._repo_dir}/.* 2> /dev/null || true"]

        self.run_containerizable_sh_command(commands=cleaning_commands, dirs_to_mount=[(self._repo_dir, "Z")])

        # Remove flag
        self._patches_applied_flag.unlink(missing_ok=True)

        # Remove empty repo directory
        self._repo_dir.rmdir()

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

        self.run_containerizable_sh_command(commands=cleaning_commands, dirs_to_mount=[(self._output_dir, "Z")])

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

        self.run_containerizable_sh_command(
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

        self.run_containerizable_sh_command(commands=cleaning_commands, dirs_to_mount=[(self._download_dir, "Z")])

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

        self.run_containerizable_sh_command(commands=cleaning_commands, dirs_to_mount=[(self._dependencies_dir, "Z")])

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

        self.run_containerizable_sh_command(commands=cleaning_commands, dirs_to_mount=[(self._block_temp_dir, "Z")])

        # Remove empty temp directory
        self._block_temp_dir.rmdir()
