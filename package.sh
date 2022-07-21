#!/bin/bash -ex
set -o pipefail
[ -e "${HOME}/.pyenv" ] || curl -L https://raw.githubusercontent.com/yyuu/pyenv-installer/master/bin/pyenv-installer | bash -e
export PATH="${HOME}/.pyenv/bin:${HOME}/.local/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"
pyenv install 3.9.4

VENV_NAME=agentless-build
pyenv virtualenv 3.9.4 "${VENV_NAME}"
pyenv local "${VENV_NAME}"
pip3 install poetry
poetry install
poetry run python package.py
