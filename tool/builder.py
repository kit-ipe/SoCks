import typing
import os
import pathlib
import shutil
import sys
import subprocess
import select
import datetime
from dateutil import parser
import inspect
import urllib
import requests
import validators
import tqdm
import tarfile

import pretty_print

class Builder:
    """
    Base class for all builder classes
    """

    def __init__(self, project_cfg: dict, socks_dir: pathlib.Path, project_dir: pathlib.Path, block_name: str):
        self._block_name = block_name

        # Project configuration
        self._project_cfg = project_cfg

        # Host user
        self._host_user = os.getlogin()
        self._host_user_id = os.getuid()

        # Container
        self._container_tool = self._project_cfg['externalTools']['containerTool']
        self._container_image = f'{self._project_cfg["blocks"][self._block_name]["container"]["image"]}:xilinx-v{self._project_cfg["externalTools"]["xilinx"]["version"]}'

        # Local git branches
        self._git_local_ref_branch = '__ref'
        self._git_local_dev_branch = '__temp'
        
        # Sources for this block
        if self._project_cfg['blocks'][self._block_name]['project'] is None or 'sources' not in self._project_cfg['blocks'][self._block_name]['project']:
            # The sources for this block are generated at runtime
            self._source_repo_url = None
            self._source_repo_branch = 'temp'
            source_repo_name = 'generated'
        else:
            sources_str = self._project_cfg['blocks'][self._block_name]['project']['sources']
            if validators.url(sources_str):
                # The sources for this block are downloaded from git
                self._source_repo_url = sources_str
                if 'branch' in self._project_cfg['blocks'][self._block_name]['project']:
                    self._source_repo_branch = self._project_cfg['blocks'][self._block_name]['project']['branch']
                else:
                    self._source_repo_branch = f'xilinx-v{self._project_cfg["externalTools"]["xilinx"]["version"]}'
                source_repo_name = pathlib.Path(urllib.parse.urlparse(self._source_repo_url).path).stem
            else:
                try:
                    # The sources for this block are provided locally
                    pathlib.Path(sources_str)
                    pretty_print.print_error(f'It is not yet supported to use local sources, but the following path was provided as source: {sources_str}')
                    sys.exit(1)
                except ValueError:
                    pretty_print.print_error(f'{sources_str} is not a valid URL and not a valid path')
                    sys.exit(1)

        # SoCks directorys (ToDo: If there is more like this needed outside of the blocks, maybe there should be a SoCks or tool class)
        self._socks_dir = socks_dir
        self._container_dir = self._socks_dir / 'container'
        
        # Project directories
        self._project_dir = project_dir
        self._project_temp_dir = self._project_dir / 'temp'
        self._patch_dir = self._project_dir / self._block_name / 'patches'
        self._repo_dir = self._project_temp_dir / self._block_name / 'repo'
        self._source_repo_dir = self._repo_dir / f'{source_repo_name}-{self._source_repo_branch}'
        self._download_dir = self._project_temp_dir / self._block_name / 'download'
        self._work_dir = self._project_temp_dir / self._block_name / 'work'
        self._output_dir = self._project_temp_dir / self._block_name / 'output'
        self._dependencies_dir = self._project_temp_dir / self._block_name / 'dependencies'

        # Project files
        # Container file for creating the container to be used for building this block
        self._container_file = self._container_dir / f'{self._container_image}.containerfile'
        # ASCII file with all patches in the order in which they are to be applied
        self._patch_list_file = self._patch_dir / 'patches.cfg'
        # Flag to remember if patches have already been applied
        self._patches_applied_flag = self._project_temp_dir / self._block_name / '.patchesapplied'


    @staticmethod
    def _run_sh_command(command: typing.List[str], logfile: pathlib.Path = None, scrolling_output: bool = False, visible_lines: int = 20):
        """ (Google documentation style: https://github.com/google/styleguide/blob/gh-pages/pyguide.md#38-comments-and-docstrings)
        Runs a sh command. If the srolling view is enabled or the output is to be logged,
        this function loses some output of commands that display a progress bar or
        someting similar. The 'tee' shell command has the same issue.

        Args:
            command:
                The command to execute as a list of strings. Example: ['/usr/bin/ping', 'www.google.com'].
                The executable should be given with the full path, as mentioned
                here: https://docs.python.org/3/library/subprocess.html#subprocess.Popen
            logfile:
                Logfile as pathlib.Path object. None if no log file is to be used.
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
                with logfile.open('a') as f:
                    if stdout_line:
                        print(stdout_line, file=f, end='')
                    if stderr_line:
                        print(stderr_line, file=f, end='')

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
    def _get_sh_results(command: typing.List[str]) -> subprocess.CompletedProcess:
        """ (Google documentation style: https://github.com/google/styleguide/blob/gh-pages/pyguide.md#38-comments-and-docstrings)
        Runs a sh command and get all output.

        Args:
            command:
                The command to execute as a list of strings. Example: ['/usr/bin/ping', 'www.google.com'].
                The executable should be given with the full path, as mentioned
                here: https://docs.python.org/3/library/subprocess.html#subprocess.Popen

        Returns:
            An object that contains stdout (str), stderr (str) and returncode (int).

        Raises:
            None
        """

        result = subprocess.run(' '.join(command), shell=True, capture_output=True, text=True, check=False)

        return result


    @staticmethod
    def _find_last_modified_file(search_list: typing.List[pathlib.Path], ignore_list: typing.List[pathlib.Path] = None) -> typing.Optional[pathlib.Path]:
        """
        Find the last modified file in a list of directories, whereby files and directories can be ignored.

        Args:
            search_list:
                List of directories and files to be searched for the most
                recently modified file.
            ignore_list:
                List of directories and files to be ignored when searching
                for the most recently modified file.

        Returns:
            The most recently modified file.

        Raises:
            None
        """

        # Initialize variables to keep track of the most recently modified file
        latest_file = None
        latest_mtime = 0

        for search_path in search_list:
            # Skip if the file or directory is in the ignore list
            if ignore_list:
                if any(search_path.samefile(ignore_path) for ignore_path in ignore_list):
                    continue

            if search_path.is_dir():
                subdir_search_list = list(search_path.iterdir())
                if subdir_search_list:
                    latest_file_subdir = Builder._find_last_modified_file(search_list=subdir_search_list, ignore_list=ignore_list)
                    if latest_file_subdir:
                        # Get the modification time of the file
                        file_mtime = latest_file_subdir.stat().st_mtime
                        # Update if this file is more recently modified
                        if file_mtime > latest_mtime:
                            latest_mtime = file_mtime
                            latest_file = latest_file_subdir
                        continue

            else:
                # Get the modification time of the file
                file_mtime = search_path.stat().st_mtime
                # Update if this file is more recently modified
                if file_mtime > latest_mtime:
                    latest_mtime = file_mtime
                    latest_file = search_path

        return latest_file


    @staticmethod
    def _check_rebuilt_required(src_search_list: typing.List[pathlib.Path], src_ignore_list: typing.List[pathlib.Path] = None, out_search_list: typing.List[pathlib.Path] = None, out_ignore_list: typing.List[pathlib.Path] = None) -> bool:
        """
        Check whether some file(s) needs to be rebuilt.

        Args:
            src_search_list:
                List of directories and files to be searched for the most
                recently modified source file.
            src_ignore_list:
                List of directories and files to be ignored when searching
                for the most recently modified source file.
            out_search_list:
                List of directories and files to be searched for the most
                recently modified output file.
            out_ignore_list:
                List of directories and files to be ignored when searching
                for the most recently modified output file.

        Returns:
            True if a rebuild is required, i.e. if the source files are newer
            than the output files. False if a rebuild is not required, i.e.
            if the output files are newer than the source files.

        Raises:
            None
        """

        # Remove non-existing files and directories
        if src_search_list:
            src_search_list = [path for path in src_search_list if path.exists()]
        if src_ignore_list:
            src_ignore_list = [path for path in src_ignore_list if path.exists()]
        if out_search_list:
            out_search_list = [path for path in out_search_list if path.exists()]
        if out_ignore_list:
            out_ignore_list = [path for path in out_ignore_list if path.exists()]

        # Find last modified source file
        latest_src_file = Builder._find_last_modified_file(search_list=src_search_list, ignore_list=src_ignore_list)

        # Find last modified output file
        if(out_search_list):
            latest_out_file = Builder._find_last_modified_file(search_list=out_search_list, ignore_list=out_ignore_list)
        else:
            latest_out_file = None

        # If there are source and output files, check whether a rebuild is required
        if latest_src_file and latest_out_file:
            return latest_src_file.stat().st_mtime > latest_out_file.stat().st_mtime

        # A rebuild is required if source or output files are missing
        else:
            return True


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

        pretty_print.print_error(f'Containerization tool {self._container_tool} is not supported. Options are \'docker\', \'podman\' and \'none\'.')
        sys.exit(1)
    

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

        The container management tool (podman/docker) will restore everything that has not changed in the containerfile from the cache.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Check if the required container file exists
        if not self._container_file.is_file():
            pretty_print.print_error(f'File {str(self._container_file)} not found.')
            sys.exit(1)

        try:
            if self._container_tool == 'docker':
                # Get last tag time from docker
                results = Builder._get_sh_results(['docker', 'image', 'inspect', '-f \'{{ .Metadata.LastTagTime }}\'', self._container_image])
                # Do not extract tag time if the image does not yet exist
                if f'No such image: {self._container_image}' in results.stderr:
                    last_tag_timestamp = 0
                else:
                    last_tag_timestamp = parser.parse(results.stdout.rpartition(' ')[0]).timestamp()
                # Get last modification time of the container file
                last_file_mod_timestamp = self._container_file.stat().st_mtime
                # Build image, if necessary
                if last_tag_timestamp < last_file_mod_timestamp:
                    pretty_print.print_build(f'Building docker image {self._container_image}...')
                    Builder._run_sh_command(['docker', 'build', '-t', self._container_image, '-f', str(self._container_file), '--build-arg', f'user_name={self._host_user}', '--build-arg', f'user_id={str(self._host_user_id)}', '.'])
                else:
                    pretty_print.print_build(f'No need to build the docker image {self._container_image}...')

            elif self._container_tool == 'podman':
                # Get last build event time from podman
                results = Builder._get_sh_results(['podman', 'image', 'inspect', '-f', '\'{{ .Id }}\'', self._container_image, '|', 'xargs', '-I', '{}', 'podman', 'events', '--filter', 'image={}', '--filter', 'event=build', '--format', '\'{{.Time}}\'', '--until', '0m'])
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
                    Builder._run_sh_command(['podman', 'build', '-t', self._container_image, '-f', str(self._container_file), '.'])
                else:
                    pretty_print.print_build(f'No need to build the podman image {self._container_image}...')

            elif self._container_tool == 'none':
                pretty_print.print_warning('Container image is not built in native mode.')
            else:
                Builder._err_unsup_container_tool()
        except Exception as e:
                pretty_print.print_error(f'An error occurred while building the container image: {str(e)}')
                sys.exit(1)


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
        if not self._source_repo_dir.exists():
            pretty_print.print_build('Initializing local repo...')
            try:
                self._output_dir.mkdir(parents=True, exist_ok=True)
                self._repo_dir.mkdir(parents=True, exist_ok=True)

                # Clone the repo
                Builder._run_sh_command(['git', 'clone', '--recursive', '--branch', self._source_repo_branch, self._source_repo_url, str(self._source_repo_dir)])
                # Create new branch self._git_local_ref_branch. This branch is used as a reference where all existing patches are applied to the git sources
                Builder._run_sh_command(['git', '-C', str(self._source_repo_dir), 'switch', '-c', self._git_local_ref_branch])
                # Create new branch self._git_local_dev_branch. This branch is used as the local development branch. New patches can be created from this branch.
                Builder._run_sh_command(['git', '-C', str(self._source_repo_dir), 'switch', '-c', self._git_local_dev_branch])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while initializing the repository: {str(e)}')
                sys.exit(1)
        else:
            pretty_print.print_build('No need to initialize the local repo...')


    def create_patches(self):
        """
        Created patches from from commits on self._git_local_dev_branch.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Only create patches if there are commits on branch self._git_local_dev_branch that are not on branch self._git_local_dev_branch.
        result_new_commits = Builder._get_sh_results(['git', '-C', str(self._source_repo_dir), 'log', '--cherry-pick', '--oneline', self._git_local_dev_branch, f'^{self._git_local_ref_branch}'])
        if result_new_commits.stdout:
            pretty_print.print_build('Creating patches...')
            try:
                # Create patches
                result_new_patches = Builder._get_sh_results(['git', '-C', str(self._source_repo_dir), 'format-patch', '--output-directory', str(self._patch_dir), self._git_local_ref_branch])
                # Add newly created patched to self._patch_list_file
                for line in result_new_patches.stdout.splitlines():
                    new_patch = line.rpartition('/')[2]
                    print(f'Patch {new_patch} was created')
                    with self._patch_list_file.open('a') as f:
                        print(new_patch, file=f, end='\n')
                # Synchronize the branches ref and dev to be able to detect new commits in the future
                Builder._run_sh_command(['git', '-C', str(self._source_repo_dir), 'checkout', self._git_local_ref_branch])
                Builder._run_sh_command(['git', '-C', str(self._source_repo_dir), 'merge', self._git_local_dev_branch])
                Builder._run_sh_command(['git', '-C', str(self._source_repo_dir), 'checkout', self._git_local_dev_branch])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while creating new patches: {str(e)}')
                sys.exit(1)
        else:
            pretty_print.print_warning('No commits found that can be used as sources for patches.')


    def apply_patches(self):
        """
        This function iterates over all patches listed in self._patch_list_file and
        applies them to the repo.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Skip all operations if the patches have already been applied
        if not self._patches_applied_flag.exists():
            pretty_print.print_build('Applying patches...')
            try:
                if self._patch_list_file.is_file():
                    with self._patch_list_file.open('r') as f:
                        for patch in f:
                            if patch:
                                # Apply patch
                                Builder._run_sh_command(['git', '-C', str(self._source_repo_dir), 'am', str(self._patch_dir / patch)])
                
                # Update the branch self._git_local_ref_branch so that it contains the applied patches and is in sync with self._git_local_dev_branch. This is important to be able to create new patches.
                Builder._run_sh_command(['git', '-C', str(self._source_repo_dir), 'checkout', self._git_local_ref_branch])
                Builder._run_sh_command(['git', '-C', str(self._source_repo_dir), 'merge', self._git_local_dev_branch])
                Builder._run_sh_command(['git', '-C', str(self._source_repo_dir), 'checkout', self._git_local_dev_branch])
                # Create the flag if it doesn't exist and update the timestamps
                self._patches_applied_flag.touch()
            except Exception as e:
                pretty_print.print_error(f'An error occurred while applying patches: {str(e)}')
                sys.exit(1)
        else:
            pretty_print.print_build('No need to apply patches...')
    

    def download_pre_built(self):
        """
        Download pre-built files instead of building them locally.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        # Progress callback function to show a status bar
        def download_progress(block_num, block_size, total_size):
            if download_progress.t is None:
                download_progress.t = tqdm.tqdm(total=total_size, unit='B', unit_scale=True, unit_divisor=1024)
            downloaded = block_num * block_size
            download_progress.t.update(downloaded - download_progress.t.n)

        # Get URL
        if 'pre-built' not in self._project_cfg['blocks'][self._block_name]['project']:
            pretty_print.print_error(f'The property blocks/{self._block_name}/project/pre-built is not provided')
            sys.exit(1)

        download_url = self._project_cfg['blocks'][self._block_name]['project']['pre-built']

        if not validators.url(download_url):
            pretty_print.print_error(f'The value of blocks/{self._block_name}/project/pre-built is not a valid URL: {download_url}')
            sys.exit(1)

        # Send a HEAD request to get the HTTP headers
        response = requests.head(download_url, allow_redirects=True)

        if response.status_code == 404:
            # File not found
            pretty_print.print_error(f'The following file could not be downloaded: {download_url}\nStatus code {response.status_code} (File not found)')
            sys.exit(1)
        elif response.status_code != 200:
            # Unexpected status code
            pretty_print.print_error(f'The following file could not be downloaded: {download_url}\nUnexpected status code {response.status_code}')
            sys.exit(1)

        #Check if the file needs to be downloaded
        last_modified = response.headers.get('Last-Modified')
        if last_modified:
            last_modified_timestamp = parser.parse(last_modified).timestamp()
        else:
            pretty_print.print_error(f'No \'Last-Modified\' header found for {download_url}')
            sys.exit(1)

        last_file_mod_timestamp = 0
        if self._download_dir.is_dir():
            items = list(self._download_dir.iterdir())
            if len(items) == 1:
                last_file_mod_timestamp = items[0].stat().st_mtime
            else:
                pretty_print.print_error(f'There is more than one item in {str(self._download_dir)}\nPlease empty the directory')
                sys.exit(1)

        if last_file_mod_timestamp < last_modified_timestamp:
            pretty_print.print_build('Downloading archive with pre-built files...')

            Builder.clean_download(self=self)
            self._download_dir.mkdir(parents=True, exist_ok=True)

            # Download the file
            download_progress.t = None
            filename = download_url.rpartition('/')[2]
            urllib.request.urlretrieve(download_url, self._download_dir / filename, reporthook=download_progress)
            if download_progress.t:
                download_progress.t.close()

            Builder.clean_output(self=self)
            self._output_dir.mkdir(parents=True, exist_ok=True)

            #Extract pre-built files
            file_extension = filename.partition('.')[2]
            if file_extension in ['tar.gz', 'tgz', 'tar.xz', 'txz']:
                # tarfile doesn't support parallelised decompression. One would have to use shell
                # tools for that. For file system archives it might be worth it to save time.
                # This should also be done in a container.
                with tarfile.open(self._download_dir / filename, "r:*") as archive:
                    # Extract all contents to the output directory
                    archive.extractall(path=self._output_dir)
            else:
                pretty_print.print_error(f'The following archive type is not supported: {file_extension}')
                sys.exit(1)

        else:
            pretty_print.print_build('No need to download pre-built files...')


    def export_block_package(self):
        """
        Exports the block package that contains all output products of this block.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        block_pkg_path = self._output_dir / f'{self._block_name}.tar.gz'

        # Check whether there is something to export
        if not self._output_dir.is_dir() or not any(self._output_dir.iterdir()):
            pretty_print.print_error(f'Unable to export block package. The following director does not exist or is empty: {self._output_dir}')
            sys.exit(1)

        # Check whether a package needs to be created
        if not Builder._check_rebuilt_required(src_search_list=[self._output_dir], src_ignore_list=[block_pkg_path], out_search_list=[block_pkg_path]):
            pretty_print.print_build('No need to export block package. No altered source files detected...')
            return

        # Export block package
        pretty_print.print_build('Exporting block package...')

        block_pkg_path.unlink(missing_ok=True)
        with tarfile.open(block_pkg_path, "w:gz") as archive:
            for file in self._output_dir.iterdir():
                if not file.samefile(block_pkg_path):
                    archive.add(file, arcname=file.name)


    def import_dependencies(self):
        """
        Imports all dependencies needed to build this block.
        Dependencies are plock backages exported from other blocks.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        for block_name, block_pkg_src_path_str in self._project_cfg['blocks'][self._block_name]['project']['dependencies'].items():
            block_pkg_src_path = self._project_dir / block_pkg_src_path_str
            import_path = self._dependencies_dir / block_name

            # Check whether the file exists
            if not block_pkg_src_path.is_file():
                pretty_print.print_error(f'Unable to import block package. The following file does not exist: {block_pkg_src_path}')
                sys.exit(1)

            # Check whether the file is a tar.gz archive
            if block_pkg_src_path.name.partition('.')[2] != 'tar.gz':
                pretty_print.print_error(f'Unable to import block package. The following archive type is not supported: {block_pkg_src_path.name.partition(".")[2]}')
                sys.exit(1)

            # Check whether this dependencie needs to be imported
            if not Builder._check_rebuilt_required(src_search_list=[block_pkg_src_path], out_search_list=[import_path]):
                pretty_print.print_build('No need to import block package. No altered source files detected...')
                return

            # Import block package
            pretty_print.print_build('Importing block package...')

            import_path.mkdir(parents=True, exist_ok=True)
            shutil.copy(block_pkg_src_path, import_path / block_pkg_src_path.name)
            with tarfile.open(import_path / block_pkg_src_path.name, "r:*") as archive:
                    # Extract all contents to the output directory
                    archive.extractall(path=import_path)


    def start_container(self):
        """
        Starts an interactive container with which the block can be built.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        potential_mounts = [f'{str(self._repo_dir)}:Z', f'{str(self._work_dir)}:Z', f'{str(self._output_dir)}:Z']

        Builder._start_container(self, potential_mounts=potential_mounts)


    def _start_container(self, potential_mounts: typing.List[str]):
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

        if self._container_tool in ('docker', 'podman'):
            try:
                pretty_print.print_build('Starting container...')
                # Check which mounts (resp. directories) are available on the host system
                available_mounts = []
                for mount in potential_mounts:
                    segments = mount.split(':')
                    if len(segments) != 2:
                        pretty_print.print_error(f'The following path contains a forbidden colon: {mount.rpartition(":")[0]}')
                        sys.exit(1)
                    if pathlib.Path(segments[0]).is_dir():
                        available_mounts.append(f'{segments[0]}:{segments[0]}:{segments[1]}')
                # Start the container
                Builder._run_sh_command([self._container_tool, 'run', '--rm', '-it', '-v', ' -v '.join(available_mounts), self._container_image])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while executing the container: {str(e)}')
                sys.exit(1)

        elif self._container_tool == 'none':
            # This function is only supported if a container tool is used
            Builder._err_container_feature(f'{inspect.getframeinfo(inspect.currentframe()).function}()')
        else:
            Builder._err_unsup_container_tool()


    def _run_menuconfig(self, menuconfig_commands: str):
        """
        Opens the menuconfig tool to enable interactive configuration of the project.

        Args:
            menuconfig_commands:
                The commands to be executed in a container to configure U-Boot interactively.

        Returns:
            None

        Raises:
            None
        """

        if not self._source_repo_dir.is_dir():
            pretty_print.print_error(f'No local sources found in {self._source_repo_dir}')
            sys.exit(1)

        if self._container_tool in ('docker', 'podman'):
            try:
                # Open the menuconfig tool in the container
                Builder._run_sh_command([self._container_tool, 'run', '--rm', '-it', '-v', f'{str(self._repo_dir)}:{str(self._repo_dir)}:Z', '-v', f'{str(self._output_dir)}:{str(self._output_dir)}:Z', self._container_image, 'sh', '-c', menuconfig_commands])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while running the menuconfig tool: {str(e)}')
                sys.exit(1)

        elif self._container_tool == 'none':
            # Open the menuconfig tool without using a container
            Builder._run_sh_command(['sh', '-c', menuconfig_commands])
        else:
            Builder._err_unsup_container_tool()


    def _prep_clean_srcs(self, prep_srcs_commands: str):
        """
        This function is intended to create a new, clean Linux kernel or U-Boot project. After the creation of the project you should create a patch that includes .gitignore and .config.

        Args:
            menuconfig_commands:
                The commands to be executed in a container to prepare a clean project.

        Returns:
            None

        Raises:
            None
        """

        if not self._source_repo_dir.is_dir():
            pretty_print.print_error(f'No local sources found in {self._source_repo_dir}')
            sys.exit(1)

        if (self._source_repo_dir / '.config').is_file():
            pretty_print.print_error(f'Configuration file already exists in {self._source_repo_dir / ".config"}')
            sys.exit(1)

        if self._container_tool in ('docker', 'podman'):
            try:
                # Prepare clean sources in the container
                Builder._run_sh_command([self._container_tool, 'run', '--rm', '-it', '-v', f'{str(self._repo_dir)}:{str(self._repo_dir)}:Z', '-v', f'{str(self._output_dir)}:{str(self._output_dir)}:Z', self._container_image, 'sh', '-c', prep_srcs_commands])
            except Exception as e:
                pretty_print.print_error(f'An error occurred while preparing clean sources: {str(e)}')
                sys.exit(1)

        elif self._container_tool == 'none':
            # Prepare clean sources without using a container
            Builder._run_sh_command(['sh', '-c', prep_srcs_commands])
        else:
            Builder._err_unsup_container_tool()


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
                    pretty_print.print_build(f'Cleaning container image {self._container_image}...')
                    Builder._run_sh_command([self._container_tool, 'image', 'rm', self._container_image])
                else:
                    pretty_print.print_build(f'No need to clean container image {self._container_image}, the image doesn\'t exist...')
            except Exception as e:
                pretty_print.print_error(f'An error occurred while cleaning the container image: {str(e)}')
                sys.exit(1)

        elif self._container_tool == 'none':
            # This function is only supported if a container tool is used
            Builder._err_container_feature(f'{inspect.getframeinfo(inspect.currentframe()).function}()')
        else:
            Builder._err_unsup_container_tool()


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

        if self._repo_dir.exists():
            # Check if there are uncommited changes in the git repo
            results = Builder._get_sh_results(['git', '-C', str(self._source_repo_dir), 'status', '--porcelain'])
            if results.stdout:
                pretty_print.print_warning(f'There are uncommited changes in {str(self._source_repo_dir)}. Do you really want to clean this repo? (y/n) ', end='')
                answer = input('')
                if answer.lower() not in ['y', 'Y', 'yes', 'Yes']:
                    pretty_print.print_clean('Cleaning abborted...')
                    sys.exit(1)

            pretty_print.print_clean('Cleaning repo directory...')
            if self._container_tool in ('docker', 'podman'):
                try:
                    # Clean up the repo directory from the container
                    Builder._run_sh_command([self._container_tool, 'run', '--rm', '-it', '-v', f'{str(self._repo_dir)}:/app/repo:Z', self._container_image, 'sh', '-c', '\"rm -rf /app/repo/* /app/repo/.* 2> /dev/null || true\"'])
                except Exception as e:
                    pretty_print.print_error(f'An error occurred while cleaning the repo directory: {str(e)}')
                    sys.exit(1)

            elif self._container_tool == 'none':
                # Clean up the repo directory without using a container
                Builder._run_sh_command(['sh', '-c', f'\"rm -rf {str(self._repo_dir)}/* {str(self._repo_dir)}/.* 2> /dev/null || true\"'])
            else:
                Builder._err_unsup_container_tool()

            # Remove flag
            self._patches_applied_flag.unlink(missing_ok=True)

            # Remove empty repo directory
            self._repo_dir.rmdir()

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

        if self._output_dir.exists():
            pretty_print.print_clean('Cleaning output directory...')
            if self._container_tool in ('docker', 'podman'):
                try:
                    # Clean up the output directory from the container
                    Builder._run_sh_command([self._container_tool, 'run', '--rm', '-it', '-v', f'{str(self._output_dir)}:/app/output:Z', self._container_image, 'sh', '-c', '\"rm -rf /app/output/* /app/output/.* 2> /dev/null || true\"'])
                except Exception as e:
                    pretty_print.print_error(f'An error occurred while cleaning the output directory: {str(e)}')
                    sys.exit(1)

            elif self._container_tool == 'none':
                # Clean up the output directory without using a container
                Builder._run_sh_command(['sh', '-c', f'\"rm -rf {str(self._output_dir)}/* {str(self._output_dir)}/.* 2> /dev/null || true\"'])
            else:
                Builder._err_unsup_container_tool()

            # Remove empty output directory
            self._output_dir.rmdir()

        else:
            pretty_print.print_clean('No need to clean the output directory...')


    def clean_download(self):
        """
        This function cleans the download directory.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        if self._download_dir.exists():
            pretty_print.print_clean('Cleaning download directory...')
            if self._container_tool in ('docker', 'podman'):
                try:
                    # Clean up the download directory from the container
                    Builder._run_sh_command([self._container_tool, 'run', '--rm', '-it', '-v', f'{str(self._download_dir)}:/app/download:Z', self._container_image, 'sh', '-c', '\"rm -rf /app/download/* /app/download/.* 2> /dev/null || true\"'])
                except Exception as e:
                    pretty_print.print_error(f'An error occurred while cleaning the download directory: {str(e)}')
                    sys.exit(1)

            elif self._container_tool == 'none':
                # Clean up the download directory without using a container
                Builder._run_sh_command(['sh', '-c', f'\"rm -rf {str(self._download_dir)}/* {str(self._download_dir)}/.* 2> /dev/null || true\"'])
            else:
                Builder._err_unsup_container_tool()

            # Remove empty download directory
            self._download_dir.rmdir()

        else:
            pretty_print.print_clean('No need to clean the download directory...')


    def clean_dependencies(self):
        """
        This function cleans the dependencies directory.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        if self._dependencies_dir.exists():
            pretty_print.print_clean('Cleaning dependencies directory...')
            if self._container_tool in ('docker', 'podman'):
                try:
                    # Clean up the dependencies directory from the container
                    Builder._run_sh_command([self._container_tool, 'run', '--rm', '-it', '-v', f'{str(self._dependencies_dir)}:/app/dependencies:Z', self._container_image, 'sh', '-c', '\"rm -rf /app/dependencies/* /app/dependencies/.* 2> /dev/null || true\"'])
                except Exception as e:
                    pretty_print.print_error(f'An error occurred while cleaning the dependencies directory: {str(e)}')
                    sys.exit(1)

            elif self._container_tool == 'none':
                # Clean up the dependencies directory without using a container
                Builder._run_sh_command(['sh', '-c', f'\"rm -rf {str(self._dependencies_dir)}/* {str(self._dependencies_dir)}/.* 2> /dev/null || true\"'])
            else:
                Builder._err_unsup_container_tool()

            # Remove empty download directory
            self._dependencies_dir.rmdir()

        else:
            pretty_print.print_clean('No need to clean the dependencies directory...')