#!/bin/bash
cd "$(dirname "$0")"

if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "ERROR: Python not found. Install Python 3.8+ from https://www.python.org/downloads/"
    exit 1
fi

PYTHON=python3
command -v python3 &> /dev/null || PYTHON=python

echo "=== videomakerauto ==="
echo ""
echo "Installing dependencies... (first run only)"
$PYTHON -m pip install -q -r requirements.txt || { echo "pip install failed"; exit 1; }

$PYTHON run.py
