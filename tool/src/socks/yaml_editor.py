import pathlib
import yaml
import re
from typing import Union


class YAML_Editor:
    """
    A class to edit YAML files
    """

    @staticmethod
    def append_list_entry(file: pathlib.Path, keys: list[str], data: Union[str, dict]):
        """
        Add a new list entry to a YAML file.

        Args:
            file:
                Path of the YAML file.
            keys:
                Keys to find the location in the YAML structure where the data is to be added.
            data:
                The data to add in the list.

        Returns:
            None

        Raises:
            ValueError:
                If one of the input values is not valid.
        """

        # Load main configuration file
        with file.open("r") as f:
            file_content = f.read()
            current_yaml_cfg = yaml.safe_load(file_content)
            current_lines = file_content.splitlines(keepends=True)

        # Check how many of the requested keys do already exist
        existing_keys = []
        current_subsec = current_yaml_cfg
        for layer in keys:
            if layer in current_subsec:
                existing_keys.append(layer)
                current_subsec = current_subsec[layer]
            else:
                break
        missing_keys = [item for item in keys if item not in existing_keys]

        # If all keys are new, append at the end of the file
        if not existing_keys:
            lines_to_append = []
            indents = ""
            for layer in keys:
                lines_to_append.append(indents + layer + ":\n")
                indents = indents + "  "

            # Convert data to YAML format
            yaml_string = yaml.dump([data], default_flow_style=False)
            for yaml_line in yaml_string.splitlines(keepends=True):
                lines_to_append.append(indents + yaml_line)

            # Add a line break if the last line does not end with one
            if not current_lines[-1].rstrip("\r").endswith("\n"):
                lines_to_append = ["\n"] + lines_to_append
            modified_lines = current_lines + lines_to_append

        # If at least some keys exist, insert the new data
        else:
            # Create a new yaml section with the provided data
            new_yaml_sec = [data]

            # If all keys exist, the existing node must be checked and taken into account
            if keys == existing_keys:
                if isinstance(current_subsec, list):
                    new_yaml_sec = current_subsec
                    new_yaml_sec.append(data)
                elif current_subsec is not None:
                    raise ValueError(
                        f"Unable to add data to node '{' -> '.join(keys)}' in file '{file}'. "
                        f"This node was expected to be of type 'list'."
                    )

            # Create string with the required number of indents for the already existing keys
            indents = ""
            for _ in existing_keys:
                indents = indents + "  "

            modified_lines = []
            in_target_section = False
            for line in current_lines:
                # If this line opens a new layer in the yaml file
                if existing_keys and re.search(f" *{existing_keys[0]}:", line):
                    del existing_keys[0]
                    if not existing_keys:
                        if "[" in line:
                            # Turn flow style list into regular list
                            line = line.split(":")[0] + ":\n"
                        in_target_section = True
                    modified_lines.append(line)
                    continue
                # Append new yaml section at the end of the target section
                if in_target_section and not line.startswith(indents):
                    for layer in missing_keys:
                        modified_lines.append(indents + layer + ":\n")
                        indents = indents + "  "
                    # Convert list to YAML format
                    yaml_string = yaml.dump(new_yaml_sec, default_flow_style=False)
                    for yaml_line in yaml_string.splitlines(keepends=True):
                        modified_lines.append(indents + yaml_line)
                    in_target_section = False
                # Do not append lines that will be appended as part of the new yaml section
                if len(new_yaml_sec) == 1 or not in_target_section:
                    modified_lines.append(line)

            # If the target section ends at the end of the file
            if in_target_section:
                for layer in missing_keys:
                    modified_lines.append(indents + layer + ":\n")
                    indents = indents + "  "
                # Convert list to YAML format
                yaml_string = yaml.dump(new_yaml_sec, default_flow_style=False)
                for yaml_line in yaml_string.splitlines(keepends=True):
                    modified_lines.append(indents + yaml_line)

            if existing_keys:
                raise ValueError(f"Unable to find '{' -> '.join(keys)}' in file '{file}'")

        # Write modified lines back to the file
        with file.open("w") as f:
            f.writelines(modified_lines)
