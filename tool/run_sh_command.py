import subprocess
import select

import pretty_print

def run_sh_command(command, logfile=None, visible=False, visible_lines=10):
    """ (Google documentation style: https://github.com/google/styleguide/blob/gh-pages/pyguide.md#38-comments-and-docstrings)
    Runs a sh command

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
                pretty_print.print_bash_output(line, end='', flush=True)
                printed_lines += 1

    # Close the streams
    process.stdout.close()
    process.stderr.close()
    process.wait()
