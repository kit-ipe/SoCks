#!/usr/bin/env python3

import sys
import pathlib
import importlib
import copy

import pretty_print
from cfg_compiler import Cfg_Compiler


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
project_cfg = Cfg_Compiler.compile(root_cfg_file=project_cfg_root_file, socks_dir=socks_dir, project_dir=project_dir)

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