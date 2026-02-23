#!/usr/bin/env bash
# Create a compact zip for installing on another computer.
# Contains only source, config, and data — no .git, .venv, or batch outputs.
# Usage: ./make_release_zip.sh

set -e
cd "$(dirname "$0")"
OUT="prompt-room-$(date +%Y%m%d).zip"
git archive -o "$OUT" HEAD
echo "Created: $OUT"
echo "Share this file. On the other computer: unzip, then run ./setup.sh"
