#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python backend/app.py
