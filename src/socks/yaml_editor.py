import pathlib
import yaml
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
            target_indent = ""
            for layer in keys:
                lines_to_append.append(target_indent + layer + ":\n")
                target_indent += "  "

            # Convert data to YAML format
            yaml_string = yaml.dump([data], default_flow_style=False)
            for yaml_line in yaml_string.splitlines(keepends=True):
                lines_to_append.append(target_indent + yaml_line)

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

            modified_lines = []
            in_target_section = False
            nr_keys_found = 0
            for line in current_lines:
                # Determine spaces before next key
                key_indent = ""
                for i in range(nr_keys_found):
                    key_indent += "  "
                # If this line is an existing key that has not yet been found
                if nr_keys_found < len(existing_keys) and line.startswith(
                    f"{key_indent}{existing_keys[nr_keys_found]}:"
                ):
                    nr_keys_found += 1
                    if nr_keys_found == len(existing_keys):
                        if "[" in line:
                            # Turn flow style list into regular list
                            line = line.split(":")[0] + ":\n"
                        in_target_section = True
                        target_indent = key_indent + "  "
                    modified_lines.append(line)
                    continue
                # Append new yaml section at the end of the target section
                if in_target_section and not line.startswith(target_indent):
                    for layer in missing_keys:
                        modified_lines.append(target_indent + layer + ":\n")
                        target_indent += "  "
                    # Convert list to YAML format
                    yaml_string = yaml.dump(new_yaml_sec, default_flow_style=False)
                    for yaml_line in yaml_string.splitlines(keepends=True):
                        modified_lines.append(target_indent + yaml_line)
                    in_target_section = False
                # Do not append lines that will be appended as part of the new yaml section
                if len(new_yaml_sec) == 1 or not in_target_section:
                    modified_lines.append(line)

            # If the target section ends at the end of the file
            if in_target_section:
                # Add a line break if the last line does not end with one
                if not modified_lines[-1].rstrip("\r").endswith("\n"):
                    modified_lines.append("\n")
                for layer in missing_keys:
                    modified_lines.append(target_indent + layer + ":\n")
                    target_indent += "  "
                # Convert list to YAML format
                yaml_string = yaml.dump(new_yaml_sec, default_flow_style=False)
                for yaml_line in yaml_string.splitlines(keepends=True):
                    modified_lines.append(target_indent + yaml_line)

            if nr_keys_found != len(existing_keys):
                raise ValueError(f"Unable to find '{' -> '.join(keys)}' in file '{file}'")

        # Write modified lines back to the file
        with file.open("w") as f:
            f.writelines(modified_lines)
