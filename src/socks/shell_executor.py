import pathlib
import shutil
import sys
import re
import subprocess
import os
import errno
import fcntl
import pty
import struct
import termios
import pyte

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
            result = subprocess.run(
                " ".join(command), shell=True, executable="sh", cwd=cwd, capture_output=True, text=True, check=check
            )
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
            None
        """

        # If scrolling output is disabled and the output should not be hidden or logged, subprocess.run can be used
        # to run the subprocess
        if self._prohibit_output_processing or (output_scrolling == False and visible_lines != 0 and logfile == None):
            try:
                subprocess.run(
                    " ".join(command), shell=True, executable="sh", cwd=cwd, check=check, env=os.environ.copy()
                )
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
        if logfile is not None:
            logfile.unlink(missing_ok=True)

        terminal_size = shutil.get_terminal_size()

        # Adapt the number of visible lines to the size of the terminal, if necessary
        visible_lines = min(visible_lines, terminal_size.lines - 2)

        # Prepare to process the command line output of the command using a terminal emulator
        screen = pyte.Screen(terminal_size.columns, terminal_size.lines)
        stream = pyte.ByteStream(screen)
        printed_lines = 0

        # Regexes for removing control sequences
        ansi_escape_re = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        ascii_control_re = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")

        def append_to_log(text: str):
            """Append cleaned subprocess output to the logfile"""

            if not logfile or not text:
                return

            # Remove control sequences
            cleaned = ansi_escape_re.sub("", text)
            cleaned = ascii_control_re.sub("", cleaned)
            # Normalize line endings (convert Windows style to Unix style to avoid unintended blank lines)
            cleaned = cleaned.replace("\r\n", "\n")

            with logfile.open("a") as f:
                f.write(cleaned)

        def get_visible_lines() -> list[str]:
            """Return the tail of the emulated screen to be shown in the scrolling view"""

            if visible_lines <= 0:
                return []

            all_lines = [row.rstrip() for row in screen.display]
            while len(all_lines) > 1 and all_lines[-1] == "":
                all_lines.pop()

            return all_lines[-visible_lines:]

        def print_scrolling_output():
            """Repaint only the currently visible tail of the virtual screen in the terminal"""

            nonlocal printed_lines

            # Move the cursor up to the top of the previously drawn block
            if printed_lines > 0:
                sys.stdout.write(f"\033[{printed_lines}F")

            visible_output_lines = get_visible_lines()
            num_lines_to_draw = min(visible_lines, max(printed_lines, len(visible_output_lines)))

            for idx in range(num_lines_to_draw):
                if idx < len(visible_output_lines):
                    line = visible_output_lines[idx]
                    if len(line.expandtabs()) > terminal_size.columns:
                        line = line.expandtabs()
                        line = line[: (terminal_size.columns - 3)] + "..."
                    # Print line and erase leftover content from previous renders
                    sys.stdout.write("\033[K" + line + "\r\n")
                else:
                    # Erase leftover content from previous renders
                    sys.stdout.write("\033[K\r\n")

            printed_lines = num_lines_to_draw
            sys.stdout.flush()

        # Tell the user where the complete output is logged
        if logfile:
            pretty_print.print_info(f"The complete output of this process is logged here: {logfile}")

        # Open and initialize a pseudo-terminal
        master_fd, slave_fd = pty.openpty()
        fcntl.ioctl(
            slave_fd,
            termios.TIOCSWINSZ,
            struct.pack("HHHH", terminal_size.lines, terminal_size.columns, 0, 0),
        )

        # Start the subprocess on the pseudo-terminal.
        process = subprocess.Popen(
            " ".join(command),
            shell=True,
            executable="sh",
            cwd=cwd,
            env=os.environ.copy(),
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            text=False,
        )
        os.close(slave_fd)

        try:
            # Continuously read from the process output
            while True:
                try:
                    chunk = os.read(master_fd, 4096)
                except OSError as e:
                    # Break loop if the subprocess has terminated (Input/Output error is expected when the child process has terminated)
                    if e.errno == errno.EIO and process.poll() is not None:
                        break
                    raise

                if chunk == b"":
                    # If no output was received, check whether the subprocess has terminated, and break the loop if that is the case
                    if process.poll() is not None:
                        break
                    continue

                # Feed raw bytes into the terminal emulator
                stream.feed(chunk)

                # Decode for logging
                decoded_output = chunk.decode("utf-8", errors="replace")
                append_to_log(decoded_output)

                if output_scrolling:
                    print_scrolling_output()
                else:
                    sys.stdout.write(decoded_output)
                    sys.stdout.flush()

            # Finish output handling
            if output_scrolling:
                print_scrolling_output()
                if printed_lines > 0:
                    sys.stdout.write("\033[K")
                    sys.stdout.flush()

        except KeyboardInterrupt:
            # On user interrupt, forcefully terminate the process
            try:
                process.kill()
                process.wait()
            except ProcessLookupError:
                # Process already exited
                pass

            print("")  # Push the error message to a new line
            pretty_print.print_error("The sub-process was interrupted by the user (Ctrl+C).\n")
            sys.exit(1)

        # Close the pseudo terminal
        os.close(master_fd)

        # Check return code
        process.wait()
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
