#!/bin/sh
set -eu
MODULE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export PYTHONPATH="$MODULE_DIR"
exec "$MODULE_DIR/.venv/bin/python" -m hotspot "$@" serve
