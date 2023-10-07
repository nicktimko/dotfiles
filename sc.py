"""
Subcommands!
"""
import argparse
import asyncio
import datetime
import enum
import getpass
import inspect
import logging
import os
import pathlib
import platform
import textwrap
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import webbrowser


_subcommands = {}
def subcommand(*arg_defs):
    def _wrapper(f):
        global _subcommands
        name = f.__name__.replace("_", "-")
        _subcommands[name] = {"func": f, "arg_defs": arg_defs}
        return f
    return _wrapper


class OS(enum.Enum):
    DEBIAN = "debian"
    MACOS = "macos"
    WINDOWS = "windows"

    UNKNOWN = "unknown"

    @staticmethod
    def current():
        plat_sys = platform.system()
        if plat_sys == "Windows":
            return OS.WINDOWS
        if plat_sys == "Darwin":
            return OS.MACOS
        if plat_sys == "Linux":
            try:
                with open("/etc/debian_version") as f:
                    dist = OS.DEBIAN
                    dist.version = f.read().strip()
            except FileNotFoundError:
                pass
            else:
                return dist

        return OS.UNKNOWN


THIS_OS = OS.current()


class distrodispatch:
    def __init__(self, base_func):
        self.func = base_func
        self.__name__ = base_func.__name__

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

    def register(self, *distros):
        def _wrapper(f):
            if THIS_OS in distros:
                self.func = f
            return f
        return _wrapper


def arg(*args, **kwargs) -> tuple[tuple, dict]:
    return args, kwargs


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


L: logging.Logger = logging.getLogger()

HOME = pathlib.Path(os.environ.get("HOME", "~")).expanduser()


@subcommand(
    arg("--force", action="store_true", help="if a key is found, overwrite")
)
@distrodispatch
def ssh_keygen(args):
    """Generate an SSH key"""
    raise RuntimeError("unsupported distro")


@ssh_keygen.register(OS.DEBIAN, OS.MACOS)
def _(args):
    ssh_dir = HOME / ".ssh"
    ssh_dir.mkdir(exist_ok=True)
    keyfile = ssh_dir / "id_ed25519"
    if keyfile.exists():
        if not args.force:
            L.fatal(f"key already exists: {keyfile}")
            return 1
        keystat = keyfile.stat()
        move_target = f"~/.ssh/id_ed25519.{int(keystat.st_ctime)}.old"
        L.warning(f"key already exists, moving to {move_target}")
        keyfile.rename(pathlib.Path(move_target).expanduser())
    
    key_comment = f"{getpass.getuser()}@{socket.gethostname()}"
    subprocess.check_call([
        "ssh-keygen", 
        "-t", "ed25519", 
        "-f", str(keyfile),
        "-N", "",
        "-C", key_comment,
    ])
    L.info("generated key at %s", keyfile)

    with open(keyfile.with_suffix(".pub"), mode="r") as f:
        pubkey = f.read()

    print(f"pubkey:\n{pubkey}") #\n\nOpen GH keys page? [yN]: ", end="")
    # if input().lower() == "y":
    #     webbrowser.open("https://github.com/settings/keys")


git_config_entries = {
    "init.defaultBranch": "main",
    "user.email": "prometheus235@gmail.com",
    "user.name": "Nicholas Timkovich",
}
git_ignore_global = [
    ".vscode",
    "~*",
]

def _git_conf_line(name, value):
    base_cmd = ["git", "config", "--global", name, value]
    L.debug("calling: %r", base_cmd)
    return subprocess.check_call(base_cmd, universal_newlines=True)


@subcommand()
def gitconfig(args):
    """Configure Git"""
    try:
        current_conf = subprocess.check_output(["git", "config", "--list"], universal_newlines=True)
    except FileNotFoundError:
        L.error("could not find git, is it installed?")
        return 1
    except subprocess.CalledProcessError:
        L.error("failed call, incompatible git version?")
        return 2
    current_conf = dict(kv.split("=", 1) for kv in current_conf.splitlines())
    L.debug(f"current conf {current_conf}")
    if all(value == current_conf.get(name.lower()) for name, value in git_config_entries.items()):
        L.info("all looks good, nothing to do")
        return
    for name, value in git_config_entries.items():
        _git_conf_line(name, value)


pyenv_installer = "https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer"
def _get_pyenv_installer():
    resp = urllib.request.urlopen(pyenv_installer)
    content_type = resp.headers["Content-Type"]
    charset = "ascii"
    if content_type:
        _mime, *others = [p.strip() for p in content_type.split(";")]
        for o in others:
            if not o.startswith("charset="):
                continue
            charset = o.split("=")[1]
    content = resp.read()
    L.debug(f"downloaded {len(content)} B script")
    return content.decode(encoding=charset)


PYENV_REL_HOME = ".pyenv"
PYENV_ROOT = pathlib.Path(os.environ["HOME"]) / PYENV_REL_HOME

@subcommand()
def pyenv(args):
    # installer_script = _get_pyenv_installer()

    # proc = subprocess.Popen(
    #     ["bash"], 
    #     stdin=subprocess.PIPE,
    #     stdout=subprocess.PIPE,
    #     stderr=subprocess.PIPE,
    #     universal_newlines=True, 
    #     env={**os.environ, "PYENV_ROOT": str(PYENV_ROOT)},
    # )
    # L.info("launching script in bash...")
    # stdout, stderr = proc.communicate(installer_script)
    # retcode = proc.wait()
    # if retcode:
    #     L.error(f"script failed! retval: {retcode}")
    #     print_abbreviated_log("stdout", "93", stdout)
    #     print_abbreviated_log("stderr", "91", stderr)
    #     return retcode

    # L.info("configuring rcfile")
    # configure_pyenv_for_shell(os.environ["SHELL"].split("/")[-1])
    install_pyenv_libs()


@distrodispatch
def install_pyenv_libs():
    L.warning("unknown distro, not sure what libs to use")


@install_pyenv_libs.register(OS.DEBIAN)
def _():
    packages = [
        "zlib1g-dev",
        "zlib1g",
        "libssl-dev", 
        "libbz2-dev", 
        "libsqlite3-dev",
        "libreadline-dev"
    ]
    print("# to run:")
    print("sudo apt-get update")
    print("sudo apt-get install -y \\\n    ", end="")
    print(" \\\n    ".join(packages))
    # subprocess.check_call(["apt-"])


def print_abbreviated_log(name, colorcode, content, line_lim=20):
    lines = content.splitlines()
    if len(lines) > line_lim:
        full_log_file = pathlib.Path(tempfile.gettempdir()) / f"{name}-{int(time.time())}.log"
        lines = [
            f"see full log in {full_log_file}",
            f"...[{len(lines) - line_lim} lines]",
        ] + lines[-line_lim:]
    if content.strip():
        print(color(format(name, "-^30s"), colorcode))
        print("".join(lines))


shellrc_snippets = {
    "bash": {
        "cmds": f"""\
export PYENV_ROOT="$HOME/{PYENV_REL_HOME}"
command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
""",
        "rcfile": pathlib.Path("~/.bashrc").expanduser(),
    },
}

def configure_pyenv_for_shell(shell):
    snippet = shellrc_snippets[shell]
    with open(snippet["rcfile"], mode="r+") as f:
        rcfile = f.read()
        if snippet["cmds"] in rcfile:
            L.info(f"snippet already appears in {snippet['rcfile']}")
            return
        f.write(snippet["cmds"])


def main():
    global _subcommands
    global L
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

    loglevel = {
        0: logging.WARNING,
        1: logging.INFO,
        2: logging.DEBUG,
    }.get(args.verbose, logging.DEBUG)

    L = logging.getLogger("main")
    handler = logging.StreamHandler(stream=sys.stderr)
    cli_fmt = CLILogFmt()
    handler.setFormatter(cli_fmt)
    L.addHandler(handler)
    L.setLevel(loglevel)

    if inspect.iscoroutinefunction(args.func):
        retval = asyncio.run(args.func(args))
    else:
        retval = args.func(args)
    return retval

if __name__ == "__main__":
    sys.exit(main())