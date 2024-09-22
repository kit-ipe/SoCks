#!/usr/bin/env python3

import typing
import sys
import pathlib
import importlib
import json
import jsonschema
import yaml
import copy
import re

import pretty_print


def find_file(file_name: str, search_list: typing.List[pathlib.Path]) -> pathlib.Path:
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
        # Iterate over all items in the path
        for item in path.iterdir():
            if item.is_file() and item.name == file_name:
                # Return found file
                return item
    # Raise an exception if the file could not be found
    raise FileNotFoundError(f'Unable to find {file_name}')


def merge_dicts(target: dict, source: dict) -> dict:
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
            target[key] = merge_dicts(target[key], value)
        elif key in target and isinstance(target[key], list) and isinstance(value, list):
            # If both values are lists, merge them without duplicating elements
            target[key] = list(set(target[key] + value))
        else:
            # If the value is not a dict or a list or if the key is not yet in the result, simply assign the value
            target[key] = value
    return target


def compose_project_configuration(config_file_name: str, socks_dir: pathlib.Path, project_dir: pathlib.Path) -> dict:
    """
    Recursively compose project configuration YAML files by tracing the import keys.
    
    Args:
        config_file_name:
            Name of the project configuration file to operate on.

    Returns:
        Fully assembled project configuration.

    Raises:
        None
    """

    try:
        config_file = find_file(file_name=config_file_name, search_list=[socks_dir / 'project_templates', project_dir]) # ToDo: I think these paths should not be hard coded here
    except FileNotFoundError as e:
        print(repr(e))
        sys.exit(1)
    with config_file.open('r') as f:
        cfg_layer = yaml.safe_load(f)
    # Directly return the cfg layer if it doesn't contain an 'import' key
    ret = cfg_layer
    if 'import' in cfg_layer:
        for file_name in cfg_layer['import']:
            # Recursively merge the so far composed return value with the imported file 
            ret = merge_dicts(target=compose_project_configuration(config_file_name=file_name, socks_dir=socks_dir, project_dir=project_dir), source=ret)
        # Remove the 'import' key from the so far composed configuration, as it is no longer needed
        del ret['import']
    return ret


def resolve_placeholders(project_cfg: dict, search_object):
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
            search_object[key] = resolve_placeholders(project_cfg, value)

    elif isinstance(search_object, list):
        # Traverse list
        for i, item in enumerate(search_object):
            search_object[i] = resolve_placeholders(project_cfg, item)

    elif isinstance(search_object, str):
        # Replace placeholders in string, if present
        placeholder_pattern = r'\{\{([^\}]+)\}\}'
        # Check if one or more placeholders are present
        if re.search(placeholder_pattern, search_object):
            str_buffer = search_object
            # Iterate over all placeholders
            for path in re.findall(placeholder_pattern, search_object):
                keys = path.split('/')
                # Get value from project configuration
                value = project_cfg
                for key in keys:
                    if key not in value:
                        pretty_print.print_error(f'The following setting contains a placeholder that does not point to a valid setting: {search_object}')
                        sys.exit(1)
                    value = value[key]
                # Replace placeholder with value
                str_buffer = str_buffer.replace(f'{{{{{path}}}}}',str(value))
            return str_buffer

    # If it's neither a dict, list, nor string, return the value as-is
    return search_object


# Set tool and project directory
socks_dir = pathlib.Path('/home/marvin/Projects/Build_System_Tests/SoCks/tool') # ToDo: I think these path should not be hard coded here
project_dir = pathlib.Path.cwd()

# Set root project configuration file
project_cfg_root_file = project_dir / 'project.yml'

# Check if we are in a SoCks project
if not project_cfg_root_file.exists():
    pretty_print.print_error(f'The current directory {project_dir} is not a SoCks project directory. No project configuration file \'project.yml\' found.')
    sys.exit(1)

# Get project configuration
project_cfg = compose_project_configuration(config_file_name=project_cfg_root_file.name, socks_dir=socks_dir, project_dir=project_dir)
project_cfg = resolve_placeholders(project_cfg, project_cfg)

# Validate project configuration
project_cfg_schema_file = socks_dir / 'schemas' / f'{project_cfg["project"]["type"]}.schema.json'
if not project_cfg_schema_file.is_file():
    pretty_print.print_error(f'{project_cfg["project"]["type"]} is not a supported project type.')
    sys.exit(1)

with project_cfg_schema_file.open('r') as f:
    project_cfg_schema = json.load(f)

jsonschema.validate(project_cfg, project_cfg_schema)

# Create builder objects
builders = {}
for key0, value0 in project_cfg['blocks'].items():
    builder_class_name = value0['builder']
    builder_module_name = builder_class_name.lower()
    try:
        module = importlib.import_module(builder_module_name)
        # Get access to the builder class
        builder_class = getattr(module, builder_class_name)
        # Create a project configuration object for the builder that only contains information that is intended for this builder, i.e. remove all information for other builders
        builder_project_cfg = copy.deepcopy(project_cfg)
        for key1, value1 in project_cfg['blocks'].items():
            if  key1 != key0:
                builder_project_cfg['blocks'].pop(key1)
        # Add builder object to dict
        builders[builder_class_name] = builder_class(project_cfg=builder_project_cfg, socks_dir=socks_dir, project_dir=project_dir)
    except ImportError:
        pretty_print.print_error(f"No builder class {builder_class_name} available")
        sys.exit(1)

#
# From here onwards it is just for testing
#

# ATF
#for func in builders['ZynqMP_AMD_ATF_Builder_Alma9'].block_cmds['build']:
#    func()

# U-Boot
#for func in builders['ZynqMP_AMD_UBoot_Builder_Alma9'].block_cmds['build']:
#    func()

# Vivado
#for func in builders['ZynqMP_AMD_Vivado_Hog_Builder_Alma9'].block_cmds['build']:
#    func()

# FSBL
#for func in builders['ZynqMP_AMD_FSBL_Builder_Alma9'].block_cmds['build']:
#    func()

# PMU Firmware
#for func in builders['ZynqMP_AMD_PMUFW_Builder_Alma9'].block_cmds['build']:
#    func()

# Kernel
#for func in builders['ZynqMP_AMD_Kernel_Builder_Alma9'].block_cmds['build']:
#    func()

# Devicetree
#for func in builders['ZynqMP_AMD_Devicetree_Builder_Alma9'].block_cmds['build']:
#    func()

# Root File System
for func in builders['ZynqMP_Alma_RootFS_Builder_Alma8'].block_cmds['build']:
    func()

# Image
#for func in builders['ZynqMP_AMD_Image_Builder_Alma9'].block_cmds['build']:
#    func()

# ToDos:
# - I think it would be good to use the dependency information from the project cfg to build a tree and
#   use that to find out which components have to be build. This should be done in this main file.
#   This would require a build funcion in every block that builds the full block. Maybe cmd_build to
#   highlight that this is a command. Maybe the same for clean.