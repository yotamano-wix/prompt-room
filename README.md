# Prompt Room

Batch Wix site generation with a simple UI. Define requests, set parameters (prompts, reference images, brand book), run, and download results as CSV.

**No coding required after setup. No Cursor or IDE needed.**

---

## Setup (new computer)

Works on a **completely fresh Mac** — nothing needs to be pre-installed.

### 1. Get the project folder

**Option A — Clean zip (no git, no history, smallest)**  
On a machine that already has the repo:

```bash
cd /path/to/prompt-room
./make_release_zip.sh
```

This creates `prompt-room-YYYYMMDD.zip`. Copy that file to the new computer (AirDrop, USB, drive), unzip it, then double-click **`setup.command`** (or run `./setup.sh` in Terminal). No `.git`, `.venv`, or batch outputs — just what’s needed to run.

**Option B — Git clone (best if they have git)**  
```bash
git clone https://github.com/yotamano-wix/prompt-room.git
cd prompt-room
```

**Option C — Copy the whole folder**  
Copy the project folder via AirDrop / USB / shared drive (includes `.git` and possibly `.venv`; exclude `batch_results/` and `.playwright-profile*/` if you want it smaller).

### 2. Run the setup

**Easiest:** Double-click **`setup.command`** in the project folder. Terminal will open and run the setup; when it’s done, press Enter to close.

**If macOS blocks it:** The first time you double-click `setup.command` (or `start.command`), macOS may say it “cannot be opened because it is from an unidentified developer.” Fix it once: **right‑click** the file → **Open** → **Open** in the dialog. After that it will run normally. Or go to **System Settings → Privacy & Security → Security** and click **Allow anyway** for the script.

**Or** open Terminal, go to the project folder, and run:

```bash
cd /path/to/prompt-room
./setup.sh
```

> Replace `/path/to/prompt-room` with the actual folder path (e.g. the folder you unzipped).
> Tip: type `cd ` then drag the folder into the Terminal window.

The setup script **automatically installs everything**:

| Step | What it installs | Why |
|------|-----------------|-----|
| 1 | Xcode Command Line Tools | Gives us `git` (for updates) |
| 2 | Homebrew | macOS package manager |
| 3 | Python 3 | Runs the app |
| 4 | Python packages | Project dependencies |
| 5 | Playwright Chromium | Browser for Wix automation |
| 6 | Git remote (HTTPS) | So the app can update itself |

At the end it asks if you want a **Desktop shortcut** (recommended).

### 3. Add your Wix credentials

Create a file called `config.json` in the project folder:

```json
{
  "app_id": "your-app-id",
  "secret_key": "your-secret-key"
}
```

This file is git-ignored and never shared.

### 4. Run

- **Double-click** `start.command` in the project folder, or
- **Double-click** the Desktop shortcut (if you created one), or
- In Terminal: `./start.command`

The app opens in your browser.

---

## Updating

When a new version is pushed to git:

1. Open the app
2. Click the **sidebar arrow** (`>`) on the left
3. Click **Check for updates**

The app pulls the latest code and reloads automatically. No Terminal needed.

---

## Project layout

| Path | Purpose |
|------|---------|
| `app.py` | Streamlit UI |
| `batch_preview.py` | Batch runner (used when you click Run) |
| `preview_automation.py` | Wix preview automation |
| `setup.sh` | One-time setup (installs everything) |
| `setup.command` | Double-click to run setup (no Terminal needed first) |
| `start.command` | Launcher (double-click to start) |
| `setup_desktop.py` | Creates a Desktop shortcut |
| `requirements.txt` | Python dependencies |
| `config.json` | Wix credentials (**do not share**) |
| `batch_config.json` | Default prompts and image pool |
| `prompts_config.json` | Prompt IDs and Wix config |

Results are saved under `batch_results/` (timestamped folders).
