#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# Prompt Room — full setup for a fresh Mac.
# No prerequisites needed — this installs everything:
#   Xcode CLI tools (git), Homebrew, Python 3,
#   project dependencies, and Playwright Chromium.
# ──────────────────────────────────────────────────────────

set -e
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

echo ""
echo "  ╔════════════════════════════════╗"
echo "  ║     Prompt Room — Setup        ║"
echo "  ╚════════════════════════════════╝"
echo ""

# ── 1. Xcode Command Line Tools (gives us git + build essentials) ──

if ! xcode-select -p &>/dev/null; then
  echo "Step 1/6  Installing Xcode Command Line Tools (includes git)..."
  echo "          A system dialog will appear — click Install and wait."
  echo ""
  xcode-select --install 2>/dev/null || true
  # Wait for the GUI installer to finish
  echo "          Waiting for installation to complete (this can take a few minutes)..."
  until xcode-select -p &>/dev/null; do
    sleep 5
  done
  echo "          Done."
else
  echo "Step 1/6  Xcode Command Line Tools — already installed."
fi
echo ""

# ── 2. Homebrew (package manager — needed for Python 3) ──

_ensure_brew_in_path() {
  if command -v brew &>/dev/null; then return 0; fi
  if [[ -x /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
    return 0
  fi
  if [[ -x /usr/local/bin/brew ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
    return 0
  fi
  return 1
}

if ! _ensure_brew_in_path; then
  echo "Step 2/6  Installing Homebrew (this may ask for your password)..."
  echo ""
  NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || true
  _ensure_brew_in_path || true
fi

if command -v brew &>/dev/null; then
  echo "Step 2/6  Homebrew — available."
else
  echo "Step 2/6  Homebrew — could not verify. Continuing anyway..."
fi
echo ""

# ── 3. Python 3 (via Homebrew if needed) ──

_has_working_python() {
  command -v python3 &>/dev/null && python3 -c "import venv, ensurepip" &>/dev/null
}

if ! _has_working_python; then
  echo "Step 3/6  Installing Python 3..."
  if command -v brew &>/dev/null; then
    brew install python@3.12 2>/dev/null || brew install python3 2>/dev/null || true
  fi
  if ! _has_working_python; then
    echo ""
    echo "  Could not install Python 3 automatically."
    echo "  Please install it from: https://www.python.org/downloads/"
    echo "  Then re-run this script."
    exit 1
  fi
fi
echo "Step 3/6  Python 3 — $(python3 --version)"
echo ""

# ── 4. Virtual environment + Python packages ──

if [[ ! -d .venv ]]; then
  echo "Step 4/6  Creating virtual environment (.venv)..."
  python3 -m venv .venv
fi
# shellcheck source=/dev/null
source .venv/bin/activate

echo "Step 4/6  Installing Python packages..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "          Done."
echo ""

# ── 5. Playwright Chromium ──

echo "Step 5/6  Installing Playwright Chromium browser (may take a minute)..."
python -m playwright install chromium
echo "          Done."
echo ""

# ── 6. Git repo for self-updates ──

_setup_git_updates() {
  local REPO_URL="https://github.com/yotamano-wix/prompt-room.git"

  if [[ ! -d .git ]]; then
    echo "Step 6/6  Setting up git for self-updates..."
    local tmpdir
    tmpdir=$(mktemp -d)
    if GIT_TERMINAL_PROMPT=0 git clone --depth 1 "$REPO_URL" "$tmpdir" 2>/dev/null; then
      mv "$tmpdir/.git" .git
      rm -rf "$tmpdir"
      git reset HEAD -q 2>/dev/null || true
      echo "          Done. Use 'Check for updates' in the app to stay current."
    else
      rm -rf "$tmpdir"
      echo "          Skipped (repo not accessible). The app works fine without this."
      echo "          Self-updates won't work until git access is set up."
    fi
    return
  fi

  # .git exists — make sure remote uses HTTPS (SSH won't work without keys)
  local current_url
  current_url="$(git remote get-url origin 2>/dev/null || echo "")"
  if [[ "$current_url" == git@* ]]; then
    echo "Step 6/6  Switching git remote to HTTPS (easier for updates)..."
    git remote set-url origin "$REPO_URL"
    echo "          Done."
  else
    echo "Step 6/6  Git — already configured."
  fi
}
_setup_git_updates
echo ""

# ── Done ──

echo "  ╔════════════════════════════════╗"
echo "  ║       Setup complete!          ║"
echo "  ╚════════════════════════════════╝"
echo ""
echo "  To run Prompt Room:"
echo "    • Double-click  start.command  in this folder"
echo "    • Or in Terminal:  ./start.command"
echo ""

if [[ "$1" == "--desktop" ]] || [[ "$1" == "-d" ]]; then
  python3 setup_desktop.py
elif [[ -t 0 ]]; then
  read -r -p "  Create a Desktop shortcut? [y/N] " reply
  if [[ "$reply" =~ ^[yY] ]]; then
    python3 setup_desktop.py
  else
    echo "  You can add it later:  python3 setup_desktop.py"
  fi
else
  echo "  To add a Desktop shortcut:  python3 setup_desktop.py"
fi
echo ""
