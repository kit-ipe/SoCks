#!/usr/bin/env python3

import typing
import sys
import pathlib
import importlib
import copy
import argparse

import pretty_print
from configuration_compiler import Configuration_Compiler


def add_active_blocks(block: str, active_blocks: typing.List[str], project_cfg: dict):
    """
    Adds the provided block and all of its dependencies to the list of active blocks

    Args:
        block:
            The block to be added.
        active_blocks:
            List of active blocks.
        project_cfg:
            Project configuration.

    Returns:
        List of active blocks.

    Raises:
        None
    """

    # Check if the provided block is valid
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
                    active_blocks = add_active_blocks(active_blocks, dep)
    # Remove duplicates
    active_blocks = [i for n, i in enumerate(active_blocks) if i not in active_blocks[:n]]
    return active_blocks

def sort_blocks(blocks: typing.List[str], project_cfg: dict):
    """
    Sorts blocks in the order in which they are to be built.

    Args:
        blocks:
            List of blocks to be sorted.
        project_cfg:
            Project configuration.

    Returns:
        Sorted list of blocks.

    Raises:
        None
    """

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
project_cfg = Configuration_Compiler.compile(root_cfg_file=project_cfg_root_file, socks_dir=socks_dir, project_dir=project_dir)

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
        pretty_print.print_error(f'No builder class {builder_class_name} available')
        sys.exit(1)

# A complete list of all commands that SoCks supports as an interaction option with blocks, including a description
supported_block_commands={
    'prepare':          'Performs all the preparatory steps to prepare this block for building, but does not build it.',
    'build':            'Builds this block.',
    'prebuild':         'Builds a project-independent preliminary version of this block that can later be completed with project-dependent components.',
    'build-sd-card':    'Creates a complete image than can be written directly to an SD card.',
    'clean':            'Deletes all generated files of this block.',
    'create-patches':   'Uses the commited changes in the repo of this block to create patch files.',
    'menucfg':          'Opens the menuconfig tool to enable interactive configuration of the project in this block.',
    'start-container':  'Starts the container image of this block in an interactive session.',
    'start-vivado-gui': 'Starts the container image and opens the Vivado GUI in an interactive session.',
    'prep-clean-srcs':  'Cleans this block and creates a new, clean Linux kernel or U-Boot project. After the creation of the project you should create a patch that includes .gitignore and .config.'
}
# A list of all commands that can be applied to a group of blocks
group_cmds = ['build', 'prepare', 'clean']

# Create argument parser
cli = argparse.ArgumentParser(description='SoCks - SoC image builder')
cli_blocks = cli.add_subparsers(title='blocks', dest='block')

# Add parsers for all blocks
for block, block_dict in project_cfg['blocks'].items():
    builder_name = project_cfg['blocks'][block]['builder']
    builder = builders[builder_name]
    # Add this block to the parser
    cli_block = cli_blocks.add_parser(block, description=builder.block_description, help=f'Interact with block {block}')
    cli_block_cmds = cli_block.add_subparsers(title='commands', dest='command')
    # Add all commands that are available for this block to the parser
    for block_cmd in builder.block_cmds:
        # Check if the command to be added is supported by SoCks
        if block_cmd not in supported_block_commands:
            pretty_print.print_error(f'The command \'{block_cmd}\' is provided by builder \'{builder_name}\', but SoCks does not support this command.')
            sys.exit(1)
        cli_block_cmd = cli_block_cmds.add_parser(block_cmd, help=supported_block_commands[block_cmd])
    # Add argument for group commands
    cli_block.add_argument("-g", "--group", action='store_true', help="Interact not only with the specified block, but also with all blocks on which this block depends.")

# Add additional parser to interact with all blocks at once
cli_block = cli_blocks.add_parser('all', description='Operate on all blocks', help='Interact with all blocks at once')
cli_block_cmds = cli_block.add_subparsers(title='commands', dest='command')
for command in group_cmds:
    cli_block_cmd = cli_block_cmds.add_parser(command, help=supported_block_commands[command])

def main():
    """
    The main method and the entry point to the SoCks command-line interface
    """

    # Initialize argument parser
    args = vars(cli.parse_args())

    # Check whether all required arguments are available
    if 'block' not in args or not args['block'] or 'command' not in args or not args['command']:
        cli.print_usage()
        pretty_print.print_error('The following arguments are required: block command.')
        cli.exit()

    target_block = args['block']
    block_cmd = args['command']

    if target_block == 'all':
        group_cmd = True
    else:
        group_cmd = args['group']

    # Create a list of all blocks to be worked with
    if group_cmd:
        if target_block == 'all':
            active_blocks =  list(project_cfg['blocks'])
        elif block_cmd in group_cmds:
            active_blocks = add_active_blocks(block=target_block, active_blocks=[], project_cfg=project_cfg)
        elif block_cmd not in group_cmds:
            pretty_print.print_error(f'The following command cannot be executed on a group of blocks: {block_cmd}.')
            sys.exit(1)
        active_blocks = sort_blocks(blocks=active_blocks, project_cfg=project_cfg)
        # Blocks should be deleted in the reverse order in which they are built
        if block_cmd == 'clean':
            active_blocks = list(reversed(active_blocks))
    else:
        active_blocks = [target_block]

    # Execute the command for all active blocks
    for block in active_blocks:
        builder_name = project_cfg['blocks'][block]['builder']
        builder = builders[builder_name]
        if block_cmd in builder.block_cmds:
            pretty_print.print_build_stage(f'Block \'{block}\'...')
            for func in builder.block_cmds[block_cmd]:
                func()

if __name__ == "__main__":
    main()

# ToDos:
# - I a user uses 'all' instead of a block, everything should be build