#!/usr/bin/env sh
set -e
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then
  exec python3 app.py "$@"
fi
exec python app.py "$@"
