import typing
import os
import pathlib
import sys
from dateutil import parser
import inspect
import subprocess

import socks.pretty_print as pretty_print
from socks.shell_command_runners import Shell_Command_Runners

class Containerization:
    """
    A class to execute commands and tasks in containers
    """

    def __init__(self, container_tool: str, container_file: pathlib.Path, container_image: str):

        if container_tool not in ['docker', 'podman', 'none']:
            pretty_print.print_error(f'Containerization tool {self._container_tool} is not supported.')
            sys.exit(1)

        # The container tool to be used. 'none' if the command is to be run directly on the host system.
        self._container_tool = container_tool
        # The container file to be user as source for building.
        self._container_file = container_file
        # Identifier of the container image in format <image name>:<image tag>.
        self._container_image = container_image


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

        pretty_print.print_error(f'{feature} is only available if a containerization tool is used.')
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
            None
        """

        # Check if the required container file exists
        if not self._container_file.is_file():
            pretty_print.print_error(f'File {self._container_file} not found.')
            sys.exit(1)

        if self._container_tool  == 'docker':
            # Get last tag time from docker
            results = Shell_Command_Runners.get_sh_results(['docker', 'image', 'inspect',
                        '-f \'{{ .Metadata.LastTagTime }}\'', self._container_image])
            # Do not extract tag time if the image does not yet exist
            if f'No such image: {self._container_image}' in results.stderr:
                last_tag_timestamp = 0
            else:
                last_tag_timestamp = parser.parse(results.stdout.rpartition(' ')[0]).timestamp()
            # Get last modification time of the container file
            last_file_mod_timestamp = self._container_file.stat().st_mtime
            # Build image, if necessary
            if last_tag_timestamp < last_file_mod_timestamp:
                host_user = os.getlogin()
                host_user_id = os.getuid()
                pretty_print.print_build(f'Building docker image {self._container_image}...')
                Shell_Command_Runners.run_sh_command(['docker', 'build', '-t', self._container_image,
                            '-f', str(self._container_file), '--build-arg', f'user_name={host_user}',
                            '--build-arg', f'user_id={host_user_id}', '.'])
            else:
                pretty_print.print_build(f'No need to build the docker image {self._container_image}...')

        elif self._container_tool  == 'podman':
            # Get last build event time from podman
            results = Shell_Command_Runners.get_sh_results(['podman', 'image', 'inspect', '-f', '\'{{ .Id }}\'',
                        self._container_image, '|', 'xargs', '-I', '{}', 'podman', 'events', '--filter', 'image={}',
                        '--filter', 'event=build', '--format', '\'{{.Time}}\'', '--until', '0m'])
            # Do not extract last build event time if the image does not yet exist
            if f'{self._container_image}: image not known' in results.stderr:
                last_build_time_timestamp = 0
            else:
                last_build_time_timestamp = parser.parse(results.stdout.splitlines()[-2].rpartition(' ')[0]).timestamp()
            # Get last modification time of the container file
            last_file_mod_timestamp = self._container_file.stat().st_mtime
            # Build image, if necessary
            if last_build_time_timestamp < last_file_mod_timestamp:
                pretty_print.print_build(f'Building podman image {self._container_image}...')
                Shell_Command_Runners.run_sh_command(['podman', 'build', '-t', self._container_image,
                            '-f', str(self._container_file), '.'])
            else:
                pretty_print.print_build(f'No need to build the podman image {self._container_image}...')

        elif self._container_tool  == 'none':
            pretty_print.print_warning('Container image is not built in native mode.')


    def clean_container_image(self):
        """
        Cleans the container image of the selected container tool.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        if self._container_tool  in ('docker', 'podman'):
            # Clean image only if it exists
            results = Shell_Command_Runners.get_sh_results([self._container_tool , 'images', '-q',
                        self._container_image])
            if results.stdout.splitlines():
                pretty_print.print_build(f'Cleaning container image {self._container_image}...')
                Shell_Command_Runners.run_sh_command([self._container_tool , 'image', 'rm', self._container_image])
            else:
                pretty_print.print_build(f'No need to clean container image {self._container_image}, ' \
                            'the image doesn\'t exist...')

        elif self._container_tool  == 'none':
            # This function is only supported if a container tool is used
            Containerization._err_container_feature(f'{inspect.getframeinfo(inspect.currentframe()).function}()')


    def run_containerizable_sh_command(self, command: str,
                                        dirs_to_mount: typing.List[typing.Tuple[pathlib.Path, str]] = [],
                                        custom_params: typing.List[str] = [], run_as_root: bool = False):
        """ (Google documentation style:
            https://github.com/google/styleguide/blob/gh-pages/pyguide.md#38-comments-and-docstrings)
        Runs a sh command in a container or directly on the host system.

        Args:
            command:
                The command to execute.
            dirs_to_mount:
                A list of tuples that represent directories to be mounted into the container. Each tuple contains a
                path and a string with the correspondig docker/podman volume mount options.
            custom_params:
                Additional custom parameters that are passed to the containerization tool.
            run_as_root:
                Set to True if the command is to be run as root user.

        Returns:
            None

        Raises:
            ValueError: If argument 'command' does not start and end with a single quote
        """

        if not command.startswith(('\'', '\"')) or not command.endswith(('\'', '\"')):
            raise ValueError('Argument \'command\' must start and end with a single or double quote.')

        if self._container_tool  in ('docker', 'podman'):
            mounts = ' '.join([f'-v {i[0]}:{i[0]}:{i[1]}' for i in dirs_to_mount])
            # Run commands in container
            user_opt = '-u root' if run_as_root else ''
            Shell_Command_Runners.run_sh_command([self._container_tool , 'run', '--rm', '-it', user_opt, mounts] +
                        custom_params + [self._container_image, 'sh', '-c', command])
        elif self._container_tool  == 'none':
            # Run commands without using a container
            sudo_opt = 'sudo' if run_as_root else ''
            Shell_Command_Runners.run_sh_command([sudo_opt, 'sh', '-c', command])


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
            None
        """

        if list(pathlib.Path('/proc/sys/fs/binfmt_misc').glob('qemu-*')):
            pretty_print.print_build('No need to activate multiarch support for containers. It is already active...')
            return

        pretty_print.print_build('Activating multiarch support for containers...')

        if self._container_tool  == 'docker':
            Shell_Command_Runners.run_sh_command(['docker', 'pull', 'multiarch/qemu-user-static'])
            Shell_Command_Runners.run_sh_command(['docker', 'run', '--rm', '--privileged',
                        'multiarch/qemu-user-static', '--reset', '-p', 'yes'])
        elif self._container_tool  == 'podman':
            Shell_Command_Runners.run_sh_command(['sudo', 'podman', 'pull', 'multiarch/qemu-user-static'])
            Shell_Command_Runners.run_sh_command(['sudo', 'podman', 'run', '--rm', '--privileged',
                        'multiarch/qemu-user-static', '--reset', '-p', 'yes'])
        elif self._container_tool  == 'none':
            pretty_print.print_warning(f'Multiarch is not activated in native mode.')
            return


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
            None
        """

        if self._container_tool  in ('docker', 'podman'):
            # Check which mounts (resp. directories) are available on the host system
            existing_mounts = [mount for mount in potential_mounts if mount[0].is_dir()]
            mounts = ' '.join([f'-v {i[0]}:{i[0]}:{i[1]}' for i in existing_mounts])

            pretty_print.print_build('Starting container...')

            try:
                Shell_Command_Runners.run_sh_command([self._container_tool , 'run', '--rm', '-it', mounts,
                            self._container_image])
            except subprocess.CalledProcessError:
                # It is okay if the interactive shell session is ended with an exit code not equal to 0
                pass

        elif self._container_tool  == 'none':
            # This function is only supported if a container tool is used
            Containerization._err_container_feature(f'{inspect.getframeinfo(inspect.currentframe()).function}()')


    def start_gui_container(self, start_gui_command: str, potential_mounts: typing.List[typing.Tuple[pathlib.Path, str]]):
        """
        Starts an interactive container with which the block can be built.

        Args:
            start_gui_command:
                Commands to be used to start the GUI in the container.
            potential_mounts:
                List of all directories that could be mounted in the container.
                Existing directories are mounted, non-existing directories are ignored.

        Returns:
            None

        Raises:
            None
        """

        # Check if x11docker is installed
        results = Shell_Command_Runners.get_sh_results(['command', '-v', 'x11docker'])
        if not results.stdout:
            pretty_print.print_error('Command \'x11docker\' not found. Install x11docker (https://github.com/mviereck/x11docker).')
            sys.exit(1)

        # Check which mounts (resp. directories) are available on the host system
        existing_mounts = [mount for mount in potential_mounts if mount[0].is_dir()]
        mounts = ' '.join([f'--share {i[0]}:{i[1]}' if i[1] == 'ro' else f'--share {i[0]}' for i in existing_mounts])

        pretty_print.print_build('Starting container...')

        if self._container_tool  == 'docker':
            Shell_Command_Runners.run_sh_command(['x11docker' , '--backend=docker', '--interactive', '--network',
                        '--clipboard=yes', '--xauth=trusted', '--user=RETAIN', mounts, self._container_image,
                        f'--runasuser={start_gui_command}'])
        elif self._container_tool  == 'podman':
            Shell_Command_Runners.run_sh_command(['x11docker' , '--backend=podman', '--interactive', '--network',
                        '--clipboard=yes', '--xauth=trusted', '--cap-default', '--user=RETAIN', mounts,
                        self._container_image, f'--runasuser={start_gui_command}'])
        elif self._container_tool  == 'none':
            # This function is only supported if a container tool is used
            Containerization._err_container_feature(f'{inspect.getframeinfo(inspect.currentframe()).function}()')