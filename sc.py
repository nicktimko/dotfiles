"""
Subcommands!
"""
import argparse
import asyncio
import datetime
import inspect
import logging
import textwrap
import sys
import time


_subcommands = {}
def subcommand(*arg_defs):
    def _wrapper(f):
        global _subcommands
        name = f.__name__.replace("_", "-")
        _subcommands[name] = {"func": f, "arg_defs": arg_defs}
        return f
    return _wrapper


def arg(*args, **kwargs) -> tuple[tuple, dict]:
    return args, kwargs

@subcommand()
def apple(args, logger):
    """docs"""

def color(s, code) -> str:
    return f"\x1B[{code}m{s}\x1B[0m"

def code(levelno: int) -> str:
    for level, name, colorcode in [
        (logging.CRITICAL, "crit", "30;41"),
        (logging.ERROR, "err", "91"),
        (logging.WARNING, "warn", "93"),
        (logging.INFO, "info", "92"),
        (logging.DEBUG, "dbug", "96"),
    ]:
        if levelno >= level:
            return color(format(name, "<4s"), colorcode)
    return color("trce", "90")


class CLILogFmt(logging.Formatter):
    """
    info: T = 2052-03-12T02:04:12+00:00 
    warn: +  0.032s something happened.
    erro: + 10.510s
    crit: +999.999s
    dbug: +1202.123s
    """
    def __init__(self, *, style="%"):
        super().__init__(style=style)
        self.start = time.time()  
        # time.monotonic prob better, but `LogRecord.created` is time.time
        self.printed_init_time = False

    def format(self, record) -> str:
        init = ""
        if not self.printed_init_time:
            ts = datetime.datetime.fromtimestamp(self.start).isoformat(timespec="milliseconds")[11:]
            init = f"T={ts}\n"
            self.printed_init_time = True

        dt = record.created - self.start
        return f"{init}{code(record.levelno)}: +{dt: 7.3f}s {record.msg}"


def main():
    global _subcommands
    parser = argparse.ArgumentParser(
        description=textwrap.dedent(__doc__),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-v", "--verbose", action="count", default=0)
    subparsers = parser.add_subparsers(required=True)

    for name, sc_data in _subcommands.items():
        subcmd_parser = subparsers.add_parser(name, help=sc_data["func"].__doc__)
        for args, kwargs in sc_data["arg_defs"]:
            subcmd_parser.add_argument(*args, **kwargs)
        subcmd_parser.set_defaults(func=sc_data["func"])
    
    args = parser.parse_args()

    logger = logging.getLogger("main")
    handler = logging.StreamHandler(stream=sys.stderr)
    cli_fmt = CLILogFmt()
    handler.setFormatter(cli_fmt)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    if inspect.iscoroutinefunction(args.func):
        retval = asyncio.run(args.func(args, logger))
    else:
        retval = args.func(args, logger)
    return retval

if __name__ == "__main__":
    sys.exit(main())