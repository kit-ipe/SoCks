import typing
import pathlib
import shutil
import sys
import re
import select
import subprocess

import socks.pretty_print as pretty_print


class Shell_Command_Runners:
    """
    A collection of functions to execute shell commands
    """

    @staticmethod
    def run_sh_command(
        command: typing.List[str],
        cwd: pathlib.Path = None,
        logfile: pathlib.Path = None,
        scrolling_output: bool = False,
        visible_lines: int = 30,
    ):
        """(Google documentation style:
            https://github.com/google/styleguide/blob/gh-pages/pyguide.md#38-comments-and-docstrings)
        Runs a sh command. If the srolling view is enabled or the output is to be logged, this function loses some
        output of commands that display a progress bar or someting similar. The 'tee' shell command has the same issue.

        Args:
            command:
                The command to execute as a list of strings. Example: ['/usr/bin/ping', 'www.google.com'].
                The executable should be given with the full path, as mentioned
                here: https://docs.python.org/3/library/subprocess.html#subprocess.Popen
            cwd:
                If cwd is not None, the working directory is changed to cwd before the commands are executed.
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
            subprocess.CalledProcessError: If the return code of the subprocess is not 0
        """

        # If scolling output is disabled and the output should not be hidden or logged, subprocess.run can be used
        # to run the subprocess
        if scrolling_output == False and visible_lines != 0 and logfile == None:
            subprocess.run(" ".join(command), shell=True, cwd=cwd, check=True)
            return

        # Remove old logfile
        if logfile != None:
            logfile.unlink(missing_ok=True)

        # Regex to strip ANSI escape sequences from strings
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

        # Prepare to process the command line output of the command
        printed_lines = 0
        last_lines = []

        def update_last_lines(line):
            if visible_lines <= 0:
                return
            if len(last_lines) >= visible_lines:
                last_lines.pop(0)
            last_lines.append(line)

        # Tell the user where the complete output is logged
        if logfile:
            print(
                "The output of this process is displayed in a scrolling view. "
                f"You can find the full output here: {logfile}"
            )

        # Start the subprocess
        process = subprocess.Popen(
            " ".join(command), shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

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
                # Strip all invisible elements from the end of the string (especially new line characters, etc.)
                stdout_line = stdout_line.rstrip()

            stderr_line = None
            if process.stderr in readable:
                stderr_line = process.stderr.readline()

            # If both are empty and the process is done, break
            if not stdout_line and not stderr_line and process.poll() is not None:
                break

            # If provided, write to log file
            if logfile:
                with logfile.open("a") as f:
                    if stdout_line:
                        # Strip ANSI escape sequences as they cannot be printed to a file
                        stdout_line = ansi_escape.sub("", stdout_line)
                        print(stdout_line, file=f)
                    if stderr_line:
                        # Strip ANSI escape sequences as they cannot be printed to a file
                        stderr_line = ansi_escape.sub("", stderr_line)
                        print(stderr_line, file=f)

            # Show output of the command
            if stdout_line:
                update_last_lines(stdout_line)
            if stderr_line:
                update_last_lines(stderr_line)

            # Clear previous output
            for _ in range(printed_lines):
                # Move the cursor up one line
                print("\033[F", end="", flush=True)
                # Clear the line
                print("\033[K", end="", flush=True)

            # Print output
            printed_lines = 0
            terminal_width = shutil.get_terminal_size().columns
            for line in last_lines:
                if len(line) > terminal_width:
                    # Replace tabs with spaces to get a realistic line length
                    line = line.expandtabs()
                    # Limit the line length to avoid wrapping
                    line = line[: (terminal_width - 3)] + "..."
                print(line, end="\r\n", flush=True)
                printed_lines += 1

        # Close the streams
        process.stdout.close()
        process.stderr.close()
        process.wait()

        # Check return code
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, " ".join(command))

    @staticmethod
    def get_sh_results(command: typing.List[str], cwd: pathlib.Path = None) -> subprocess.CompletedProcess:
        """(Google documentation style:
            https://github.com/google/styleguide/blob/gh-pages/pyguide.md#38-comments-and-docstrings)
        Runs a sh command and get all output.

        Args:
            command:
                The command to execute as a list of strings. Example: ['/usr/bin/ping', 'www.google.com'].
                The executable should be given with the full path, as mentioned here:
                https://docs.python.org/3/library/subprocess.html#subprocess.Popen
            cwd:
                If cwd is not None, the working directory is changed to cwd before the commands are executed.

        Returns:
            An object that contains stdout (str), stderr (str) and returncode (int).

        Raises:
            None
        """

        result = subprocess.run(" ".join(command), shell=True, cwd=cwd, capture_output=True, text=True, check=False)

        return result
