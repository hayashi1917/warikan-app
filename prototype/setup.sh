#!/bin/sh
set -eu

python3 -m venv .venv

# shellcheck disable=SC1091
. .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
