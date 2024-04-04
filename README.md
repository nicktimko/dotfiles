# dotfiles

## macOS

1. `xcode-select --install` and agree, etc, etc.
1. Install Homebrew. Copy latest install line from [brew.sh/](https://brew.sh/) or [the GH repo](https://github.com/Homebrew/brew)
1. Install Homebrew packages:
    ```
    brew install \
        pyenv \
        pyenv-virtualenv \
        pyenv-pip-migrate \
        pyenv-ccache \
        ffmpeg \
        xz \
        tcl-tk \
        sqlite3 \
        zlib \
        readline \
        openssl 
    ```
1. Install Oh My ZSH! Copy latest install line from [ohmyz.sh](https://ohmyz.sh/#install) or [the GH repo](https://github.com/ohmyzsh/ohmyzsh)
1. Build a Python or five. I usually install latest patch version of everything not EOL'd, which if the latest is 3.x, also includes 3.x-1, 3.x-2, 3.x-3... See `pyenv install --list` for what's available, or check [endoflife.date](https://endoflife.date/):
    ```
    # (this is 'one' line/command)
    curl -sSL https://endoflife.date/api/python.json \
    | jq --arg today $(date '+%Y-%m-%d') \
        --raw-output \
        '.[] | select(.eol > $today) | .cycle' \
    | while read ver
    do
        latest_available=$(pyenv install --list \
            | grep -e "^\s*$ver" \
            | tail -1 \
            | xargs \
        )
        echo "$ver >> $latest_available"
        pyenv install --skip-existing $latest_available
    done
    ```
1. pyenv completions for zsh: `pyenv init >> ~/.zshrc`
1. Create general-purpose Python virtualenv and set as global default
    ```
    $latest=3.12.2
    pyenv virtualenv $latest main
    # be able to launch a specific Python version if desired.
    pyenv global main 3.12.2 3.11.8 3.10.13 3.9.18 3.8.18
    ```
1. [PipX](https://pipx.pypa.io/)
    1. Install & Configure
        ```
        brew install pipx
        pipx ensurepath
        ```

    1. Install some good stand-alone utils. HTTPie gives `http`, which is like cURL for the 21st century. Black is just nice to have anywhere if working with Python.
        ```
        pipx install \
            httpie \
            black
        ```

1. Jupyter Notebook
    1. Prep virtualenv
        ```
        python -m venv ~/.local/jupyter
        ~/.local/jupyter/bin/python -m pip install jupyter
        ```

    1. Configure... TODO

1. If you installed [VS Code](https://code.visualstudio.com/), search for *"Shell Command: Install 'code' command in PATH"* and run that so `code` works on the command line.

# `syssetup.py`

Working on automating more of this for multiple OSs, but I need it so infrequently that it's a bit of playing catch-up every time I get a new computer and needing to update a few packages here and there, which kinda obviates trying to automate it all.

```
python3 syssetup.py pyenv
python3 syssetup.py install-pybuild-libs
python3 syssetup.py pyenv-install-supported
pyenv virtualenv 3.12.0 global
pyenv global global 3.12.0 3.11.6 3.10.13 3.9.18 3.8.18
```