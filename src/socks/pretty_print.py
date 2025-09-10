_red = "\033[91m"
_green = "\033[92m"
_orange = "\033[93m"
_blue = "\033[94m"
_magenta = "\033[95m"
_cyan = "\033[96m"
_end = "\033[0m"
_bold = "\033[1m"
_underline = "\033[4m"


def print_info(message: str, end: str = "\n", flush: bool = True):
    print(_blue + "[INFO] " + message + _end, end=end, flush=flush)


def print_warning(message: str, end: str = "\n", flush: bool = True):
    print(_orange + "[WARNING] " + message + _end, end=end, flush=flush)


def print_error(message: str, end: str = "\n", flush: bool = True):
    print(_red + "[ERROR] " + message + _end, end=end, flush=flush)


def print_build_stage(message: str, end: str = "\n", flush: bool = True):
    print(_green + "\n> " + message + _end, end=end, flush=flush)


def print_build(message: str, end: str = "\n", flush: bool = True):
    print(_cyan + ">> " + message + _end, end=end, flush=flush)


def print_clean(message: str, end: str = "\n", flush: bool = True):
    print(_magenta + ">> " + message + _end, end=end, flush=flush)
