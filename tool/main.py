#!/usr/bin/env python3

import sys
import pathlib
import importlib
import copy

import pretty_print
from cfg_compiler import Cfg_Compiler


def find_active_blocks(active_blocks, block):
    if block not in project_cfg['blocks']:
        pretty_print.print_error(f'Block \'{block}\' is not part of the configuration provided.')
        sys.exit(1)
    # Create a list with this block and all its direct dependencies
    block_deps = []
    if 'project' in project_cfg['blocks'][block] and 'dependencies' in project_cfg['blocks'][block]['project']:
        for dep, dep_path in project_cfg['blocks'][block]['project']['dependencies'].items():
            block_deps.append(dep)
    block_deps.append(block)
    # Add new dependencies to active list
    for block_i in block_deps:
        if block_i not in active_blocks:
            active_blocks.append(block_i)
    # Check if we have to dive deeper to find all dependencies
    for block_i in active_blocks:
        if 'project' in project_cfg['blocks'][block_i] and 'dependencies' in project_cfg['blocks'][block_i]['project']:
            for dep, dep_path in project_cfg['blocks'][block_i]['project']['dependencies'].items():
                if dep not in active_blocks:
                    active_blocks = find_active_blocks(active_blocks, dep)
    # Remove duplicates
    active_blocks = [i for n, i in enumerate(active_blocks) if i not in active_blocks[:n]]
    return active_blocks

def sort_blocks(blocks):
    tmp_block_list = blocks
    for block in blocks:
        # Get a list of this blocks dependencies
        block_deps = []
        if 'project' in project_cfg['blocks'][block] and 'dependencies' in project_cfg['blocks'][block]['project']:
            for dep, dep_path in project_cfg['blocks'][block]['project']['dependencies'].items():
                block_deps.append(dep)
        if not block_deps:
            continue
        # Make sure that all dependencies are in the list before this block
        for dep in block_deps:
            if dep in tmp_block_list[tmp_block_list.index(block):]:
                # Move dependency
                tmp_block_list.insert(tmp_block_list.index(block), tmp_block_list.pop(blocks.index(dep)))
    return tmp_block_list

# Set tool and project directory
socks_dir = pathlib.Path('/home/marvin/Projects/Build_System_Tests/SoCks/tool') # ToDo: I think this path should not be hard coded here
project_dir = pathlib.Path.cwd()

# Set root project configuration file
project_cfg_root_file = project_dir / 'project.yml'

# Check if we are in a SoCks project
if not project_cfg_root_file.exists():
    pretty_print.print_error(f'The current directory {project_dir} is not a SoCks project directory. No project configuration file \'project.yml\' found.')
    sys.exit(1)

# Get project configuration
project_cfg = Cfg_Compiler.compile(root_cfg_file=project_cfg_root_file, socks_dir=socks_dir, project_dir=project_dir)

# Create builder objects
builders = {}
for block0, block_dict0 in project_cfg['blocks'].items():
    builder_class_name = block_dict0['builder']
    builder_module_name = builder_class_name.lower()
    try:
        module = importlib.import_module(builder_module_name)
        # Get access to the builder class
        builder_class = getattr(module, builder_class_name)
        # Create a project configuration object for the builder that only contains information that is intended for this builder, i.e. remove all information for other builders
        builder_project_cfg = copy.deepcopy(project_cfg)
        for block1, block_dict1 in project_cfg['blocks'].items():
            if  block1 != block0:
                builder_project_cfg['blocks'].pop(block1)
        # Add builder object to dict
        builders[builder_class_name] = builder_class(project_cfg=builder_project_cfg, socks_dir=socks_dir, project_dir=project_dir)
    except ImportError:
        pretty_print.print_error(f"No builder class {builder_class_name} available")
        sys.exit(1)

# Create list of all blocks to be operated on
target_block = 'u-boot'
block_cmd = 'build'

group_cmds = ['build', 'prepare', 'clean']

if block_cmd in group_cmds:
    active_blocks = find_active_blocks([], target_block)
    active_blocks = sort_blocks(active_blocks)
else:
    active_blocks = [target_block]

for block in active_blocks:
    builder_name = project_cfg['blocks'][block]['builder']
    builder = builders[builder_name]
    if block_cmd in builder.block_cmds:
        pretty_print.print_build_stage(f'Block \'{block}\'...')
        for func in builder.block_cmds[block_cmd]:
            func()


# ToDos:
# - I a user uses 'all' instead of a block, everything should be build