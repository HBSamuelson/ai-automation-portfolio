#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pytest -q n8n-lead-intake/tests
python3 -m pytest -q lead-list-scraper/tests
python3 -m pytest -q voice-receptionist/tests
(cd website-chatbot && npm test)
