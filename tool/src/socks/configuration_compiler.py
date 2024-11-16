import typing
import sys
import pathlib
import yaml
import re

import socks.pretty_print as pretty_print


class Configuration_Compiler:
    """
    A class to compile the project configuration
    """

    @staticmethod
    def _find_file(file_name: str, search_list: typing.List[pathlib.Path]) -> pathlib.Path:
        """
        Find file in search paths. Subdirectories are not searched.

        Args:
            file_name:
                Name of file to find.
            search_list:
                List of paths to be searched.

        Returns:
            The file that was found.

        Raises:
            FileNotFoundError: If the file could not be found.
        """

        for path in search_list:
            # Check if the provided path exists
            if not path.is_dir():
                pretty_print.print_error(f"The following path does not exist: {path}")
                sys.exit(1)
            # Iterate over all items in the path
            for item in path.iterdir():
                if item.is_file() and item.name == file_name:
                    # Return found file
                    return item

        # Raise an exception if the file could not be found
        raise FileNotFoundError(f"Unable to find {file_name}")

    @staticmethod
    def _merge_dicts(target: dict, source: dict) -> dict:
        """
        Recursively merge two dictionaries.

        Args:
            target:
                Target dictionary that receives values from the source dictionary.
            source:
                Source dictionary that overwrites values in the target dictionary.

        Returns:
            Merged target dictionary.

        Raises:
            None
        """

        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                # If both values are dictionaries, merge them recursively
                target[key] = Configuration_Compiler._merge_dicts(target[key], value)
            elif key in target and isinstance(target[key], list) and isinstance(value, list):
                # If both values are lists, merge them without duplicating elements
                target[key] = list(set(target[key] + value))
            else:
                # If the value is not a dict or a list or if the key is not yet in the result, simply assign the value
                target[key] = value

        return target

    @staticmethod
    def _merge_cfg_files(
        config_file_name: str, socks_dir: pathlib.Path, project_dir: pathlib.Path
    ) -> typing.Tuple[dict, list]:
        """
        Recursively merge project configuration YAML files by tracing the import keys.

        Args:
            config_file_name:
                Name of the project configuration file to operate on.
            socks_dir:
                Path of the SoCks tool.
            project_dir:
                Path of the SoCks project.

        Returns:
            Fully assembled project configuration.

        Raises:
            None
        """

        try:
            config_file = Configuration_Compiler._find_file(
                file_name=config_file_name, search_list=[socks_dir / "templates" / "project_configuration", project_dir]
            )  # ToDo: I think these paths should not be hard coded here
        except FileNotFoundError as e:
            print(repr(e))
            sys.exit(1)

        with config_file.open("r") as f:
            cfg_layer = yaml.safe_load(f)

        # Add file to list of read configuration files
        read_files = [config_file]

        # Directly return the cfg layer if it doesn't contain an 'import' key
        gathered_cfg = cfg_layer

        if "import" in cfg_layer:
            for file_name in cfg_layer["import"]:
                # Recursively merge the so far composed return value with the file to be imported
                cfg_buffer, files_buffer = Configuration_Compiler._merge_cfg_files(
                    config_file_name=file_name, socks_dir=socks_dir, project_dir=project_dir
                )
                gathered_cfg = Configuration_Compiler._merge_dicts(target=cfg_buffer, source=gathered_cfg)
                read_files = read_files + files_buffer
            # Remove the 'import' key from the so far composed configuration, as it is no longer needed
            del gathered_cfg["import"]

        return gathered_cfg, read_files

    @staticmethod
    def _resolve_placeholders(project_cfg: dict, search_object):
        """
        Recursively search the project configuration and replace all placeholders.

        Args:
            project_cfg:
                The entire project configuration.
            search_object:
                The part of the project configuration to be searched. The initial seed is the entire project configuration.

        Returns:
            The part of the project configuration provided in search_object with all placeholders replaced.

        Raises:
            None
        """

        if isinstance(search_object, dict):
            # Traverse dictionary
            for key, value in search_object.items():
                search_object[key] = Configuration_Compiler._resolve_placeholders(project_cfg, value)

        elif isinstance(search_object, list):
            # Traverse list
            for i, item in enumerate(search_object):
                search_object[i] = Configuration_Compiler._resolve_placeholders(project_cfg, item)

        elif isinstance(search_object, str):
            # Replace placeholders in string, if present
            placeholder_pattern = r"\{\{([^\}]+)\}\}"
            # Check if one or more placeholders are present
            if re.search(placeholder_pattern, search_object):
                str_buffer = search_object
                # Iterate over all placeholders
                for path in re.findall(placeholder_pattern, search_object):
                    keys = path.split("/")
                    # Get value from project configuration
                    value = project_cfg
                    for key in keys:
                        if key not in value:
                            pretty_print.print_error(
                                f"The following setting contains a placeholder that does not point to a valid setting: {search_object}"
                            )
                            sys.exit(1)
                        value = value[key]
                    # Replace placeholder with value
                    str_buffer = str_buffer.replace(f"{{{{{path}}}}}", str(value))
                return str_buffer

        # If it's neither a dict, list, nor string, return the value as-is
        return search_object

    @staticmethod
    def compile(
        root_cfg_file: pathlib.Path, socks_dir: pathlib.Path, project_dir: pathlib.Path
    ) -> typing.Tuple[dict, list]:
        """
        Compile the project configuration.

        Args:
            root_cfg_file:
                Path of the top level project configuration file.
            socks_dir:
                Path of the SoCks tool.
            project_dir:
                Path of the SoCks project.

        Returns:
            Fully assemble the project configuration.

        Raises:
            None
        """

        # Merge config files
        project_cfg, read_cfg_files = Configuration_Compiler._merge_cfg_files(
            config_file_name=root_cfg_file.name, socks_dir=socks_dir, project_dir=project_dir
        )

        # Resolve placeholders
        project_cfg = Configuration_Compiler._resolve_placeholders(project_cfg=project_cfg, search_object=project_cfg)

        return project_cfg, read_cfg_files
