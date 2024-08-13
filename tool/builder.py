import os
import sys
import subprocess
import select
import datetime
from dateutil import parser
import inspect

import pretty_print

class Builder:
    """
    Base class for all builder classes
    """

    def __init__(self, socks_dir, block_name, project_dir, source_repo_name, source_repo_url, source_repo_branch, container_tool, container_image, vivado_dir, vitis_dir):
        self._block_name = block_name

        # Host user
        self._host_user = os.getlogin()
        self._host_user_id = os.getuid()

        # Container
        self._container_tool = container_tool
        self._container_image = container_image

        # Local git branches
        self._git_local_ref_branch = '__ref'
        self._git_local_dev_branch = '__temp'
        
        # Repo
        self._source_repo_url = source_repo_url
        self._source_repo_branch = source_repo_branch

        # SoCks directorys (ToDo: If there is more like this needed outside of the blocks, maybe there should be a SoCks or tool class)
        self._socks_dir = socks_dir
        self._container_dir = self._socks_dir+'/container/'
        self._vivado_dir = vivado_dir
        self._vitis_dir = vitis_dir
        
        # Project directories
        self._project_dir = project_dir
        self._patch_dir = self._project_dir+'/'+self._block_name+'/patches/'
        self._repo_dir = self._project_dir+'/temp/'+self._block_name+'/repo/'
        self._source_repo_dir = self._repo_dir+source_repo_name+'-'+self._source_repo_branch+'/'
        self._xsa_dir = self._project_dir+'/temp/'+self._block_name+'/source_xsa/'
        self._work_dir = self._project_dir+'/temp/'+self._block_name+'/work/'
        self._output_dir = self._project_dir+'/temp/'+self._block_name+'/output/'

        # Project files
        # Flag to remember if patches have already been applied
        self._patches_applied_flag = self._project_dir+'/temp/'+self._block_name+'/.patchesapplied'
        # File containing all patches to be used
        self._patch_cfg_file = self._patch_dir+'/.patches.cfg'


    @staticmethod
    def _run_sh_command(command, logfile=None, scrolling_output=False, visible_lines=20):
        """ (Google documentation style: https://github.com/google/styleguide/blob/gh-pages/pyguide.md#38-comments-and-docstrings)
        Runs a sh command. If the srolling view is enabled or the output is to be logged,
        this function loses some output of commands that display a progress bar or
        someting similar. The 'tee' shell command has the same issue.

        Args:
            command:
                The command to execute. Example: '/usr/bin/ping www.google.com'.
                The executable should be given with the full path, as mentioned
                here: https://docs.python.org/3/library/subprocess.html#subprocess.Popen
            logfile:
                Path of the logfile. None if no log file is to be used.
            scrolling_output:
                If True, the output of the sh command is printed in a scrolling view.
                The printed output is updated at runtime and the latest lines are
                always displayed.
            visible_lines:
                Maximum number of sh output lines to be printed if scolling_output
                is True. If set to 0, no output is visible.

        Returns:
            None

        Raises:
            subprocess.CalledProcessError: If the return code of the subprocess is not 0 
        """

        # If scolling output is disabled and the output should not be hidden or logged, subprocess.run can be used to run the subprocess
        if scrolling_output == False and visible_lines != 0 and logfile == None:
            subprocess.run(' '.join(command), shell=True, check=True)
            return

        # Prepare to process the command line output of the command
        printed_lines = 0
        last_lines = []

        def update_last_lines(line):
            if visible_lines <= 0:
                return
            if len(last_lines) >= visible_lines:
                last_lines.pop(0)
            last_lines.append(line)
        
        # Start the subprocess
        process = subprocess.Popen(' '.join(command), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Continuously read from the process output
        while True:
            try:
                # Wait for any of the pipes to have available data
                readable = select.select([process.stdout, process.stderr], [], [])[0]
            
            except KeyboardInterrupt:
                # Gracefully handle Ctrl+C
                process.kill()

            # Read one line from the pipe(s) in which data is available
            stdout_line = None
            if process.stdout in readable:
                stdout_line = process.stdout.readline()

            stderr_line = None
            if process.stderr in readable:
                stderr_line = process.stderr.readline()

            # If both are empty and the process is done, break
            if not stdout_line and not stderr_line and process.poll() is not None:
                break

            # If provided, write to log file
            if logfile:
                if stdout_line:
                    print(stdout_line, file=open(logfile, 'a'), end='')
                if stderr_line:
                    print(stderr_line, file=open(logfile, 'a'), end='')

            # If enabled, show output of the command
            if visible:
                if stdout_line:
                    update_last_lines(stdout_line)
                if stderr_line:
                    update_last_lines(stderr_line)

                # Clear previous output
                for _ in range(printed_lines):
                    # Move the cursor up one line
                    print('\033[F', end='')
                    # Clear the line
                    print('\033[K', end='')

                # Print output
                printed_lines = 0
                for line in last_lines:
                    print(line, end='', flush=True)
                    printed_lines += 1

        # Close the streams
        process.stdout.close()
        process.stderr.close()
        process.wait()

        # Check return code
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, ' '.join(command))


    @staticmethod
    def _get_sh_results(command):
        """ (Google documentation style: https://github.com/google/styleguide/blob/gh-pages/pyguide.md#38-comments-and-docstrings)
        Runs a sh command and get all output.

        Args:
            command:
                The command to execute. Example: '/usr/bin/ping www.google.com'.
                The executable should be given with the full path, as mentioned
                here: https://docs.python.org/3/library/subprocess.html#subprocess.Popen

        Returns:
            An object that contains stdout (str), stderr (str) and returncode (int)

        Raises:
            None
        """

        result = subprocess.run(' '.join(command), shell=True, capture_output=True, text=True, check=False)

        return result


    @staticmethod
    def _err_unsup_container_tool():
        """
        Display an error message that the requested container tool is not supported.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        pretty_print.print_error('Containerization tool '+self._container_tool+' is not supported. Options are \'docker\', \'podman\' and \'none\'.')
        sys.exit(1)
    

    @staticmethod
    def _err_container_feature(feature):
        """
        Display an error message that the requested feature is only available if a container tool is used.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        pretty_print.print_error(feature+' is only available if a containerization tool is used.')
        sys.exit(1)


    def build_container_image(self):
        """
        Builds the container image for the selected container tool.

        The container management tool (podman/docker) will restore everything that has not changed in the containerfile from the cache.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check if the required container file exists
        if not os.path.isfile(self._container_dir+'/'+self._container_image+'.containerfile'):
            pretty_print.print_error('File '+self._container_dir+'/'+self._container_image+'.containerfile not found.')
            sys.exit(1)

        try:
            if self._container_tool == 'docker':
                # Get last tag time from docker
                results = Builder._get_sh_results(['docker', 'image', 'inspect', '-f \'{{ .Metadata.LastTagTime }}\'', self._container_image])
                # Do not extract tag time if the image does not yet exist
                if 'No such image: '+self._container_image in results.stderr:
                    last_tag_time_timestamp = 0
                else:
                    last_tag_time_timestamp = parser.parse(results.stdout.rpartition(' ')[0]).timestamp()
                # Get last modification time of the container file
                last_file_mod_time_timestamp = os.path.getmtime(self._container_dir+'/'+self._container_image+'.containerfile')
                # Build image, if necessary
                if last_tag_time_timestamp < last_file_mod_time_timestamp:
                    pretty_print.print_build('Building docker image '+self._container_image+'...')
                    Builder._run_sh_command(['docker', 'build', '-t', self._container_image, '-f', self._container_dir+'/'+self._container_image+'.containerfile', '--build-arg', 'user_name='+self._host_user, '--build-arg', 'user_id='+str(self._host_user_id), '.'])
                else:
                    pretty_print.print_build('No need to build the docker image '+self._container_image+'...')

            elif self._container_tool == 'podman':
                # Get last build event time from podman
                results = Builder._get_sh_results(['podman', 'image', 'inspect', '-f', '\'{{ .Id }}\'', self._container_image, '|', 'xargs', '-I', '{}', 'podman', 'events', '--filter', 'image={}', '--filter', 'event=build', '--format', '\'{{.Time}}\'', '--until', '0m'])
                # Do not extract last build event time if the image does not yet exist
                if self._container_image+': image not known' in results.stderr:
                    last_build_time_timestamp = 0
                else:
                    last_build_time_timestamp = parser.parse(results.stdout.splitlines()[-2].rpartition(' ')[0]).timestamp()
                # Get last modification time of the container file
                last_file_mod_time_timestamp = os.path.getmtime(self._container_dir+'/'+self._container_image+'.containerfile')
                # Build image, if necessary
                if last_build_time_timestamp < last_file_mod_time_timestamp:
                    pretty_print.print_build('Building podman image '+self._container_image+'...')
                    Builder._run_sh_command(['podman', 'build', '-t', self._container_image, '-f', self._container_dir+'/'+self._container_image+'.containerfile', '.'])
                else:
                    pretty_print.print_build('No need to build the podman image '+self._container_image+'...')

            elif self._container_tool == 'none':
                pretty_print.print_warning('Container image is not built in native mode.')
            else:
                Builder._err_unsup_container_tool()
        except Exception as e:
                pretty_print.print_error('An error occurred while building the container image: '+str(e))
                sys.exit(1)


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

        if self._container_tool in ('docker', 'podman'):
            try:
                # Clean image only if it exists
                results = Builder._get_sh_results([self._container_tool, 'images', '-q', self._container_image])
                if results.stdout.splitlines():
                    pretty_print.print_build('Cleaning container image '+self._container_image+'...')
                    Builder._run_sh_command([self._container_tool, 'image', 'rm', self._container_image])
                else:
                    pretty_print.print_build('No need to clean container image '+self._container_image+', the image doesn\'t exist...')
            except Exception as e:
                pretty_print.print_error('An error occurred while cleaning the container image: '+str(e))
                sys.exit(1)

        elif self._container_tool == 'none':
            Builder._err_container_feature(inspect.getframeinfo(inspect.currentframe()).function+'()')
        else:
            Builder._err_unsup_container_tool()


    def start_container(self):
        """
        Start an interactive container with which the block can be built.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        if self._container_tool in ('docker', 'podman'):
            try:
                pretty_print.print_build('Starting container...')
                # A complete list of all container mounts supported by SoCks
                potential_mounts = [self._xsa_dir+':Z', self._vivado_dir+':ro', self._vitis_dir+':ro', self._repo_dir+':Z', self._work_dir+':Z', self._output_dir+':Z']
                available_mounts = []
                # Check which mounts (resp. directories) are available on the host system
                for mount in potential_mounts:
                    segments = mount.split(':')
                    if len(segments) != 2:
                        pretty_print.print_error('The following path contains a forbidden colon: '+mount.rpartition(':')[0])
                        sys.exit(1)
                    if os.path.isdir(segments[0]):
                        available_mounts.append(segments[0]+':'+segments[0]+':'+segments[1])
                # Start the container
                Builder._run_sh_command([self._container_tool, 'run', '--rm', '-it', '-v', ' -v '.join(available_mounts), self._container_image])
            except Exception as e:
                pretty_print.print_error('An error occurred while starting the container: '+str(e))
                sys.exit(1)

        elif self._container_tool == 'none':
            Builder._err_container_feature(inspect.getframeinfo(inspect.currentframe()).function+'()')
        else:
            Builder._err_unsup_container_tool()


    def init_repo(self):
        """
        Clones and initializes the git repo.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Skip all operations if the repo already exists
        if not os.path.isdir(self._source_repo_dir):
            pretty_print.print_build('Fetching repo...')
            try:
                os.makedirs(self._output_dir, exist_ok=True)
                os.makedirs(self._repo_dir, exist_ok=True)

                # Clone the repo
                Builder._run_sh_command(['git', 'clone', '--recursive', '--branch', self._source_repo_branch, self._source_repo_url, self._source_repo_dir])
                # Create new branch self._git_local_ref_branch. This branch is used as a reference where all existing patches are applied to the git sources
                Builder._run_sh_command(['git', '-C', self._source_repo_dir, 'switch', '-c', self._git_local_ref_branch])
                # Create new branch self._git_local_dev_branch. This branch is used as the local development branch. New patches can be created from this branch.
                Builder._run_sh_command(['git', '-C', self._source_repo_dir, 'switch', '-c', self._git_local_dev_branch])
            except Exception as e:
                pretty_print.print_error('An error occurred while initializing the repository: '+str(e))
                sys.exit(1)
        else:
            pretty_print.print_build('No need to fetch the repo...')


    def apply_patches(self):
        """
        This function iterates over all patches listed in self._patch_cfg_file and
        applies them to the repo.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Skip all operations if the patches have already been applied
        if not os.path.isfile(self._patches_applied_flag):
            pretty_print.print_build('Applying patches...')
            try:
                if os.path.isfile(self._patch_cfg_file):
                    with open(self._patch_cfg_file, 'r') as patches:
                        for patch in patches:
                            if patch:
                                # Apply patch
                                Builder._run_sh_command(['git', '-C', self._source_repo_dir, 'am', self._patch_dir+'/'+patch])
                
                # Update the branch self._git_local_ref_branch so that it contains the applied patches and is in sync with self._git_local_dev_branch. This is important to be able to create new patches.
                Builder._run_sh_command(['git', '-C', self._source_repo_dir, 'checkout', self._git_local_ref_branch])
                Builder._run_sh_command(['git', '-C', self._source_repo_dir, 'merge', self._git_local_dev_branch])
                Builder._run_sh_command(['git', '-C', self._source_repo_dir, 'checkout', self._git_local_dev_branch])
                # Create the flag if it doesn't exist and update the timestamps
                with open(self._patches_applied_flag, 'w'):
                    os.utime(self._patches_applied_flag, None)
            except Exception as e:
                pretty_print.print_error('An error occurred while applying patches: '+str(e))
                sys.exit(1)
        else:
            pretty_print.print_build('No need to apply patches...')


    def clean_repo(self):
        """
        This function cleans the git repo directory.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        if os.path.isdir(self._repo_dir):
            # Check if there are uncommited changes in the git repo
            results = Builder._get_sh_results(['git', '-C', self._source_repo_dir, 'status', '--porcelain'])
            if results.stdout:
                pretty_print.print_warning('There are uncommited changes in '+self._source_repo_dir+'. Do you really want to clean this repo? (y/n) ', end='')
                answer = input('')
                if answer.lower() not in ['y', 'Y', 'yes', 'Yes']:
                    pretty_print.print_clean('Cleaning abborted...')
                    sys.exit(1)

            pretty_print.print_clean('Cleaning repo directory...')
            if self._container_tool in ('docker', 'podman'):
                try:
                    # Clean up the repo from the container
                    Builder._run_sh_command([self._container_tool, 'run', '--rm', '-it', '-v', self._repo_dir+':/app/repo:Z', self._container_image, 'sh', '-c', '\"rm -rf /app/repo/* /app/repo/.* 2> /dev/null || true\"'])
                except Exception as e:
                    pretty_print.print_error('An error occurred while cleaning the repo directory: '+str(e))
                    sys.exit(1)

            elif self._container_tool == 'none':
                # Clean up the repo without using a container
                Builder._run_sh_command(['sh', '-c', '\"rm -rf '+self._repo_dir+'/* '+self._repo_dir+'/.* 2> /dev/null || true\"'])
            else:
                Builder._err_unsup_container_tool()

            # Remove flag
            if os.path.isfile(self._patches_applied_flag):
                os.remove(self._patches_applied_flag)

            # Remove empty repo directory
            os.rmdir(self._repo_dir)

        else:
            pretty_print.print_clean('No need to clean the repo directory...')


    def clean_output(self):
        """
        This function cleans the git repo directory.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        if os.path.isdir(self._output_dir):
            pretty_print.print_clean('Cleaning output directory...')
            if self._container_tool in ('docker', 'podman'):
                try:
                    # Clean up the repo from the container
                    Builder._run_sh_command([self._container_tool, 'run', '--rm', '-it', '-v', self._output_dir+':/app/output:Z', self._container_image, 'sh', '-c', '\"rm -rf /app/output/* /app/output/.* 2> /dev/null || true\"'])
                except Exception as e:
                    pretty_print.print_error('An error occurred while cleaning the output directory: '+str(e))
                    sys.exit(1)

            elif self._container_tool == 'none':
                # Clean up the repo without using a container
                Builder._run_sh_command(['sh', '-c', '\"rm -rf '+self._output_dir+'/* '+self._output_dir+'/.* 2> /dev/null || true\"'])
            else:
                Builder._err_unsup_container_tool()

            # Remove empty output directory
            os.rmdir(self._output_dir)

        else:
            pretty_print.print_clean('No need to clean the output directory...')