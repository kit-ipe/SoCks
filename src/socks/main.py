import sys
import pathlib
import importlib.resources
import importlib.metadata
import importlib
import pkgutil
import inspect
import copy
import argparse
import yaml
import pydantic

import socks
import socks.pretty_print as pretty_print
from socks.configuration_compiler import Configuration_Compiler


def add_active_blocks(block: str, active_blocks: list[str], project_cfg: dict):
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
    if block not in project_cfg["blocks"]:
        pretty_print.print_error(f"Block '{block}' is not part of the configuration provided.")
        sys.exit(1)
    # Create a list with this block and all its direct dependencies
    block_deps = []
    if "project" in project_cfg["blocks"][block] and "dependencies" in project_cfg["blocks"][block]["project"]:
        for dep, dep_path in project_cfg["blocks"][block]["project"]["dependencies"].items():
            block_deps.append(dep)
    block_deps.append(block)
    # Add new dependencies to active list
    for block_i in block_deps:
        if block_i not in active_blocks:
            active_blocks.append(block_i)
    # Check if we have to dive deeper to find all dependencies
    for block_i in active_blocks:
        if "project" in project_cfg["blocks"][block_i] and "dependencies" in project_cfg["blocks"][block_i]["project"]:
            for dep, dep_path in project_cfg["blocks"][block_i]["project"]["dependencies"].items():
                if dep not in active_blocks:
                    active_blocks = add_active_blocks(active_blocks, dep)
    # Remove duplicates
    active_blocks = [i for n, i in enumerate(active_blocks) if i not in active_blocks[:n]]
    return active_blocks


def sort_blocks(blocks: list[str], project_cfg: dict):
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
        if "project" in project_cfg["blocks"][block] and "dependencies" in project_cfg["blocks"][block]["project"]:
            for dep, dep_path in project_cfg["blocks"][block]["project"]["dependencies"].items():
                block_deps.append(dep)
        if not block_deps:
            continue
        # Make sure that all dependencies are in the list before this block
        for dep in block_deps:
            if dep in tmp_block_list[tmp_block_list.index(block) :]:
                # Move dependency
                tmp_block_list.insert(tmp_block_list.index(block), tmp_block_list.pop(blocks.index(dep)))
    return tmp_block_list


# Create list to collect warnings from the coordinating instance
coordinating_instance_warnings = []

# Set tool and project directory
socks_dir = pathlib.Path(importlib.resources.files(socks))
project_dir = pathlib.Path.cwd()

# Set root project configuration file
project_cfg_root_file = project_dir / "project.yml"
project_cfg_user_file = project_dir / "project-user.yml"

# Check if we are in a SoCks project
if not project_cfg_root_file.exists():
    pretty_print.print_error(
        f"The current directory {project_dir} is not a SoCks project directory. No project configuration file 'project.yml' found."
    )
    sys.exit(1)

# Get project configuration
project_cfg, _ = Configuration_Compiler.compile(
    root_cfg_file=project_cfg_root_file,
    user_cfg_file=project_cfg_user_file,
    socks_dir=socks_dir,
    project_dir=project_dir,
)

# Check project type and find respective module
arch_supp_pkgs = ["amd_zynqmp_support", "amd_versal_support", "raspberrypi_support"]
project_model_suffix = "_Base_Model"
project_model_class_name = project_cfg["project"]["type"] + project_model_suffix
project_model_module = None
for package in arch_supp_pkgs:
    try:
        project_model_module = importlib.import_module(f"{package}.{project_model_class_name.lower()}")
        selected_arch_supp_pkg = package
        break  # Exit the loop if the module is successfully imported
    except ImportError:
        continue  # Try the next package if import fails
if project_model_module is None:
    available_prj_model_classes = []
    # Iterate over all modules in the available architecture support packages
    for package in arch_supp_pkgs:
        package_module = importlib.import_module(f"{package}")
        package_dir = pathlib.Path(importlib.resources.files(package_module))
        for _, module_name, _ in pkgutil.walk_packages(path=[str(package_dir)], prefix=f"{package}."):
            # Find modules that end with the project model suffix
            if module_name.endswith(project_model_suffix.lower()):
                module = importlib.import_module(module_name)
                # Find classes that end with the project model suffix
                classes = [
                    cls
                    for name, cls in inspect.getmembers(module, inspect.isclass)
                    if name.endswith(project_model_suffix)
                ]
                available_prj_model_classes.extend(classes)

    supported_prj_types = [
        "'" + cls.__name__.split(project_model_suffix)[0] + "'" for cls in available_prj_model_classes
    ]

    pretty_print.print_error(
        f"Project type '{project_cfg['project']['type']}' is not supported "
        f"(No project model class '{project_model_class_name}' available).\n"
        "\tAvailable options are: " + ", ".join(supported_prj_types)
    )
    sys.exit(1)

# Get access to the project model class
project_model_class = getattr(project_model_module, project_model_class_name)

# Initialize project configuration model
try:
    project_cfg_model = project_model_class(**project_cfg)
except pydantic.ValidationError as e:
    for err in e.errors():
        keys = []
        for item in err["loc"]:
            if isinstance(item, str):
                # If the item is a string, just append it
                keys.append(item)
            if isinstance(item, int):
                # If the item is an integer, it is an index in a list
                keys[-1] = f"{keys[-1]}[{item}]"
        pretty_print.print_error(
            f"The following error occured while analyzing node '{' -> '.join(keys)}' "
            f"of the project configuration: {err['msg']}"
        )
    sys.exit(1)

# Check project version
if project_cfg_model.project.socks_version == "any":
    coordinating_instance_warnings.append(
        "The check that validates whether the project is compatible with the version of SoCks being used is "
        "disabled because 'project -> socks_version' is set to 'any'."
    )
elif project_cfg_model.project.socks_version != importlib.metadata.version("socks").split("+", 1)[0]:
    pretty_print.print_error(
        "This project is not compatible with the version of SoCks used:\n"
        f"\tSoCks version: '{importlib.metadata.version('socks').split('+', 1)[0]}'\n"
        f"\tSoCks version required by the project: '{project_cfg_model.project.socks_version}'"
    )
    sys.exit(1)

# Create builder objects
builders = {}
for block in project_cfg_model.blocks.model_fields:
    block_cfg = getattr(project_cfg_model.blocks, block)
    if block_cfg is None:
        continue

    # Search builder module in architecture support package
    try:
        module = importlib.import_module(f"{selected_arch_supp_pkg}.{block_cfg.builder.lower()}")
    except ImportError:
        pretty_print.print_error(
            f"Builder '{block_cfg.builder}' not found in selected architecture support package: {selected_arch_supp_pkg}"
        )
        sys.exit(1)

    # Get access to the builder class
    builder_class = getattr(module, block_cfg.builder)
    # Create a project configuration object for the builder that only contains information that is intended
    # for this builder, i.e. remove all information for other builders
    builder_project_cfg = copy.deepcopy(project_cfg)
    for block_i, block_dict_i in project_cfg["blocks"].items():
        if block_i != block:
            builder_project_cfg["blocks"].pop(block_i)
    # Add builder object to dict
    builders[block_cfg.builder] = builder_class(
        project_cfg=builder_project_cfg,
        socks_dir=socks_dir,
        project_dir=project_dir,
    )

# A complete list of all commands that SoCks supports as an interaction option with blocks, including a description
supported_block_commands = {
    "prepare": "Performs all the preparatory steps to prepare this block for building, but does not build it.",
    "build": "Builds this block.",
    "prebuild": "Builds a project-independent preliminary version of this block that can later be completed with project-dependent components.",
    "build-sd-card": "Creates a complete image that can be written directly to an SD card.",
    "build-pkgs": "Builds custom packages for the root file system. These packages typically use files generated by other blocks.",
    "clean": "Deletes all generated files of this block.",
    "create-patches": "Uses the commited changes in this block's repo to create patch files.",
    "create-cfg-snippet": "Creates a configuration snippet from the changes in the .config file in this block's repo.",
    "menucfg": "Opens the menuconfig tool to enable interactive configuration of the project in this block.",
    "start-container": "Starts the container image of this block in an interactive session.",
    "start-vivado-gui": "Starts the container image and opens the Vivado GUI in an interactive session.",
}
# A list of all commands that can be applied to a group of blocks
group_cmds = ["build", "prepare", "clean"]

# Create argument parser
cli = argparse.ArgumentParser(description="SoCks - SoC image builder")
cli_blocks = cli.add_subparsers(title="blocks", dest="block")

# Add arguments
cli.add_argument(
    "-v",
    "--version",
    action="store_true",
    help="Print the version of SoCKs and exit",
)
cli.add_argument(
    "-s",
    "--show-configuration",
    action="store_true",
    help="Print the complete project configuration to the standard output and exit",
)
cli.add_argument(
    "-r",
    "--raw-output",
    action="store_true",
    help="Disable processing of shell output from build tools before it is shown (Recommended for GitLab CI/CD)",
)
cli.add_argument(
    "-p",
    "--print-csc",
    action="store_true",
    help="Enforce printing of shell commands before they are executed in a container",
)

# Add parsers for all blocks
for block, block_dict in project_cfg["blocks"].items():
    builder_name = project_cfg["blocks"][block]["builder"]
    builder = builders[builder_name]
    # Add this block to the parser
    cli_block = cli_blocks.add_parser(block, description=builder.block_description, help=f"Interact with block {block}")
    cli_block_cmds = cli_block.add_subparsers(title="commands", dest="command")
    # Add all commands that are available for this block to the parser
    for block_cmd in builder.block_cmds:
        # Check if the command to be added is supported by SoCks
        if block_cmd not in supported_block_commands:
            pretty_print.print_error(
                f"The command '{block_cmd}' is provided by builder '{builder_name}', but SoCks does not support this command."
            )
            sys.exit(1)
        cli_block_cmd = cli_block_cmds.add_parser(block_cmd, help=supported_block_commands[block_cmd])
    # Add argument for group commands
    cli_block.add_argument(
        "-g",
        "--group",
        action="store_true",
        help="Interact not only with the specified block, but also with all blocks on which this block depends.",
    )

# Add additional parser to interact with all blocks at once
cli_block = cli_blocks.add_parser("all", description="Operate on all blocks", help="Interact with all blocks at once")
cli_block_cmds = cli_block.add_subparsers(title="commands", dest="command")
for command in group_cmds:
    cli_block_cmd = cli_block_cmds.add_parser(command, help=supported_block_commands[command])

# Do tab completion
try:
    import argcomplete

    argcomplete.autocomplete(cli, always_complete_options=False)
except ImportError:
    pass


def main():
    """
    The main method and the entry point to the SoCks command-line interface
    """

    # Initialize argument parser
    args = vars(cli.parse_args())

    # Check for arguments that can be processed directly here
    if "version" in args and args["version"] == True:
        print(f"SoCks {importlib.metadata.version('socks')}")
        cli.exit()
    if "show_configuration" in args and args["show_configuration"] == True:
        print(yaml.dump(project_cfg))
        cli.exit()
    # Check whether all required arguments are available
    if "block" not in args or not args["block"] or "command" not in args or not args["command"]:
        cli.print_usage()
        pretty_print.print_error("The following arguments are required: block command.")
        cli.exit()
    if "raw_output" in args and args["raw_output"] == True:
        for builder in builders.values():
            builder.shell_executor.prohibit_output_processing(state=True)
            builder.container_executor.prohibit_output_processing(state=True)
    if "print_csc" in args and args["print_csc"] == True:
        for builder in builders.values():
            builder.container_executor.enforce_command_printing(state=True)

    target_block = args["block"]
    block_cmd = args["command"]

    if target_block == "all":
        group_cmd = True
    else:
        group_cmd = args["group"]

    # Create a list of all blocks to be worked with
    if group_cmd:
        if target_block == "all":
            active_blocks = list(project_cfg["blocks"])
        elif block_cmd in group_cmds:
            active_blocks = add_active_blocks(block=target_block, active_blocks=[], project_cfg=project_cfg)
        else:
            pretty_print.print_error(f"The following command cannot be executed on a group of blocks: {block_cmd}.")
            sys.exit(1)
        active_blocks = sort_blocks(blocks=active_blocks, project_cfg=project_cfg)
        # Blocks should be deleted in the reverse order in which they are built
        if block_cmd == "clean":
            active_blocks = list(reversed(active_blocks))
    else:
        active_blocks = [target_block]

    if block_cmd not in ["clean", "start-container", "start-vivado-gui"]:
        # Validate sources of all active blocks
        for block in active_blocks:
            builder_name = project_cfg["blocks"][block]["builder"]
            builder = builders[builder_name]
            builder.validate_srcs()

    # If necessary, issue warnings before building and ask the user for permission
    pre_action_warnings = []
    for warning in coordinating_instance_warnings:
        pre_action_warnings.append("Coordinating instance: " + warning)
    for block in active_blocks:
        builder_name = project_cfg["blocks"][block]["builder"]
        builder = builders[builder_name]
        for warning in builder.pre_action_warnings:
            pre_action_warnings.append(f"Block '{builder.block_id}': " + warning)
    if pre_action_warnings:
        for warning in pre_action_warnings:
            pretty_print.print_warning(warning)
        print(f"\nPlease read the warnings above carefully. Do you really want to continue? (Y/n) ", end="")
        answer = input("").strip().lower()
        if answer not in ("", "y", "yes"):
            pretty_print.print_clean("Aborted...")
            sys.exit(1)

    # Execute the command for all active blocks
    for index, block in enumerate(active_blocks):
        builder_name = project_cfg["blocks"][block]["builder"]
        builder = builders[builder_name]
        if block_cmd in builder.block_cmds:
            pretty_print.print_build_stage(f"[{index + 1}/{len(active_blocks)}] Block '{block}'...")
            for func in builder.block_cmds[block_cmd]:
                func()


if __name__ == "__main__":
    main()
