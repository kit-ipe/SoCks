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
        self.project_dir = project_dir
        self.patch_dir = self.project_dir+'/'+block_name+'/patches/'
        self.repo_dir = self.project_dir+'/temp/'+block_name+'/repo/'
        self.output_dir = self.project_dir+'/temp/'+block_name+'/output/'

        # Files
        # Flag to remember if patches have already been applied
        self.patches_applied_flag = self.project_dir+'/temp/'+block_name+'/.patchesapplied'
        # File containing all patches to be used
        self.patch_cfg_file = self.patch_dir+'/.patches.cfg'

        # Git branches
        self.git_local_ref_branch = '__ref'
        self.git_local_dev_branch = '__temp'

    #
    # ToDo: Most likely this function can be removed
    #
    @staticmethod
    def _run_sh_command_limited_output(command, logfile=None, visible=True, visible_lines=20):
        """ (Google documentation style: https://github.com/google/styleguide/blob/gh-pages/pyguide.md#38-comments-and-docstrings)
        Runs a sh command. This function does not work properly for commands that show
        a progress bar or someting similar.

        Args:
            command:
                The command to execute. Example: '/usr/bin/ping www.google.com'.
                The executable should be given with the full path, as mentioned
                here: https://docs.python.org/3/library/subprocess.html#subprocess.Popen
            logfile:
                Path of the logfile. None if no log file is to be used.
            visible:
                If True the output of the command will be printed.
            visible_lines:
                Maximum number of sh output lines to be printed. The output is updated
                at run time and the latest lines are always displayed.

        Returns:
            None

        Raises:
            None
        """

        # Prepare to handle the command line output of the command
        printed_lines = 0
        last_lines = []

        def update_last_lines(line):
            if len(last_lines) >= visible_lines:
                last_lines.pop(0)
            last_lines.append(line)
        
        # Start the subprocess
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

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
            pretty_print.print_error('Error: The following sh command failed: \''+' '.join(command)+'\'')
            sys.exit(1)


    @staticmethod
    def _run_sh_command(command, logfile=None):
        """ (Google documentation style: https://github.com/google/styleguide/blob/gh-pages/pyguide.md#38-comments-and-docstrings)
        Runs a sh command. If a logfile is used this function does not work properly
        for commands that show a progress bar or someting similar.

        Args:
            command:
                The command to execute. Example: '/usr/bin/ping www.google.com'.
                The executable should be given with the full path, as mentioned
                here: https://docs.python.org/3/library/subprocess.html#subprocess.Popen
            logfile:
                Path of the logfile. None if no log file is to be used.

        Returns:
            None

        Raises:
            None
        """

        if logfile:
            subprocess.run(' '.join(command+['2>&1', '|', 'tee', '--append', logfile]), shell=True, check=True)
        else:
            subprocess.run(' '.join(command), shell=True, check=True)


    def init_repo(self):
        """
        Clone and initialize the git repo. All operations are skipped, if the repo
        already exists.
        """

        if(not os.path.isdir(self.source_repo_dir)):
            pretty_print.print_build('-> Fetching repo...')
            try:
                os.makedirs(self.output_dir, exist_ok=True)
                os.makedirs(self.repo_dir, exist_ok=True)

                Builder._run_sh_command(['git', 'clone', '--recursive', '--branch', self.source_repo_branch, self.source_repo_url, self.source_repo_dir])
                Builder._run_sh_command(['git', '-C', self.source_repo_dir, 'switch', '-c', self.git_local_ref_branch])
                Builder._run_sh_command(['git', '-C', self.source_repo_dir, 'switch', '-c', self.git_local_dev_branch])
            except Exception as e:
                pretty_print.print_error('An error occurred while initializing the repository: '+str(e))
                sys.exit(1)
        else:
            pretty_print.print_build('-> No need to fetch the repo...')


    def apply_patches(self):
        """
        This function iterates over all patches listed in self.patch_cfg_file and
        applies them to the repo. All operations are skipped, if the patches have
        already been applied.

        The git branch self.git_local_ref_branch is used as a reference with all
        existing patches applied.
        The git branch self.git_local_dev_branch is used as the local development
        branch. New patches can be created from this branch.
        """
        if(not os.path.isfile(self.patches_applied_flag)):
            pretty_print.print_build('-> Applying patches...')
            try:
                if os.path.isfile(self.patch_cfg_file):
                    with open(self.patch_cfg_file) as patches:
                        for patch in patches:
                            if patch:
                                Builder._run_sh_command(['git', '-C', self.source_repo_dir, 'am', self.patch_dir+'/'+patch])
                
                Builder._run_sh_command(['git', '-C', self.source_repo_dir, 'checkout', self.git_local_ref_branch])
                Builder._run_sh_command(['git', '-C', self.source_repo_dir, 'merge', self.git_local_dev_branch])
                Builder._run_sh_command(['git', '-C', self.source_repo_dir, 'checkout', self.git_local_dev_branch])
                # Create the flasg if it doesn't exist and update the timestamps
                with open(self.patches_applied_flag, 'w'):
                    os.utime(self.patches_applied_flag, None)
            except Exception as e:
                pretty_print.print_error('An error occurred while applying patches: '+str(e))
                sys.exit(1)
        else:
            pretty_print.print_build('-> No need to apply patches...')