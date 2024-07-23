#!/usr/bin/env python3

import sys
import os
import json
import jsonschema
import yaml


def find_file(file_name, search_paths):
    for path in search_paths:
        content = os.listdir(path)
        for item in content:
            if os.path.isfile(path+'/'+item) and item == file_name:
                return path+'/'+item
    raise FileNotFoundError('Unable to find '+file_name)

def merge_dicts(target, source):
    """
    Recursively merge two dictionaries.
    
    :param target: First dictionary
    :param source: Second dictionary
    :return: Merged dictionary
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
    try:
        config_file_path = find_file(file_name=config_file, search_paths=['.', '../project'])
    except FileNotFoundError as e:
        print(repr(e))
        sys.exit(1)
    with open(config_file_path, 'r') as f:
        cfg_layer = yaml.safe_load(f)
    ret = cfg_layer
    if 'import' in cfg_layer:
        for file_name in cfg_layer['import']:
            # ToDo: Check if multi imports work and if they are executed in the correct order
            ret = merge_dicts(compose_project_configuration(file_name), cfg_layer)
        del ret['import']
    return ret


with open('zynqmp.schema.json', 'r') as f:
    schema = json.load(f)

project_config = compose_project_configuration(config_file='project.yml')
print('\n\n')
print(project_config)

try:
    jsonschema.validate(project_config, schema)
except jsonschema.ValidationError as e:
    print('Validation of project configuration failed: '+e.schema.get('error_msg', e.message))
    sys.exit(1)
