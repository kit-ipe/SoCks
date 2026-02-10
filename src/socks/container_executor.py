import os
import pwd
import pathlib
import sys
import inspect
import subprocess

import socks.pretty_print as pretty_print
from socks.build_validator import Build_Validator
from socks.shell_executor import Shell_Executor
from socks.timestamp_logger import Timestamp_Logger


class Container_Executor:
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
        prohibit_output_processing: bool = False,
        enforce_command_printing: bool = False,
    ):

        if container_tool not in ("docker", "podman", "none"):
            pretty_print.print_error(f"Containerization tool {self._container_tool} is not supported.")
            sys.exit(1)

        # Shell command executor
        self._shell_executor = Shell_Executor(prohibit_output_processing=prohibit_output_processing)

        if container_tool != "none":
            # Check if the selected container tool is installed
            # This detailed check is necessary to avoid being tricked by podman's Docker compatibility layer
            results = self._shell_executor.get_sh_results(command=[container_tool, "--version"], check=False)
            installation_valid = False
            if container_tool == "docker":
                installation_valid = results.returncode == 0 and any(
                    "Docker version" in s for s in results.stdout.splitlines()
                )
                if installation_valid:
                    # Check for docker buildx
                    results = self._shell_executor.get_sh_results(
                        command=[container_tool, "buildx", "version"], check=False
                    )
                    if results.returncode != 0:
                        pretty_print.print_error(f"Docker buildx is not available on the host system")
                        sys.exit(1)
            elif container_tool == "podman":
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

        # Get host user and id (a bit complicated but should work in most Unix environments)
        self._host_user_id = os.getuid()
        self._host_user = pwd.getpwuid(self._host_user_id).pw_name

        # Enforce printing shell commands before they are executed in the container.
        # This setting overwrites all other shell command printing settings.
        self._enforce_command_printing = enforce_command_printing

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
            pretty_print.print_info("Container image is not built in native mode.")
            return

        # Check if the required container file exists
        if not self._container_file.is_file():
            pretty_print.print_error(f"File {self._container_file} not found.")
            sys.exit(1)

        # Check whether the image needs to be built
        if not Build_Validator.check_rebuild_bc_timestamp(
            src_search_list=[self._container_file, self._container_file.parent / "entrypoint.sh"],
            out_timestamp=self._container_log.get_logged_timestamp(
                identifier=f"{self._container_tool}-image-{self._container_image_tagged}-built"
            ),
        ):
            pretty_print.print_build(f"No need to build {self._container_tool} image {self._container_image_tagged}...")
            return

        with self._container_log.timestamp(
            identifier=f"{self._container_tool}-image-{self._container_image_tagged}-built"
        ):
            if self._container_tool == "docker":
                pretty_print.print_build(f"Building docker image {self._container_image_tagged}...")

                self._shell_executor.exec_sh_command(
                    [
                        "docker",
                        "buildx",
                        "build",
                        "-t",
                        self._container_image_tagged,
                        "-f",
                        str(self._container_file),
                        "--ssh",
                        "default",
                        "--build-context",
                        f"container_srcs={str(self._container_file.parent)}",
                        "--load",
                        ".",
                    ]
                )

            elif self._container_tool == "podman":
                pretty_print.print_build(f"Building podman image {self._container_image_tagged}...")

                self._shell_executor.exec_sh_command(
                    [
                        "podman",
                        "build",
                        "-t",
                        self._container_image_tagged,
                        "-f",
                        str(self._container_file),
                        "--ssh",
                        "default",
                        "--build-context",
                        f"container_srcs={str(self._container_file.parent)}",
                        "--ulimit nofile=2048:2048",  # This is required to be able to build a toolchain with crosstool-ng in the container
                        ".",
                    ]
                )

            else:
                raise ValueError(f"Unexpected container tool: {self._container_tool}")

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
            results = self._shell_executor.get_sh_results(
                [self._container_tool, "images", "-q", self._container_image_tagged]
            )
            if results.stdout.splitlines():
                pretty_print.print_build(f"Cleaning container image {self._container_image_tagged}...")
                self._shell_executor.exec_sh_command(
                    [self._container_tool, "image", "rm", self._container_image_tagged]
                )
            else:
                pretty_print.print_build(
                    f"No need to clean container image {self._container_image_tagged}, " "the image doesn't exist..."
                )

        elif self._container_tool == "none":
            # This function is only supported if a container tool is used
            Container_Executor._err_container_feature(f"{inspect.getframeinfo(inspect.currentframe()).function}()")

        else:
            raise ValueError(f"Unexpected container tool: {self._container_tool}")

    def exec_sh_commands(
        self,
        commands: list[str],
        dirs_to_mount: list[tuple[pathlib.Path, str]] = [],
        custom_params: list[str] = [],
        print_commands: bool = False,
        run_as_root: bool = False,
        logfile: pathlib.Path = None,
        output_scrolling: bool = False,
        visible_lines: int = 30,
    ):
        """(Google documentation style:
            https://github.com/google/styleguide/blob/gh-pages/pyguide.md#38-comments-and-docstrings)
        Executes shell commands in a container or directly on the host system. Bash is used to execute the shell
        commands, but it is recommended to use only POSIX shell compatible commands to maintain portability for
        the future.

        Args:
            commands:
                List of commands to execute.
            dirs_to_mount:
                A list of tuples that represent directories to be mounted into the container. Each tuple contains a
                path and a string with the correspondig docker/podman volume mount options. Directories which do not
                exist are ignored.
            custom_params:
                Additional custom parameters that are passed to the containerization tool.
            print_commands:
                Set to True to print every shell command before it is executed in the container
            run_as_root:
                Set to True if the command is to be run as root user.
            logfile:
                Logfile as pathlib.Path object. None if no log file is to be used.
            output_scrolling:
                If True, the output of the shell command is printed in a scrolling view. The printed output is updated
                at runtime and the latest lines are always displayed.
            visible_lines:
                Maximum number of shell output lines to be printed if scolling_output is True. If set to 0, no output
                is visible.

        Returns:
            None

        Raises:
            ValueError:
                If an unexpected container tool is specified
        """

        # Assemble command string for container
        comp_commands = "'"
        if self._enforce_command_printing or print_commands:
            comp_commands = comp_commands + 'trap "echo \\"csc> \$BASH_COMMAND\\"" DEBUG && '
        for i, command in enumerate(commands):
            if i == len(commands) - 1:
                # The last element of the list is treated differently
                comp_commands = comp_commands + command
            else:
                comp_commands = comp_commands + command + " && "
        comp_commands = comp_commands + "'"

        if self._container_tool in ("docker", "podman"):
            # Prepare mounts
            existing_mounts = [mount for mount in dirs_to_mount if mount[0].is_dir()]
            mounts = " ".join([f"-v {i[0]}:{i[0]}:{i[1]}" for i in existing_mounts])

            # Prepare user
            if run_as_root or self._container_tool == "podman":
                # The root user should always be used in podman containers. Using a different user causes permission issues.
                # Files created on the host via mounted directories belong to the user who started the container anyway.
                container_user = "root"
                container_user_id = "0"
            else:
                container_user = self._host_user
                container_user_id = self._host_user_id

            # Run commands in container
            self._shell_executor.exec_sh_command(
                command=[
                    self._container_tool,
                    "run",
                    "--rm",
                    "-it",
                    f"--env CONTAINER_USER={container_user}",
                    f"--env CONTAINER_USER_ID={container_user_id}",
                    mounts,
                ]
                + custom_params
                + [self._container_image_tagged, "bash", "-c", comp_commands],
                logfile=logfile,
                output_scrolling=output_scrolling,
                visible_lines=visible_lines,
            )

        elif self._container_tool == "none":
            # Run commands without using a container

            # Prepare usage of sudo, if necessary
            sudo_opt = ""
            if run_as_root:
                sudo_opt = "sudo --preserve-env=PATH"
                pretty_print.print_warning(
                    "SoCks will use 'sudo --preserve-env=PATH' to execute build commands. "
                    "Enable the containerization feature of SoCks to prevent this, "
                    "or run SoCks entirely in a container to limit the risk."
                )

            self._shell_executor.exec_sh_command(
                command=[sudo_opt, "bash", "-c", comp_commands],
                logfile=logfile,
                output_scrolling=output_scrolling,
                visible_lines=visible_lines,
            )

        else:
            raise ValueError(f"Unexpected container tool: {self._container_tool}")

    def prohibit_output_processing(self, state: bool):
        """
        Enable or disable shell output processing

        Args:
            state:
                True to prohibit processing of shell output, False to allow processing of shell output

        Returns:
            None

        Raises:
            None
        """

        self._shell_executor.prohibit_output_processing(state)

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
            self._shell_executor.exec_sh_command(["docker", "pull", "multiarch/qemu-user-static:register"])
            self._shell_executor.exec_sh_command(
                ["docker", "run", "--rm", "--privileged", "multiarch/qemu-user-static:register", "--reset"]
            )

        elif self._container_tool == "podman":
            self._shell_executor.exec_sh_command(["sudo", "podman", "pull", "multiarch/qemu-user-static:register"])
            self._shell_executor.exec_sh_command(
                ["sudo", "podman", "run", "--rm", "--privileged", "multiarch/qemu-user-static:register", "--reset"]
            )

        elif self._container_tool == "none":
            pretty_print.print_info(f"Multiarch is not activated in native mode.")
            return

        else:
            raise ValueError(f"Unexpected container tool: {self._container_tool}")

    def start_container(self, potential_mounts: list[tuple[pathlib.Path, str]], init_commands: list[str] = []):
        """
        Starts an interactive container with which the block can be built.

        Args:
            potential_mounts:
                List of all directories that could be mounted in the container.
                Existing directories are mounted, non-existing directories are ignored.
            init_commands:
                List of commands to initialize the container.

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

            # Assemble command string for container, if any
            comp_commands = ""
            if init_commands:
                comp_commands = "'"
                for i, command in enumerate(init_commands):
                    if i == len(init_commands) - 1:
                        # The last element of the list is treated differently
                        comp_commands = comp_commands + command + " && exec bash"
                    else:
                        comp_commands = comp_commands + command + " && "
                comp_commands = comp_commands + "'"

            # Prepare user
            if self._container_tool == "podman":
                # The root user should always be used in podman containers. Using a different user causes permission issues.
                # Files created on the host via mounted directories belong to the user who started the container anyway.
                container_user = "root"
                container_user_id = "0"
            else:
                container_user = self._host_user
                container_user_id = self._host_user_id

            pretty_print.print_build("Starting container...")

            if comp_commands:
                self._shell_executor.exec_sh_command(
                    command=[
                        self._container_tool,
                        "run",
                        "--rm",
                        "-it",
                        f"--env CONTAINER_USER={container_user}",
                        f"--env CONTAINER_USER_ID={container_user_id}",
                        mounts,
                        self._container_image_tagged,
                        "bash",
                        "-c",
                        comp_commands,
                    ],
                    check=False,
                )
            else:
                self._shell_executor.exec_sh_command(
                    command=[
                        self._container_tool,
                        "run",
                        "--rm",
                        "-it",
                        f"--env CONTAINER_USER={container_user}",
                        f"--env CONTAINER_USER_ID={container_user_id}",
                        mounts,
                        self._container_image_tagged,
                    ],
                    check=False,
                )

        elif self._container_tool == "none":
            # This function is only supported if a container tool is used
            Container_Executor._err_container_feature(f"{inspect.getframeinfo(inspect.currentframe()).function}()")

        else:
            raise ValueError(f"Unexpected container tool: {self._container_tool}")

    def start_gui_container(self, start_gui_commands: list[str], potential_mounts: list[tuple[pathlib.Path, str]]):
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
        results = self._shell_executor.get_sh_results(command=["command", "-v", "x11docker"], check=False)
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
            self._shell_executor.exec_sh_command(
                [
                    "x11docker",
                    "--backend=docker",
                    "--interactive",
                    "--network",
                    "--clipboard=yes",
                    "--xauth=trusted",
                    f"--user={self._host_user_id}:{self._host_user_id}",  # Replaces the entrypoint script in GUI containers
                    "--no-entrypoint",  # The entrypoint script doesn't work if x11docker uses the docker backend
                    mounts,
                    self._container_image_tagged,
                    f"--runasuser={comp_commands}",
                ]
            )

        elif self._container_tool == "podman":
            self._shell_executor.exec_sh_command(
                [
                    "x11docker",
                    "--backend=podman",
                    "--interactive",
                    "--network",
                    "--clipboard=yes",
                    "--xauth=trusted",
                    "--cap-default",
                    "--user=RETAIN",
                    f"--env CONTAINER_USER={self._host_user}",
                    f"--env CONTAINER_USER_ID={self._host_user_id}",
                    mounts,
                    self._container_image_tagged,
                    f"--runasuser={comp_commands}",
                ]
            )

        elif self._container_tool == "none":
            # This function is only supported if a container tool is used
            Container_Executor._err_container_feature(f"{inspect.getframeinfo(inspect.currentframe()).function}()")

        else:
            raise ValueError(f"Unexpected container tool: {self._container_tool}")

    def enforce_command_printing(self, state: bool):
        """
        Enable or disable shell output processing

        Args:
            state:
                True to enforce the printing of shell command before they are executed in the container,
                False to optionally allow the printing of commands.

        Returns:
            None

        Raises:
            None
        """

        self._enforce_command_printing = state
