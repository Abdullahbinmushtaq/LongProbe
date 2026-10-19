#!/usr/bin/env bash
# Install this checkout for reproducible, offline sample retrieval scenarios.
set -euo pipefail

DEMO_REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DEMO_PYTHON="${DEMO_PYTHON:-python3}"
"$DEMO_PYTHON" -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11 or newer is required"'
"$DEMO_PYTHON" -m venv "$DEMO_REPO_ROOT/demos/.demo_venv"
"$DEMO_REPO_ROOT/demos/.demo_venv/bin/python" -m pip install -e "$DEMO_REPO_ROOT"
"$DEMO_REPO_ROOT/demos/.demo_venv/bin/python" -c 'import longprobe; print("Demo package:", longprobe.__version__)'
printf '%s\n' 'Demo environment ready. No model download, API key, or vector database is needed.'
