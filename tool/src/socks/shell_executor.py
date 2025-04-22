import pathlib
import shutil
import sys
import re
import select
import subprocess
import os

import socks.pretty_print as pretty_print


class Shell_Executor:
    """
    A collection of functions to execute shell commands
    """

    def __init__(
        self,
        prohibit_output_processing: bool = False,
    ):
        # Prohibit output scrolling. This setting overwrites all other output scrolling settings.
        self._prohibit_output_processing = prohibit_output_processing

    @staticmethod
    def get_sh_results(command: list[str], cwd: pathlib.Path = None, check: bool = True) -> subprocess.CompletedProcess:
        """(Google documentation style:
            https://github.com/google/styleguide/blob/gh-pages/pyguide.md#38-comments-and-docstrings)
        Runs a shell command and returns all output.

        Args:
            command:
                The command to execute as a list of strings. Example: ['/usr/bin/ping', 'www.google.com'].
                The executable should be given with the full path, as mentioned here:
                https://docs.python.org/3/library/subprocess.html#subprocess.Popen
            cwd:
                If cwd is not None, the working directory is changed to cwd before the commands are executed.
            check:
                If set to True, the exit code of the process is checked.

        Returns:
            An object that contains stdout (str), stderr (str) and returncode (int).

        Raises:
            None
        """

        try:
            result = subprocess.run(" ".join(command), shell=True, cwd=cwd, capture_output=True, text=True, check=check)
        except subprocess.CalledProcessError as e:
            if e.stdout:
                print(f"\n{e.stdout}")
            if e.stderr:
                print(f"\n{e.stderr}")
            pretty_print.print_error(
                "The return code of a sub-process was not equal to zero (see output above).\n"
                f"return code: {e.returncode}\n"
                f"shell command: {e.cmd}"
            )
            sys.exit(1)

        return result

    def exec_sh_command(
        self,
        command: list[str],
        cwd: pathlib.Path = None,
        check: bool = True,
        logfile: pathlib.Path = None,
        output_scrolling: bool = False,
        visible_lines: int = 30,
    ):
        """(Google documentation style:
            https://github.com/google/styleguide/blob/gh-pages/pyguide.md#38-comments-and-docstrings)
        Executes a shell command. If the srolling view is enabled or the output is to be logged, this function loses
        some output of commands that display a progress bar or someting similar. The 'tee' shell command has the
        same issue.

        Args:
            command:
                The command to execute as a list of strings. Example: ['/usr/bin/ping', 'www.google.com'].
                The executable should be given with the full path, as mentioned
                here: https://docs.python.org/3/library/subprocess.html#subprocess.Popen
            cwd:
                If cwd is not None, the working directory is changed to cwd before the commands are executed.
            check:
                If set to True, the exit code of the process is checked.
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
            subprocess.CalledProcessError: If the return code of the subprocess is not 0
        """

        # If scolling output is disabled and the output should not be hidden or logged, subprocess.run can be used
        # to run the subprocess
        if self._prohibit_output_processing or (output_scrolling == False and visible_lines != 0 and logfile == None):
            try:
                subprocess.run(" ".join(command), shell=True, cwd=cwd, check=check, env=os.environ.copy())
            except subprocess.CalledProcessError as e:
                if e.stdout:
                    print(f"\n{e.stdout}")
                if e.stderr:
                    print(f"\n{e.stderr}")
                pretty_print.print_error(
                    "The return code of a sub-process was not equal to zero (see output above).\n"
                    f"return code: {e.returncode}\n"
                    f"shell command: {e.cmd}"
                )
                sys.exit(1)
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
            pretty_print.print_info(f"The complete output of this process is logged here: {logfile}\n")

        # Start the subprocess
        process = subprocess.Popen(
            " ".join(command),
            shell=True,
            cwd=cwd,
            env=os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
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
                # Strip all invisible elements from the end of the string (especially new line characters, etc.)
                stderr_line = stderr_line.rstrip()

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

            if output_scrolling:
                # Add output of the command to buffer
                if stdout_line:
                    update_last_lines(stdout_line)
                if stderr_line:
                    update_last_lines(stderr_line)

                # Move the cursor to the beginning of the scrolling output
                for _ in range(printed_lines):
                    # Move the cursor up one line
                    sys.stdout.write("\033[F")
                sys.stdout.flush()

                # Print output
                printed_lines = 0
                terminal_width = shutil.get_terminal_size().columns
                for line in last_lines:
                    if len(line) > terminal_width:
                        # Replace tabs with spaces to get a realistic line length
                        line = line.expandtabs()
                        # Limit the line length to avoid wrapping
                        line = line[: (terminal_width - 3)] + "..."
                    # Replace content of this line. The line is cleared before anything new is printed.
                    sys.stdout.write("\033[K" + line + "\r\n")
                    printed_lines += 1
                sys.stdout.flush()
            else:
                # Print output
                if stdout_line:
                    sys.stdout.write(stdout_line + "\r\n")
                if stderr_line:
                    sys.stdout.write(stderr_line + "\r\n")
                sys.stdout.flush()

        # Close the streams
        process.stdout.close()
        process.stderr.close()
        process.wait()

        # Check return code
        if check and process.returncode != 0:
            pretty_print.print_error(
                "The return code of a sub-process was not equal to zero (see output above).\n"
                f"return code: {process.returncode}\n"
                f"shell command: {' '.join(command)}"
            )
            sys.exit(1)

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

        self._prohibit_output_processing = state
