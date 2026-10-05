#!/usr/bin/env bash
# Run the full test suite. It builds a demo workspace in a temporary
# directory and never writes into this repository.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
exec "${PYTHON:-python3}" -m unittest discover -s tests -v
