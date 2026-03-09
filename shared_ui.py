from __future__ import annotations

"""Shared Streamlit UI helpers used by all pages (sidebar, CSS, git self-update)."""

import os
import subprocess
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent


def git_info() -> dict:
    """Return current commit hash (short), branch, and message. Empty strings on error."""
    info = {"hash": "", "branch": "", "message": "", "date": ""}
    try:
        info["hash"] = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(PROJECT_ROOT), stderr=subprocess.DEVNULL,
        ).decode().strip()
        info["branch"] = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(PROJECT_ROOT), stderr=subprocess.DEVNULL,
        ).decode().strip()
        info["message"] = subprocess.check_output(
            ["git", "log", "-1", "--format=%s"], cwd=str(PROJECT_ROOT), stderr=subprocess.DEVNULL,
        ).decode().strip()
        info["date"] = subprocess.check_output(
            ["git", "log", "-1", "--format=%cd", "--date=relative"], cwd=str(PROJECT_ROOT), stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        pass
    return info


def git_update() -> tuple[bool, str]:
    """Pull latest from remote and reinstall deps. Returns (success, output_text)."""
    git_dir = PROJECT_ROOT / ".git"
    if not git_dir.exists():
        return False, "Not a git repository. Re-run setup.sh to enable updates."

    venv_pip = PROJECT_ROOT / ".venv" / "bin" / "pip"
    pip_cmd = str(venv_pip) if venv_pip.exists() else "pip"
    lines: list[str] = []
    try:
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        subprocess.run(
            ["git", "stash", "--include-untracked"], cwd=str(PROJECT_ROOT),
            capture_output=True, text=True, timeout=15, env=env,
        )
        pull = subprocess.run(
            ["git", "pull", "--ff-only"], cwd=str(PROJECT_ROOT),
            capture_output=True, text=True, timeout=60, env=env,
        )
        lines.append(pull.stdout.strip())
        if pull.returncode != 0:
            pull_err = pull.stderr or ""
            if "Not possible to fast-forward" in pull_err or "diverging" in pull_err.lower() or "local changes" in pull_err.lower():
                subprocess.run(
                    ["git", "fetch", "origin"], cwd=str(PROJECT_ROOT),
                    capture_output=True, text=True, timeout=60, env=env,
                )
                reset = subprocess.run(
                    ["git", "reset", "--hard", "origin/main"], cwd=str(PROJECT_ROOT),
                    capture_output=True, text=True, timeout=30, env=env,
                )
                lines.append(reset.stdout.strip())
                if reset.returncode != 0:
                    lines.append(reset.stderr.strip())
                    return False, "\n".join(lines)
            else:
                lines.append(pull_err.strip())
                return False, "\n".join(lines)
        pip = subprocess.run(
            [pip_cmd, "install", "-q", "-r", "requirements.txt"], cwd=str(PROJECT_ROOT),
            capture_output=True, text=True, timeout=120,
        )
        if pip.returncode != 0:
            lines.append(f"pip install failed:\n{pip.stderr.strip()}")
            return False, "\n".join(lines)
        return True, "\n".join(lines) or "Up to date."
    except subprocess.TimeoutExpired:
        return False, "Update timed out. Check your network connection."
    except FileNotFoundError:
        return False, "git is not installed. Re-run setup.sh to install it."
    except Exception as e:
        return False, str(e)


def render_sidebar():
    """Sidebar: version info and self-update button."""
    with st.sidebar:
        st.markdown("### Settings")
        info = git_info()
        if info["hash"]:
            st.caption(f"Version: `{info['hash']}` on `{info['branch']}`")
            st.caption(f"{info['message']} — {info['date']}")
        else:
            st.caption("Version info not available.")
            st.caption("Run `./setup.sh` to enable self-updates.")

        if st.button("Check for updates", key="update_btn"):
            with st.spinner("Pulling latest changes..."):
                ok, output = git_update()
            if ok:
                already = "Already up to date" in output or "Already up-to-date" in output
                if already:
                    st.success("Already up to date.")
                else:
                    st.success("Updated! The app will reload automatically.")
                    new_info = git_info()
                    if new_info["hash"]:
                        st.caption(f"Now at `{new_info['hash']}`: {new_info['message']}")
            else:
                st.error("Update failed.")
                st.code(output)
        st.markdown("---")


THUMB_HEIGHT_PX = 96


def apply_custom_css():
    st.markdown(f"""
    <style>
    .stApp {{ background-color: #f8fafc !important; }}
    .block-container {{ padding-top: 2.25rem; padding-bottom: 4rem; max-width: 880px; }}
    p, span, label, .stMarkdown, .stMarkdown p, [data-testid="stCaptionContainer"] {{ color: #1e293b !important; }}
    h1, h2, h3 {{ font-weight: 500; letter-spacing: -0.02em; color: #0f172a !important; }}
    h1 {{ font-size: 1.65rem; margin-bottom: 0.25rem; }}
    h2 {{ font-size: 0.95rem; font-weight: 600; color: #475569 !important; margin-top: 2.25rem; margin-bottom: 0.75rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.5rem; }}
    [data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea, [data-testid="stNumberInput"] input {{
        background-color: #fff !important; color: #1e293b !important;
        border: 1px solid #e2e8f0; border-radius: 8px;
    }}
    [data-testid="stRadio"] label, [data-testid="stCheckbox"] label {{ color: #1e293b !important; }}
    .stRadio > div {{ gap: 1rem; }}
    .stButton > button {{ border-radius: 8px; font-weight: 500; transition: box-shadow 0.15s ease; }}
    .stButton > button:hover {{ box-shadow: 0 2px 12px rgba(0,0,0,0.06); }}
    .stButton > button[kind="primary"], .stButton > button[kind="primary"] * {{ color: #fff !important; }}
    .stButton > button[kind="primary"]:hover, .stButton > button[kind="primary"]:hover * {{ color: #fff !important; }}
    [data-testid="stExpander"] {{ border: 1px solid #e2e8f0; border-radius: 10px; background: #fff !important; }}
    [data-testid="stExpander"] summary, [data-testid="stExpander"] p {{ color: #1e293b !important; }}
    .caption {{ font-size: 0.8rem; color: #64748b !important; }}
    .hint {{ font-size: 0.8rem; color: #64748b !important; margin-top: 0.25rem; }}
    [data-testid="stDataFrame"] {{ color: #1e293b !important; }}
    [data-testid="stImage"] img {{ height: {THUMB_HEIGHT_PX}px; width: 100%; object-fit: cover; object-position: top; border-radius: 6px; }}
    [data-testid="stImage"] {{ margin-bottom: 4px; }}
    hr {{ border: none; border-top: 1px solid #e2e8f0; margin: 1.5rem 0; }}
    [data-testid="stVerticalBlockBorderWrapper"] {{ margin-bottom: 0.35rem; }}
    </style>
    """, unsafe_allow_html=True)
