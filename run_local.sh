#!/usr/bin/env sh
# Local run without Docker. Needs Python 3.9+.
set -e
cd "$(dirname "$0")/backend"
python3 -m pip install -r requirements.txt
python3 -m app.bootstrap
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
