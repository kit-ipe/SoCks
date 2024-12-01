import typing
import os
import pathlib
import sys
from dateutil import parser
import inspect
import subprocess

import socks.pretty_print as pretty_print
from socks.shell_command_runners import Shell_Command_Runners
from socks.timestamp_logger import Timestamp_Logger


class Containerization:
    """
    A class to execute commands and tasks in containers
    """

    def __init__(
        self,
        container_tool: str,
        container_file: pathlib.Path,
        container_image: str,
        container_image_tag: str,
        container_log_file: pathlib.Path,
    ):

        if container_tool not in ["docker", "podman", "none"]:
            pretty_print.print_error(f"Containerization tool {self._container_tool} is not supported.")
            sys.exit(1)

        # Check if the selected container tool is installed
        # This detailed check is necessary to avoid being tricked by podman's Docker compatibility layer
        results = Shell_Command_Runners.get_sh_results([container_tool, "--version"])
        installation_valid = True
        if container_tool == "docker":
            installation_valid = results.returncode == 0 and any(
                "Docker version" in s for s in results.stdout.splitlines()
            )
        if container_tool == "podman":
            installation_valid = results.returncode == 0 and any(
                "podman version" in s for s in results.stdout.splitlines()
            )
        if not installation_valid:
            pretty_print.print_error(
                f"It seems that the selected container tool '{container_tool}' is not installed correctly. "
                + f"(This was detected by analysing the output of '{container_tool} --version')"
            )
            sys.exit(1)

        # The container tool to be used. 'none' if the command is to be run directly on the host system.
        self._container_tool = container_tool
        # The container file to be user as source for building.
        self._container_file = container_file
        # Identifier of the container image in format <image name>:<image tag>.
        self._container_image_tagged = f"{container_image}:{container_image_tag}"

        # Timestamp logger
        self._container_log = Timestamp_Logger(container_log_file)

    @staticmethod
    def _err_container_feature(feature: str):
        """
        Display an error message that the requested feature is only available if a container tool is used.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        pretty_print.print_error(f"{feature} is only available if a containerization tool is used.")
        sys.exit(1)

    def build_container_image(self):
        """
        Builds the container image for the selected container tool.

        The container management tool (podman/docker) will restore everything that has not changed in the
        containerfile from the cache.

        Args:
            None

        Returns:
            None

        Raises:
            ValueError:
                If an unexpected container tool is specified
        """

        # Skip this function if no container tool is used
        if self._container_tool == "none":
            pretty_print.print_warning("Container image is not built in native mode.")
            return

        # Check if the required container file exists
        if not self._container_file.is_file():
            pretty_print.print_error(f"File {self._container_file} not found.")
            sys.exit(1)

        # Get last build timestamp
        last_build_timestamp = self._container_log.get_logged_timestamp(
            identifier=f"{self._container_tool}-image-{self._container_image_tagged}-built"
        )
        # Get last modification time of the container file
        last_file_mod_timestamp = self._container_file.stat().st_mtime
        # Build image, if necessary
        if last_build_timestamp < last_file_mod_timestamp:
            if self._container_tool == "docker":
                host_user = os.getlogin()
                host_user_id = os.getuid()
                pretty_print.print_build(f"Building docker image {self._container_image_tagged}...")
                Shell_Command_Runners.run_sh_command(
                    [
                        "docker",
                        "build",
                        "-t",
                        self._container_image_tagged,
                        "-f",
                        str(self._container_file),
                        "--build-arg",
                        f"user_name={host_user}",
                        "--build-arg",
                        f"user_id={host_user_id}",
                        ".",
                    ]
                )

            elif self._container_tool == "podman":
                pretty_print.print_build(f"Building podman image {self._container_image_tagged}...")
                Shell_Command_Runners.run_sh_command(
                    ["podman", "build", "-t", self._container_image_tagged, "-f", str(self._container_file), "."]
                )

            else:
                raise ValueError(f"Unexpected container tool: {self._container_tool}")

            self._container_log.log_timestamp(
                identifier=f"{self._container_tool}-image-{self._container_image_tagged}-built"
            )
        else:
            pretty_print.print_build(f"No need to build {self._container_tool} image {self._container_image_tagged}...")

    def clean_container_image(self):
        """
        Cleans the container image of the selected container tool.

        Args:
            None

        Returns:
            None

        Raises:
            ValueError:
                If an unexpected container tool is specified
        """

        if self._container_tool in ("docker", "podman"):
            # Clean image only if it exists
            results = Shell_Command_Runners.get_sh_results(
                [self._container_tool, "images", "-q", self._container_image_tagged]
            )
            if results.stdout.splitlines():
                pretty_print.print_build(f"Cleaning container image {self._container_image_tagged}...")
                Shell_Command_Runners.run_sh_command(
                    [self._container_tool, "image", "rm", self._container_image_tagged]
                )
            else:
                pretty_print.print_build(
                    f"No need to clean container image {self._container_image_tagged}, " "the image doesn't exist..."
                )

        elif self._container_tool == "none":
            # This function is only supported if a container tool is used
            Containerization._err_container_feature(f"{inspect.getframeinfo(inspect.currentframe()).function}()")

        else:
            raise ValueError(f"Unexpected container tool: {self._container_tool}")

    def run_containerizable_sh_command(
        self,
        commands: typing.List[str],
        dirs_to_mount: typing.List[typing.Tuple[pathlib.Path, str]] = [],
        custom_params: typing.List[str] = [],
        print_commands: bool = False,
        run_as_root: bool = False,
        logfile: pathlib.Path = None,
        scrolling_output: bool = False,
        visible_lines: int = 30,
    ):
        """(Google documentation style:
            https://github.com/google/styleguide/blob/gh-pages/pyguide.md#38-comments-and-docstrings)
        Runs a sh command in a container or directly on the host system.

        Args:
            commands:
                List of commands to execute.
            dirs_to_mount:
                A list of tuples that represent directories to be mounted into the container. Each tuple contains a
                path and a string with the correspondig docker/podman volume mount options.
            custom_params:
                Additional custom parameters that are passed to the containerization tool.
            print_commands:
                Set to True to print every shell command before it is executed in the container
            run_as_root:
                Set to True if the command is to be run as root user.
            logfile:
                Logfile as pathlib.Path object. None if no log file is to be used.
            scrolling_output:
                If True, the output of the sh command is printed in a scrolling view. The printed output is updated
                at runtime and the latest lines are always displayed.
            visible_lines:
                Maximum number of sh output lines to be printed if scolling_output is True. If set to 0, no output
                is visible.

        Returns:
            None

        Raises:
            ValueError:
                If an unexpected container tool is specified
        """

        # Assemble command string for container
        comp_commands = "'"
        if print_commands:
            comp_commands = comp_commands + 'trap "echo \\"container> \$BASH_COMMAND\\"" DEBUG && '
        for i, command in enumerate(commands):
            if i == len(commands) - 1:
                # The last element of the list is treated differently
                comp_commands = comp_commands + command
            else:
                comp_commands = comp_commands + command + " && "
        comp_commands = comp_commands + "'"

        if self._container_tool in ("docker", "podman"):
            mounts = " ".join([f"-v {i[0]}:{i[0]}:{i[1]}" for i in dirs_to_mount])
            # Run commands in container
            user_opt = "-u root" if run_as_root else ""
            Shell_Command_Runners.run_sh_command(
                command=[self._container_tool, "run", "--rm", "-it", user_opt, mounts]
                + custom_params
                + [self._container_image_tagged, "sh", "-c", comp_commands],
                logfile=logfile,
                scrolling_output=scrolling_output,
                visible_lines=visible_lines,
            )

        elif self._container_tool == "none":
            # Run commands without using a container
            sudo_opt = "sudo" if run_as_root else ""
            Shell_Command_Runners.run_sh_command(
                command=[sudo_opt, "sh", "-c", comp_commands],
                logfile=logfile,
                scrolling_output=scrolling_output,
                visible_lines=visible_lines,
            )

        else:
            raise ValueError(f"Unexpected container tool: {self._container_tool}")

    def enable_multiarch(self):
        """
        Enable to execute binaries for different architectures in containers
        that are launched afterwards. This enables to execute x86 and arm64
        binaries in the same container. QEMU is automatically used when it
        is needed.

        Args:
            container_tool:
                The container tool to be used. None or 'none' if the command is to be run directly on the host system.

        Returns:
            None

        Raises:
            ValueError:
                If an unexpected container tool is specified
        """

        if list(pathlib.Path("/proc/sys/fs/binfmt_misc").glob("qemu-*")):
            pretty_print.print_build("No need to activate multiarch support for containers. It is already active...")
            return

        pretty_print.print_build("Activating multiarch support for containers...")

        if self._container_tool == "docker":
            Shell_Command_Runners.run_sh_command(["docker", "pull", "multiarch/qemu-user-static:register"])
            Shell_Command_Runners.run_sh_command(
                ["docker", "run", "--rm", "--privileged", "multiarch/qemu-user-static:register", "--reset"]
            )

        elif self._container_tool == "podman":
            Shell_Command_Runners.run_sh_command(["sudo", "podman", "pull", "multiarch/qemu-user-static:register"])
            Shell_Command_Runners.run_sh_command(
                ["sudo", "podman", "run", "--rm", "--privileged", "multiarch/qemu-user-static:register", "--reset"]
            )

        elif self._container_tool == "none":
            pretty_print.print_warning(f"Multiarch is not activated in native mode.")
            return

        else:
            raise ValueError(f"Unexpected container tool: {self._container_tool}")

    def start_container(self, potential_mounts: typing.List[typing.Tuple[pathlib.Path, str]]):
        """
        Starts an interactive container with which the block can be built.

        Args:
            potential_mounts:
                List of all directories that could be mounted in the container.
                Existing directories are mounted, non-existing directories are ignored.

        Returns:
            None

        Raises:
            ValueError:
                If an unexpected container tool is specified
        """

        if self._container_tool in ("docker", "podman"):
            # Check which mounts (resp. directories) are available on the host system
            existing_mounts = [mount for mount in potential_mounts if mount[0].is_dir()]
            mounts = " ".join([f"-v {i[0]}:{i[0]}:{i[1]}" for i in existing_mounts])

            pretty_print.print_build("Starting container...")

            try:
                Shell_Command_Runners.run_sh_command(
                    [self._container_tool, "run", "--rm", "-it", mounts, self._container_image_tagged]
                )
            except subprocess.CalledProcessError:
                pass  # It is okay if the interactive shell session is ended with an exit code not equal to 0

        elif self._container_tool == "none":
            # This function is only supported if a container tool is used
            Containerization._err_container_feature(f"{inspect.getframeinfo(inspect.currentframe()).function}()")

        else:
            raise ValueError(f"Unexpected container tool: {self._container_tool}")

    def start_gui_container(
        self, start_gui_commands: typing.List[str], potential_mounts: typing.List[typing.Tuple[pathlib.Path, str]]
    ):
        """
        Starts an interactive container with which the block can be built.

        Args:
            start_gui_commands:
                List of commands to be used to start the GUI in the container.
            potential_mounts:
                List of all directories that could be mounted in the container.
                Existing directories are mounted, non-existing directories are ignored.

        Returns:
            None

        Raises:
            ValueError:
                If an unexpected container tool is specified
        """

        # Check if x11docker is installed
        results = Shell_Command_Runners.get_sh_results(["command", "-v", "x11docker"])
        if not results.stdout:
            pretty_print.print_error(
                "Command 'x11docker' not found. Install x11docker (https://github.com/mviereck/x11docker)."
            )
            sys.exit(1)

        # Assemble command string for container
        comp_commands = "'"
        for i, command in enumerate(start_gui_commands):
            if i == len(start_gui_commands) - 1:
                # The last element of the list is treated differently
                comp_commands = comp_commands + command
            else:
                comp_commands = comp_commands + command + " && "
        comp_commands = comp_commands + "'"

        # Check which mounts (resp. directories) are available on the host system
        existing_mounts = [mount for mount in potential_mounts if mount[0].is_dir()]
        mounts = " ".join([f"--share {i[0]}:{i[1]}" if i[1] == "ro" else f"--share {i[0]}" for i in existing_mounts])

        pretty_print.print_build("Starting container...")

        if self._container_tool == "docker":
            Shell_Command_Runners.run_sh_command(
                [
                    "x11docker",
                    "--backend=docker",
                    "--interactive",
                    "--network",
                    "--clipboard=yes",
                    "--xauth=trusted",
                    "--user=RETAIN",
                    mounts,
                    self._container_image_tagged,
                    f"--runasuser={comp_commands}",
                ]
            )

        elif self._container_tool == "podman":
            Shell_Command_Runners.run_sh_command(
                [
                    "x11docker",
                    "--backend=podman",
                    "--interactive",
                    "--network",
                    "--clipboard=yes",
                    "--xauth=trusted",
                    "--cap-default",
                    "--user=RETAIN",
                    mounts,
                    self._container_image_tagged,
                    f"--runasuser={comp_commands}",
                ]
            )

        elif self._container_tool == "none":
            # This function is only supported if a container tool is used
            Containerization._err_container_feature(f"{inspect.getframeinfo(inspect.currentframe()).function}()")

        else:
            raise ValueError(f"Unexpected container tool: {self._container_tool}")
