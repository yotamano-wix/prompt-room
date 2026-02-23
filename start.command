#!/bin/bash
cd "$(dirname "$0")"
if [[ ! -d .venv ]]; then
  echo "Prompt Room is not set up. Run:  ./setup.sh"
  read -r -p "Press Enter to close..."
  exit 1
fi
source .venv/bin/activate
exec streamlit run app.py --server.headless false
