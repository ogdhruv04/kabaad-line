#!/usr/bin/env bash
# Start the API (:8000) and web app (:5173) for a local demo. Ctrl+C stops both.
# The tunnel for the ElevenLabs webhooks is separate (see README → "Letting the voice agent reach your laptop").
set -euo pipefail
cd "$(dirname "$0")"
.venv/bin/uvicorn server.main:app --port 8000 --reload --reload-dir server &
API=$!
trap 'kill $API 2>/dev/null' EXIT
cd web && npx vite --port 5173 --host 127.0.0.1
