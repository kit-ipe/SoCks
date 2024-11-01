_magenta = "\033[95m"
_blue = "\033[94m"
_cyan = "\033[96m"
_green = "\033[92m"
_orange = "\033[93m"
_red = "\033[91m"
_end = "\033[0m"
_bold = "\033[1m"
_underline = "\033[4m"


def print_warning(message: str, end: str = "\n", flush: bool = False):
    print(_orange + "WARNING: " + message + _end, end=end, flush=flush)


def print_error(message: str, end: str = "\n", flush: bool = False):
    print(_red + "ERROR: " + message + _end, end=end, flush=flush)


def print_build_stage(message: str, end: str = "\n", flush: bool = False):
    print(_green + "\n>>> " + message + _end, end=end, flush=flush)


def print_build(message: str, end: str = "\n", flush: bool = False):
    print(_cyan + "-> " + message + _end, end=end, flush=flush)


def print_clean(message: str, end: str = "\n", flush: bool = False):
    print(_magenta + "-> " + message + _end, end=end, flush=flush)
