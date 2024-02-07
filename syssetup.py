"""
Subcommands!
"""
import argparse
import asyncio
import datetime
import enum
import getpass
import http
import inspect
import json
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

def _download(url):
    L.debug(f"> GET {url}")
    resp = urllib.request.urlopen(url)
    statuscode = resp.status if sys.version_info >= (3, 9) else resp.code
    L.debug(f"< {statuscode} {http.HTTPStatus(statuscode).phrase}")
    content_type = resp.headers["Content-Type"]
    L.debug(f"< Content-Type: {content_type}")
    L.debug(f"< Content-Length: {resp.headers['Content-Length']}")
    charset = "ascii"
    if content_type:
        _mime, *others = [p.strip() for p in content_type.split(";")]
        for o in others:
            if not o.startswith("charset="):
                continue
            charset = o.split("=")[1]
    content = resp.read()
    return content.decode(encoding=charset)


PYENV_REL_HOME = ".pyenv"
PYENV_ROOT = pathlib.Path(os.environ["HOME"]) / PYENV_REL_HOME

@subcommand()
def pyenv(args):
    installer_script = _download(pyenv_installer)

    proc = subprocess.Popen(
        ["bash"], 
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True, 
        env={**os.environ, "PYENV_ROOT": str(PYENV_ROOT)},
    )
    L.info("launching script in bash...")
    stdout, stderr = proc.communicate(installer_script)
    retcode = proc.wait()
    if retcode:
        L.error(f"script failed! retval: {retcode}")
        print_abbreviated_log("stdout", "93", stdout)
        print_abbreviated_log("stderr", "91", stderr)
        return retcode

    L.info("configuring rcfile")
    configure_pyenv_for_shell(os.environ["SHELL"].split("/")[-1])
    print(missing_pybuild_libs())


@subcommand()
@distrodispatch
def install_pybuild_libs(args):
    L.warning("unknown distro, not sure what libs to use")
    return 1


APT_PYBUILD_PACKAGES = [
    "zlib1g-dev",
    "zlib1g",
    "libssl-dev", 
    "libbz2-dev", 
    "libsqlite3-dev",
    "libreadline-dev",
    "libffi-dev",
    "liblzma-dev",
    "tk-dev",
]

@install_pybuild_libs.register(OS.DEBIAN)
def _(args):
    need_libs = missing_pybuild_libs()
    if not need_libs:
        L.info("looks good, nothing to do")
        return
    L.info(f"installing: {', '.join(need_libs)}")
    # subprocess.check_call(["sudo", "apt-get", "update"])
    subprocess.check_call(["sudo", "apt-get", "install", "-y", *need_libs])


@distrodispatch
def missing_pybuild_libs():
    L.warning("unknown distro, not sure what libs to use")


@missing_pybuild_libs.register(OS.DEBIAN)
def _():
    have = {False: set(), True: set()}
    for pkg in APT_PYBUILD_PACKAGES:
        have["installed" in deb_package_status(pkg)].add(pkg)
    L.debug(f"package installed?: {have}")
    return have[False]


def deb_package_status(pkg_name):
    out = subprocess.check_output(["dpkg", "--status", pkg_name], universal_newlines=True)
    for line in (l.strip() for l in out.splitlines()):
        if not line.startswith("Status:"):
            continue
        _status, statuses = line.split(":", 1)
        break
    else:
        return set()
    return set(statuses.split())


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


@subcommand()
def pyenv_install_supported(args):
    L.debug("requesting eol data")
    versions = json.loads(_download("https://endoflife.date/api/Python.json"))
    L.debug(f"found {len(versions)} version cycles")
    today = datetime.datetime.today().strftime("%Y-%m-%d")
    supported = [ver["latest"] for ver in versions if ver["eol"] >= today]
   
    L.info("to install: " + ", ".join(supported))

    if missing_pybuild_libs():
        print("missing libraries to build Pythons, run command 'install-pybuild-libs'")
        return 1

    for ver in supported:
        L.info(f"pyenv install {ver}")
        subprocess.check_call(
            ["pyenv", "install", ver, "--skip-existing"], 
            executable=PYENV_ROOT / "bin" / "pyenv",
        )


JUPYTER_PY_VER = "3.11"
JUPYTER_DIR = "~/.jupyter"
JUPYTER_CONF_FILENAME = "jup-conf.py"
JUPYTER_ROOT_DIR = "~/Code"

_JUPYTER_ENTRY_SCRIPT = f"""\
#!/bin/sh

SCRIPT=$(readlink -f "$0")
SCRIPTPATH=$(dirname "$SCRIPT")

$SCRIPTPATH/bin/python -m jupyter lab \\
    --config $SCRIPTPATH/{JUPYTER_CONF_FILENAME}
"""

_JUPYTER_CONF = f"""\
c = get_config() # noqa
c.ServerApp.port = 2222

c.ServerApp.open_browser = False
c.ExtensionApp.open_browser = False
c.LabServerApp.open_browser = False
c.LabApp.open_browser = False

c.ServerApp.root_dir = '{str(pathlib.Path(JUPYTER_ROOT_DIR).expanduser())}'
"""

@subcommand()
def jupyter_server(args):
    jupyter_dir = pathlib.Path(JUPYTER_DIR).expanduser()
    # subprocess.check_call([f"python{JUPYTER_PY_VER}", "-m", "venv", jupyter_dir])
    # subprocess.check_call(
        # [str(jupyter_dir / "bin" / "python"), "-m", "pip", "install", "jupyterlab"],
    # )
    with open(jupyter_dir / JUPYTER_CONF_FILENAME, mode="w") as f:
        f.write(_JUPYTER_CONF)
    with open(jupyter_dir / "entry.sh", mode="w") as f:
        f.write(_JUPYTER_ENTRY_SCRIPT)


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