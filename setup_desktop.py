"""
Create a Desktop shortcut so designers can launch Prompt Room by double-clicking.
Run once after cloning/setting up the project:  python setup_desktop.py
"""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DESKTOP = Path.home() / "Desktop"
SHORTCUT_NAME = "Prompt Room.command"


def main():
    shortcut_path = DESKTOP / SHORTCUT_NAME
    content = f'''#!/bin/bash
cd "{PROJECT_ROOT}"
if [[ ! -d .venv ]]; then
  echo "Prompt Room is not set up. In Terminal run:  cd \\"{PROJECT_ROOT}\\"; ./setup.sh"
  read -r -p "Press Enter to close..."
  exit 1
fi
source .venv/bin/activate
exec streamlit run app.py --server.headless false
'''
    shortcut_path.write_text(content)
    shortcut_path.chmod(0o755)
    print(f"Created: {shortcut_path}")
    print("Double-click 'Prompt Room' on your Desktop to launch the app.")


if __name__ == "__main__":
    main()
