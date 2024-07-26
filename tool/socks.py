#!/usr/bin/env python3

import sys
import os
import json
import jsonschema
import yaml


def find_file(file_name, search_paths):
    """
    Find file in search paths. Subdirectories are not searched.
    
    :param file_name: File to find
    :param search_paths: List of paths to search in
    :return: Path of the file
    """
    for path in search_paths:
        # Get a list of all items in the path
        content = os.listdir(path)
        for item in content:
            if os.path.isfile(path+'/'+item) and item == file_name:
                # Return the path of the file
                return path+'/'+item
    # Raise an exception if the file could not be found
    raise FileNotFoundError('Unable to find '+file_name)

def merge_dicts(target, source):
    """
    Recursively merge two dictionaries.
    
    :param target: Target dictionary that receives values from the source dictionary
    :param source: Source dictionary that overwrites values in the target dictionary
    :return: Merged target dictionary
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

def compose_project_configuration(config_file):
    """
    Recursively compose project configuration YAML files by tracing the import keys.
    
    :param config_file: Project configuration file
    :return: Fully assembled project configuration
    """
    try:
        config_file_path = find_file(file_name=config_file, search_paths=['.', '../project'])
    except FileNotFoundError as e:
        print(repr(e))
        sys.exit(1)
    with open(config_file_path, 'r') as f:
        cfg_layer = yaml.safe_load(f)
    # Directly return the cfg layer if it doesn't contain an 'import' key
    ret = cfg_layer
    if 'import' in cfg_layer:
        for file_name in cfg_layer['import']:
            # Recursively merge the so far composed return value with the imported file 
            ret = merge_dicts(target=compose_project_configuration(file_name), source=ret)
        # Remove the 'import' key from the so far composed configuration, as it is no longer needed
        del ret['import']
    return ret


with open('zynqmp.schema.json', 'r') as f:
    schema = json.load(f)

project_config = compose_project_configuration(config_file='project.yml')
#print('\n\n')
#print(project_config)

jsonschema.validate(project_config, schema)