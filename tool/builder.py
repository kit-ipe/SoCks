import os
import sys
import subprocess
import select

import pretty_print

class Builder:
    """
    Base class for all builder classes
    """

    def __init__(self, block_name, project_dir):
        # Directories
        self._project_dir = project_dir
        self._patch_dir = self._project_dir+'/'+block_name+'/patches/'
        self._repo_dir = self._project_dir+'/temp/'+block_name+'/repo/'
        self._output_dir = self._project_dir+'/temp/'+block_name+'/output/'

        # Files
        # Flag to remember if patches have already been applied
        self._patches_applied_flag = self._project_dir+'/temp/'+block_name+'/.patchesapplied'
        # File containing all patches to be used
        self._patch_cfg_file = self._patch_dir+'/.patches.cfg'

        # Git branches
        self._git_local_ref_branch = '__ref'
        self._git_local_dev_branch = '__temp'


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
                is True.

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


    def init_repo(self):
        """
        Clone and initialize the git repo. All operations are skipped, if the repo
        already exists.
        """

        if(not os.path.isdir(self._source_repo_dir)):
            pretty_print.print_build('-> Fetching repo...')
            try:
                os.makedirs(self._output_dir, exist_ok=True)
                os.makedirs(self._repo_dir, exist_ok=True)

                Builder._run_sh_command(['git', 'clone', '--recursive', '--branch', self._source_repo_branch, self._source_repo_url, self._source_repo_dir])
                Builder._run_sh_command(['git', '-C', self._source_repo_dir, 'switch', '-c', self._git_local_ref_branch])
                Builder._run_sh_command(['git', '-C', self._source_repo_dir, 'switch', '-c', self._git_local_dev_branch])
            except Exception as e:
                pretty_print.print_error('An error occurred while initializing the repository: '+str(e))
                sys.exit(1)
        else:
            pretty_print.print_build('-> No need to fetch the repo...')


    def apply_patches(self):
        """
        This function iterates over all patches listed in self._patch_cfg_file and
        applies them to the repo. All operations are skipped, if the patches have
        already been applied.

        The git branch self._git_local_ref_branch is used as a reference with all
        existing patches applied.
        The git branch self._git_local_dev_branch is used as the local development
        branch. New patches can be created from this branch.
        """
        if(not os.path.isfile(self._patches_applied_flag)):
            pretty_print.print_build('-> Applying patches...')
            try:
                if os.path.isfile(self._patch_cfg_file):
                    with open(self._patch_cfg_file) as patches:
                        for patch in patches:
                            if patch:
                                Builder._run_sh_command(['git', '-C', self._source_repo_dir, 'am', self._patch_dir+'/'+patch])
                
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
            pretty_print.print_build('-> No need to apply patches...')