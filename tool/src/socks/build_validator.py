import os
import typing
import pathlib
import shutil
import pydantic
import yaml

from socks.shell_executor import Shell_Executor


class Build_Validator:
    """
    A class with tools for checking whether a component needs to be (re)built
    """

    def __init__(self, project_cfg: pydantic.BaseModel, model_class: type[object], block_temp_dir: pathlib.Path):
        self._project_cfg = project_cfg

        # File with the project configuration that was used for this block in the last build sequence
        self._prev_build_cfg_file = block_temp_dir / ".previous_build_config.yml"
        # File with the project configuration that was used for this block in the last prepare sequence
        self._prev_prep_cfg_file = block_temp_dir / ".previous_prepare_config.yml"

        # Read the project configuration that was used for this block in the last build or prepare sequence, if any
        try:
            with self._prev_build_cfg_file.open("r") as f:
                prev_cfg = yaml.safe_load(f)
            self._prev_build_cfg = model_class(**prev_cfg)
        except (pydantic.ValidationError, FileNotFoundError):
            self._prev_build_cfg = None
        try:
            with self._prev_prep_cfg_file.open("r") as f:
                prev_cfg = yaml.safe_load(f)
            self._prev_prep_cfg = model_class(**prev_cfg)
        except (pydantic.ValidationError, FileNotFoundError):
            self._prev_prep_cfg = None

    @staticmethod
    def _find_last_modified_file(
        search_list: list[pathlib.Path], ignore_list: list[pathlib.Path] = None
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
    def check_rebuild_bc_timestamp(
        src_search_list: list[pathlib.Path],
        src_ignore_list: list[pathlib.Path] = None,
        out_timestamp: float = None,
        out_search_list: list[pathlib.Path] = None,
        out_ignore_list: list[pathlib.Path] = None,
    ) -> bool:
        """
        Uses timestamps to check whether some file(s) need to be rebuilt.

        Args:
            src_search_list:
                List of directories and files to be searched for the most
                recently modified source file.
            src_ignore_list:
                List of directories and files to be ignored when searching
                for the most recently modified source file.
            out_timestamp:
                Timestamp of the last modification of output files. If this
                parameter is provided, the parameters out_search_list and
                out_ignore_list are ignored.
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
        latest_src_file = Build_Validator._find_last_modified_file(
            search_list=src_search_list, ignore_list=src_ignore_list
        )

        # Find last modified output file
        if out_search_list and out_timestamp is None:
            latest_out_file = Build_Validator._find_last_modified_file(
                search_list=out_search_list, ignore_list=out_ignore_list
            )
        else:
            latest_out_file = None

        latest_src_mod = None
        if latest_src_file:
            latest_src_mod = latest_src_file.stat(follow_symlinks=False).st_mtime

        latest_out_mod = None
        if out_timestamp is not None:
            latest_out_mod = out_timestamp
        elif latest_out_file:
            latest_out_mod = latest_out_file.stat(follow_symlinks=False).st_mtime

        # If there are source and output files, check whether a rebuild is required
        if latest_src_mod is not None and latest_out_mod is not None:
            return latest_src_mod > latest_out_mod

        # A rebuild is required if source or output files are missing
        else:
            return True

    @staticmethod
    def check_rebuild_bc_timestamp_faster(
        src_search_list: list[pathlib.Path],
        src_ignore_list: list[pathlib.Path] = None,
        out_search_list: list[pathlib.Path] = None,
        out_ignore_list: list[pathlib.Path] = None,
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

        shell_executor = Shell_Executor()

        # Find last modified source file
        src_search_str = " ".join(list(map(str, src_search_list)))
        if src_ignore_list:
            src_ignore_str = f'\( -path {" -prune -o -path ".join(list(map(str, src_ignore_list)))} -prune \) -o'
        else:
            src_ignore_str = ""

        results = shell_executor.get_sh_results(
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

        results = shell_executor.get_sh_results(
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

    def check_rebuild_bc_config(self, keys: list[list[str]], accept_prep: bool = False) -> bool:
        """
        Uses the project configuration to check whether some file(s) need to be rebuilt.

        Args:
            keys:
                A list containing lists of strings. Each list of strings represents a key sequence in the dicts
                that is to be compared.
            accept_prep:
                Whether a configuration from a prepare sequence should be evaluated if no configuration from a
                build sequence exists. Should be True in places where this function is executed as part of a
                prepare sequence.

        Returns:
            True if a rebuild is required, i.e. if the checked configuration parameters have changed. False if
            a rebuild is not required, i.e. if the checked configuration parameters are unchanged.

        Raises:
            None
        """

        # Convert pydantic models to dicts
        current_cfg_dict = self._project_cfg.model_dump()
        try:
            if accept_prep and self._prev_build_cfg is None:
                previous_cfg_dict = self._prev_prep_cfg.model_dump()
            else:
                previous_cfg_dict = self._prev_build_cfg.model_dump()
        except:
            # A rebuild is required if the project configuration that was used for the last build or
            # prepare sequence cannot be loaded
            return True

        for key_list in keys:
            # Iterate over all keys in the list to find the units to be compared
            to_compare_current = current_cfg_dict
            to_compare_previous = previous_cfg_dict
            for key in key_list:
                to_compare_current = to_compare_current[key]
                to_compare_previous = to_compare_previous[key]

            # Compare units
            if to_compare_current != to_compare_previous:
                return True

        return False

    def _save_project_cfg(self, file: pathlib.Path):
        """
        Writes the project configuration that is currently used for this block to a file. The file is only written
        if the current config is different to the one already saved in the file. This makes it possible to use
        the checksum of this file to check when the project configuration of this block was last changed.

        Args:
            file:
                File to which the configuration is to be written

        Returns:
            None

        Raises:
            None
        """

        # Create a list of lists with all top level keys of the block specific project config
        cfg_keys = list(self._project_cfg.model_dump().keys())
        cfg_key_lists = [[key] for key in cfg_keys]

        # Compare the entire block specific project config
        if not self.check_rebuild_bc_config(keys=cfg_key_lists, accept_prep=True):
            # The file does not need to be written if the current config is the same as the old one
            return

        # Write to file
        with file.open("w") as f:
            f.write("# This file was created automatically, please do not modify!\n")
            f.write(yaml.dump(self._project_cfg.model_dump()))

    def save_project_cfg_prepare(self):
        """
        Writes the project configuration that is currently used for preparing this block to a file.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Rename config file so that it can still be used
        if self._prev_build_cfg_file.exists():
            shutil.move(self._prev_build_cfg_file, self._prev_prep_cfg_file)

        self._save_project_cfg(self._prev_prep_cfg_file)

    def save_project_cfg_build(self):
        """
        Writes the project configuration that is currently used for building this block to a file.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Rename config file so that it can still be used
        if self._prev_prep_cfg_file.exists():
            shutil.move(self._prev_prep_cfg_file, self._prev_build_cfg_file)

        self._save_project_cfg(self._prev_build_cfg_file)
