import pathlib
import shutil
import sys
import re
import subprocess
import os
import codecs
import errno
import fcntl
import pty
import struct
import termios

import socks.pretty_print as pretty_print


class _Terminal_Screen_Buffer:
    """
    A lightweight terminal screen model for managing subprocess output scrolling.
    """

    def __init__(self, visible_lines: int):
        self._visible_lines = visible_lines
        self._max_buffer_lines = max(visible_lines + 20, 100)
        self._lines = [""]
        self._cursor_row = 0
        self._cursor_col = 0
        self._parser_state = "text"
        self._csi_buffer = ""
        self._completed_lines = []

    def feed(self, text: str):
        """
        Adds new text to the buffer. Control sequences are detected and applied to the buffer.

        Args:
            text:
                 Terminal output from a subprocess that is to be added to the buffer.

        Returns:
            None

        Raises:
            None
        """

        # Parse incoming characters and apply their terminal control effects to the virtual buffer.
        for char in text:
            if self._parser_state == "text":
                if char == "\x1b":
                    self._parser_state = "escape"
                elif char == "\n":
                    self._newline()
                elif char == "\r":
                    self._cursor_col = 0
                elif char == "\b":
                    self._cursor_col = max(0, self._cursor_col - 1)
                elif char == "\t":
                    tab_width = 8 - (self._cursor_col % 8)
                    self._write_text(" " * tab_width)
                elif char >= " " and char != "\x7f":
                    self._write_text(char)
            elif self._parser_state == "escape":
                if char == "[":
                    self._parser_state = "csi"
                    self._csi_buffer = ""
                elif char == "]":
                    self._parser_state = "osc"
                else:
                    self._parser_state = "text"
            elif self._parser_state == "csi":
                self._csi_buffer += char
                if "@" <= char <= "~":
                    self._apply_csi(self._csi_buffer)
                    self._csi_buffer = ""
                    self._parser_state = "text"
            elif self._parser_state == "osc":
                if char == "\x07":
                    self._parser_state = "text"

    def collect_completed_lines(self) -> list[str]:
        """
        Hands completed lines to the caller and clears the internal queue afterwards. This function is to be used
        to write the logfile.

        Args:
            None

        Returns:
            Completed lines that have not yet been collected.

        Raises:
            None
        """

        completed_lines = self._completed_lines
        self._completed_lines = []
        return completed_lines

    def flush_current_line(self) -> list[str]:
        """
        Hands the current in-progress (unterminated) line. This function is to be used to write the logfile.

        Args:
            None

        Returns:
            Current in-progress line.

        Raises:
            None
        """

        self._ensure_cursor_row()
        if self._lines[self._cursor_row]:
            return [self._lines[self._cursor_row]]
        return []

    def get_visible_lines(self) -> list[str]:
        """
        Returns the tail of the virtual screen that should be shown in the scrolling view.

        Args:
            None

        Returns:
            Lines to be displayed in the scrolling view.

        Raises:
            None
        """

        if self._visible_lines <= 0:
            return []

        visible_lines = self._lines
        if len(visible_lines) > 1 and visible_lines[-1] == "":
            visible_lines = visible_lines[:-1]

        return visible_lines[-self._visible_lines :]

    def _apply_csi(self, sequence: str):
        """
        Applies an ANSI CSI control sequence such as cursor movement or line clearing to the buffer.

        Args:
            sequence:
                ANSI CSI control sequence.

        Returns:
            None

        Raises:
            None
        """

        final = sequence[-1]
        params = sequence[:-1]
        params = params.lstrip("?")

        def first_param(default: int) -> int:
            if params == "":
                return default
            try:
                return int(params.split(";")[0])
            except ValueError:
                return default

        self._ensure_cursor_row()

        if final == "A":
            self._cursor_row = max(0, self._cursor_row - first_param(1))
        elif final == "B":
            self._cursor_row += first_param(1)
            self._ensure_cursor_row()
            self._trim_buffer()
        elif final == "C":
            self._cursor_col += first_param(1)
        elif final == "D":
            self._cursor_col = max(0, self._cursor_col - first_param(1))
        elif final == "E":
            self._cursor_row += first_param(1)
            self._cursor_col = 0
            self._ensure_cursor_row()
            self._trim_buffer()
        elif final == "F":
            self._cursor_row = max(0, self._cursor_row - first_param(1))
            self._cursor_col = 0
        elif final == "G":
            self._cursor_col = max(0, first_param(1) - 1)
        elif final == "K":
            mode = first_param(0)
            line = self._lines[self._cursor_row]
            if mode == 0:
                self._lines[self._cursor_row] = line[: self._cursor_col]
            elif mode == 1:
                self._lines[self._cursor_row] = line[self._cursor_col :]
                self._cursor_col = 0
            elif mode == 2:
                self._lines[self._cursor_row] = ""
                self._cursor_col = 0
        elif final == "J":
            mode = first_param(0)
            if mode == 2:
                self._lines = [""]
                self._cursor_row = 0
                self._cursor_col = 0
        elif final == "m":
            # Select Graphic Rendition (colors, bold, ...); ignored for the scrolling view.
            return

        self._cursor_col = max(0, self._cursor_col)

    def _ensure_cursor_row(self):
        """
        Expands the line list until the current cursor row exists.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        while self._cursor_row >= len(self._lines):
            self._lines.append("")

    def _trim_buffer(self):
        """
        Drops the oldest lines once the internal scrollback grows beyond the configured limit.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        while len(self._lines) > self._max_buffer_lines and self._cursor_row > 0:
            self._lines.pop(0)
            self._cursor_row -= 1

    def _write_text(self, text: str):
        """
        Writes printable text at the current cursor position, replacing overwritten characters.

        Args:
            text:
                Text to be written.

        Returns:
            None

        Raises:
            None
        """

        self._ensure_cursor_row()
        line = self._lines[self._cursor_row]

        if self._cursor_col > len(line):
            line += " " * (self._cursor_col - len(line))

        prefix = line[: self._cursor_col]
        suffix_start = self._cursor_col + len(text)
        suffix = line[suffix_start:] if suffix_start < len(line) else ""
        self._lines[self._cursor_row] = prefix + text + suffix
        self._cursor_col += len(text)

    def _newline(self):
        """
        Finalizes the current line and moves the virtual cursor to the next line.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        self._ensure_cursor_row()
        self._completed_lines.append(self._lines[self._cursor_row])

        self._cursor_row += 1
        self._cursor_col = 0
        self._ensure_cursor_row()
        self._trim_buffer()


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
            subprocess.CalledProcessError: If the return code of the subprocess is not 0
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
        if logfile != None:
            logfile.unlink(missing_ok=True)

        terminal_size = shutil.get_terminal_size()

        # Adapt the number of visible lines to the size of the terminal, if necessary
        visible_lines = min(visible_lines, terminal_size.lines - 2)

        # Prepare to process the command line output of the command
        printed_lines = 0
        terminal_buffer = _Terminal_Screen_Buffer(visible_lines=visible_lines)

        def append_to_log(lines: list[str]):
            # Persist finalized logical lines to the logfile without ANSI escape sequences.
            if not logfile or not lines:
                return

            # Regex to strip ANSI escape sequences from strings
            ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

            with logfile.open("a") as f:
                for line in lines:
                    print(ansi_escape.sub("", line), file=f)

        def print_scrolling_output():
            # Repaint only the currently visible tail of the virtual screen in the terminal.
            nonlocal printed_lines

            # Move the cursor up
            sys.stdout.write(f"\033[{printed_lines}F")

            visible_output_lines = terminal_buffer.get_visible_lines()
            lines_to_draw = max(printed_lines, len(visible_output_lines))

            for idx in range(lines_to_draw):
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

            printed_lines = len(visible_output_lines)
            sys.stdout.flush()

        # Tell the user where the complete output is logged
        if logfile:
            pretty_print.print_info(f"The complete output of this process is logged here: {logfile}\n")

        # Open and initialize a pseudo-terminal
        master_fd, slave_fd = pty.openpty()
        fcntl.ioctl(
            slave_fd,
            termios.TIOCSWINSZ,
            struct.pack("HHHH", terminal_size.lines, terminal_size.columns, 0, 0),
        )

        # Start the subprocess on the pseudo terminal.
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

        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

        # Continuously read from the process output
        while True:
            try:
                chunk = os.read(master_fd, 4096)
            except KeyboardInterrupt:
                # Gracefully handle Ctrl+C
                process.kill()
                continue
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

            decoded_output = decoder.decode(chunk)
            if decoded_output == "":
                continue

            terminal_buffer.feed(decoded_output)
            append_to_log(terminal_buffer.collect_completed_lines())

            if output_scrolling:
                print_scrolling_output()
            else:
                sys.stdout.write(decoded_output)
                sys.stdout.flush()

        # Finish output handling
        flushed_output = decoder.decode(b"", final=True)
        if flushed_output:
            terminal_buffer.feed(flushed_output)
            append_to_log(terminal_buffer.collect_completed_lines())

            if output_scrolling:
                print_scrolling_output()
            else:
                sys.stdout.write(flushed_output)
                sys.stdout.flush()

        if output_scrolling:
            print_scrolling_output()
            if printed_lines > 0:
                sys.stdout.write("\033[K")
                sys.stdout.flush()

        append_to_log(terminal_buffer.flush_current_line())

        # Close the pseudo terminal
        os.close(master_fd)
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
