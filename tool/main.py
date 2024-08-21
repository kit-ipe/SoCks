#!/usr/bin/env python3

import typing
import sys
import pathlib
import importlib
import json
import jsonschema
import yaml
import copy

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


# Set tool and project directory
socks_dir = pathlib.Path('/home/marvin/Projects/Build_System_Tests/SoCks/tool') # ToDo: I think these path should not be hard coded here
project_dir = pathlib.Path.cwd()

# Set root project configuration file
project_cfg_root_file = project_dir / 'project.yml'

# Check if we are in a SoCks project
if not project_cfg_root_file.exists():
    pretty_print.print_error(f'The current directory {str(project_dir)} is not a SoCks project directory. No project configuration file \'project.yml\' found.')
    sys.exit(1)

# Get project configuration
project_cfg = compose_project_configuration(config_file_name=project_cfg_root_file.name, socks_dir=socks_dir, project_dir=project_dir)

# Validate project configuration
if 'projectType' in project_cfg:
    project_cfg_schema_file = socks_dir / 'schemas' / f'{project_cfg["projectType"]}.schema.json'
    if not project_cfg_schema_file.is_file():
        pretty_print.print_error(f'{project_cfg["projectType"]} is not a supported project type.')
        sys.exit(1)
else:
    pretty_print.print_error('Project configuration is missing the \'projectType\' field.')
    sys.exit(1)
with project_cfg_schema_file.open('r') as f:
    project_cfg_schema = json.load(f)

jsonschema.validate(project_cfg, project_cfg_schema)

# Create builder objects
builder_modules = ['zynqmp_amd_atf_builder_alma9']
builders = {}

for key0, value0 in project_cfg['blocks'].items():
    if key0 == 'atf':    # ToDo: Remove. Just temporary here for testing.
        builder_found = False
        for module_name in builder_modules:
            try:
                module = importlib.import_module(module_name)
                if hasattr(module, value0['builder']):
                    # Get access to the builder class
                    builder_class = getattr(module, value0['builder'])
                    # Create a project configuration object for the builder that only contains information that is intended for this builder, i.e. remove all information for other builders
                    builder_project_cfg = copy.deepcopy(project_cfg)
                    for key1, value1 in project_cfg['blocks'].items():
                        if  key1 != key0:
                            builder_project_cfg['blocks'].pop(key1)
                    # Add builder object to dict
                    builders[value0['builder']] = builder_class(project_cfg=builder_project_cfg, socks_dir=socks_dir, project_dir=project_dir)
                    builder_found = True
                    break
            except ImportError:
                continue
        if not builder_found:
            pretty_print.print_error(f"No builder class {value0['builder']} available")
            sys.exit(1)

#
# From here onwards it is just for testing
#

#builders['ZynqMP_AMD_ATF_Builder_Alma9'].build_container_image()
#builders['ZynqMP_AMD_ATF_Builder_Alma9'].init_repo()
#builders['ZynqMP_AMD_ATF_Builder_Alma9'].apply_patches()
#builders['ZynqMP_AMD_ATF_Builder_Alma9'].create_patches()

#builders['ZynqMP_AMD_ATF_Builder_Alma9'].build_atf()

#builders['ZynqMP_AMD_ATF_Builder_Alma9'].download_pre_built('https://serenity.web.cern.ch/sw/ci/os/branches/3-build-complete-serenity-s1-kria-k26-image-in-a-pipeline/0e10c5d1/pipeline7729069/pre-built_alma8_rev1_xck26.tar.xz')
#builders['ZynqMP_AMD_ATF_Builder_Alma9'].download_pre_built('https://serenity.web.cern.ch/sw/ci/os/branches/3-build-complete-serenity-s1-kria-k26-image-in-a-pipeline/0e10c5d1/pipeline7729069/serenity-s1-kria-atf.tar.gz')
builders['ZynqMP_AMD_ATF_Builder_Alma9'].clean_download()
builders['ZynqMP_AMD_ATF_Builder_Alma9'].clean_repo()
builders['ZynqMP_AMD_ATF_Builder_Alma9'].clean_output()