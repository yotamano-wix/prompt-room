from __future__ import annotations

"""
Prompt Room — Streamlit UI for batch Wix site generation.
Minimal, aesthetic UI for designers. Configure requests; optional reference images and brand book; run; download CSV.
"""

import base64
import json
import os
import random
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent
BATCH_CONFIG_PATH = PROJECT_ROOT / "batch_config.json"
REFERENCE_IMAGES_CSV = PROJECT_ROOT / "reference_images.csv"
PROMPTS_CONFIG_PATH = PROJECT_ROOT / "prompts_config.json"
BATCH_RESULTS_DIR = PROJECT_ROOT / "batch_results"
UPLOADS_DIR = PROJECT_ROOT / "batch_reference_images"

# Ensure uploads dir exists
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


# --------------- Git helpers (self-update) ---------------

def _git_info() -> dict:
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


def _git_update() -> tuple[bool, str]:
    """Pull latest from remote and reinstall deps. Returns (success, output_text)."""
    git_dir = PROJECT_ROOT / ".git"
    if not git_dir.exists():
        return False, "Not a git repository. Re-run setup.sh to enable updates."

    venv_pip = PROJECT_ROOT / ".venv" / "bin" / "pip"
    pip_cmd = str(venv_pip) if venv_pip.exists() else "pip"
    lines = []
    try:
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        pull = subprocess.run(
            ["git", "pull", "--ff-only"], cwd=str(PROJECT_ROOT),
            capture_output=True, text=True, timeout=60, env=env,
        )
        lines.append(pull.stdout.strip())
        if pull.returncode != 0:
            if "Not possible to fast-forward" in pull.stderr or "diverging" in pull.stderr.lower():
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
                lines.append(pull.stderr.strip())
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


def _render_sidebar():
    """Sidebar: version info and self-update button."""
    with st.sidebar:
        st.markdown("### Settings")
        info = _git_info()
        if info["hash"]:
            st.caption(f"Version: `{info['hash']}` on `{info['branch']}`")
            st.caption(f"{info['message']} — {info['date']}")
        else:
            st.caption("Version info not available.")
            st.caption("Run `./setup.sh` to enable self-updates.")

        if st.button("Check for updates", key="update_btn"):
            with st.spinner("Pulling latest changes..."):
                ok, output = _git_update()
            if ok:
                already = "Already up to date" in output or "Already up-to-date" in output
                if already:
                    st.success("Already up to date.")
                else:
                    st.success("Updated! The app will reload automatically.")
                    new_info = _git_info()
                    if new_info["hash"]:
                        st.caption(f"Now at `{new_info['hash']}`: {new_info['message']}")
            else:
                st.error("Update failed.")
                st.code(output)
        st.markdown("---")


def load_batch_config():
    prompts = []
    max_concurrent = 2
    if BATCH_CONFIG_PATH.exists():
        with open(BATCH_CONFIG_PATH, "r") as f:
            config = json.load(f)
        prompts = config.get("user_prompts", [])
        max_concurrent = config.get("max_concurrent", 2)

    urls = []
    images_pool_brand_books = {}
    if REFERENCE_IMAGES_CSV.exists():
        try:
            df = pd.read_csv(REFERENCE_IMAGES_CSV)
            url_col = "Image URL"
            bb_col = "Image Brand Book"
            if url_col in df.columns:
                urls = df[url_col].dropna().astype(str).str.strip().tolist()
                urls = [u for u in urls if u]
            if bb_col in df.columns:
                for _, row in df.iterrows():
                    u = row.get(url_col)
                    if pd.isna(u) or not str(u).strip():
                        continue
                    u = str(u).strip()
                    bb = row.get(bb_col)
                    if pd.isna(bb) or not str(bb).strip():
                        images_pool_brand_books[u] = None
                    else:
                        images_pool_brand_books[u] = str(bb).strip()
                # Ensure every URL has an entry (None if not in df)
                for u in urls:
                    images_pool_brand_books.setdefault(u, None)
        except Exception:
            urls = []
            images_pool_brand_books = {}
    return prompts, urls, images_pool_brand_books, max_concurrent


def load_prompts_config():
    if not PROMPTS_CONFIG_PATH.exists():
        return {}
    with open(PROMPTS_CONFIG_PATH, "r") as f:
        config = json.load(f)
    wix = config.get("wix_preview", {})
    overrides = dict(wix.get("prompt_overrides", {}))
    prompts = config.get("prompts", {})
    if "architect" in prompts:
        overrides.setdefault("architectPromptId", prompts["architect"].get("id", ""))
    if "curator" in prompts:
        overrides.setdefault("typographyPromptId", prompts["curator"].get("id", ""))
    if "copier" in prompts:
        overrides.setdefault("copierPromptId", prompts["copier"].get("id", ""))
    overrides.setdefault("designerPromptId", "")
    return overrides


def image_to_data_url(bytes_data: bytes, mimetype: str = "image/png") -> str:
    b64 = base64.b64encode(bytes_data).decode("ascii")
    return f"data:{mimetype};base64,{b64}"


# Thumbnail fixed height (crop to show top)
THUMB_HEIGHT_PX = 96

def apply_custom_css():
    st.markdown(f"""
    <style>
    /* Light, calm base */
    .stApp {{ background-color: #f8fafc !important; }}
    .block-container {{ padding-top: 2.25rem; padding-bottom: 4rem; max-width: 880px; }}
    /* Typography */
    p, span, label, .stMarkdown, .stMarkdown p, [data-testid="stCaptionContainer"] {{ color: #1e293b !important; }}
    h1, h2, h3 {{ font-weight: 500; letter-spacing: -0.02em; color: #0f172a !important; }}
    h1 {{ font-size: 1.65rem; margin-bottom: 0.25rem; }}
    h2 {{ font-size: 0.95rem; font-weight: 600; color: #475569 !important; margin-top: 2.25rem; margin-bottom: 0.75rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.5rem; }}
    /* Inputs: clean and consistent */
    [data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea, [data-testid="stNumberInput"] input {{
        background-color: #fff !important; color: #1e293b !important;
        border: 1px solid #e2e8f0; border-radius: 8px;
    }}
    [data-testid="stRadio"] label, [data-testid="stCheckbox"] label {{ color: #1e293b !important; }}
    .stRadio > div {{ gap: 1rem; }}
    /* Buttons */
    .stButton > button {{ border-radius: 8px; font-weight: 500; transition: box-shadow 0.15s ease; }}
    .stButton > button:hover {{ box-shadow: 0 2px 12px rgba(0,0,0,0.06); }}
    /* Primary button: white label */
    .stButton > button[kind="primary"], .stButton > button[kind="primary"] * {{ color: #fff !important; }}
    .stButton > button[kind="primary"]:hover, .stButton > button[kind="primary"]:hover * {{ color: #fff !important; }}
    /* Expanders as subtle cards */
    [data-testid="stExpander"] {{ border: 1px solid #e2e8f0; border-radius: 10px; background: #fff !important; }}
    [data-testid="stExpander"] summary, [data-testid="stExpander"] p {{ color: #1e293b !important; }}
    .caption {{ font-size: 0.8rem; color: #64748b !important; }}
    .hint {{ font-size: 0.8rem; color: #64748b !important; margin-top: 0.25rem; }}
    [data-testid="stDataFrame"] {{ color: #1e293b !important; }}
    /* Ref thumbnails */
    [data-testid="stImage"] img {{ height: {THUMB_HEIGHT_PX}px; width: 100%; object-fit: cover; object-position: top; border-radius: 6px; }}
    [data-testid="stImage"] {{ margin-bottom: 4px; }}
    /* Slightly softer horizontal rules */
    hr {{ border: none; border-top: 1px solid #e2e8f0; margin: 1.5rem 0; }}
    </style>
    """, unsafe_allow_html=True)


def _results_table_from_dir(batch_dir: Path, key_prefix: str = "past") -> None:
    """Render results table + Download CSV + report link for a given batch directory."""
    res_path = batch_dir / "results.json"
    csv_path = batch_dir / "results.csv"
    report_path = batch_dir / "report.html"
    if not res_path.exists():
        st.caption("No results yet for this batch.")
        return
    with open(res_path, "r") as f:
        results = json.load(f)
    if not results:
        st.caption("Results file is empty.")
        return
    df = pd.DataFrame([{
        "Run #": r.get("run_id"),
        "User Request": (r.get("user_prompt") or "")[:200],
        "Reference Image URL": (r.get("reference_image_url") or "")[:80],
        "Publish URL": r.get("publish_url") or "",
        "Editor URL": r.get("editor_url") or "",
        "Screenshot": r.get("screenshot_path") or "",
        "Brand Book Preview": (r.get("brand_book_preview") or "")[:300],
        "Status": "error" if r.get("error") else "success",
        "Error": r.get("error") or "",
    } for r in results])
    st.dataframe(df, width="stretch", hide_index=True)
    if csv_path.exists():
        st.download_button("Download CSV", data=csv_path.read_bytes(), file_name=csv_path.name, mime="text/csv", key=f"{key_prefix}_dl_csv")
    if report_path.exists():
        st.markdown(f"[Open HTML Report](file://{report_path.absolute()})")


def _render_running_view():
    """Show only progress/results when a run is in progress. No form. Live refresh, Abort, then back to form."""
    output_dir = st.session_state.get("run_output_dir")
    proc = st.session_state.get("run_process")
    if not output_dir:
        return False
    output_path = Path(output_dir)
    progress_path = output_path / "progress.json"
    results_path = output_path / "results.json"
    csv_path = output_path / "results.csv"
    report_path = output_path / "report.html"

    st.markdown("# Prompt Room")
    st.markdown("### Batch in progress")

    # Abort button (when process is still running)
    if proc is not None and proc.poll() is None:
        col_abort, _ = st.columns([1, 3])
        with col_abort:
            if st.button("Abort run", type="secondary", key="abort_run"):
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except (OSError, ProcessLookupError):
                    pass
                try:
                    proc.wait(timeout=5)
                except Exception:
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    except (OSError, ProcessLookupError):
                        proc.kill()
                st.session_state.run_output_dir = None
                st.session_state.run_process = None
                st.rerun()

    # Live-updating progress and results (fragment reruns every 8 sec so rows appear as runs complete)
    @st.fragment(run_every=8)
    def _progress_and_results_block():
        out_dir = st.session_state.get("run_output_dir")
        if not out_dir:
            return
        out_path = Path(out_dir)
        prog_path = out_path / "progress.json"
        res_path = out_path / "results.json"
        csv_path_out = out_path / "results.csv"
        report_path_out = out_path / "report.html"
        if prog_path.exists():
            with open(prog_path, "r") as f:
                progress = json.load(f)
            completed = progress.get("completed", 0)
            total = progress.get("total", 0)
            st.progress(completed / total if total else 0, text=f"Runs: {completed} / {total}")
            if total > 0 and completed >= total:
                st.success("Run complete.")
        else:
            p = st.session_state.get("run_process")
            if p is not None and p.poll() is None:
                st.info("Batch started. Progress will appear after the first run completes.")
            elif p is not None and p.poll() is not None:
                exit_code = p.returncode
                if exit_code != 0:
                    st.error(f"Batch process exited with code {exit_code}.")
                    try:
                        stderr_out = p.stdout.read() if p.stdout else ""
                        if stderr_out:
                            st.code(stderr_out[-3000:] if len(stderr_out) > 3000 else stderr_out)
                    except Exception:
                        pass
                else:
                    st.warning("Batch process finished but wrote no progress. Check logs.")
        if res_path.exists():
            st.markdown("---")
            st.markdown("### Results")
            _results_table_from_dir(out_path, key_prefix="running")

    _progress_and_results_block()
    if proc is not None and proc.poll() is None:
        st.caption("Progress updates every few seconds. You can abort above.")

    if st.button("Clear and run again", key="clear_run"):
        st.session_state.run_output_dir = None
        st.session_state.run_process = None
        st.rerun()
    return True


def main():
    st.set_page_config(page_title="Prompt Room", page_icon="◐", layout="wide", initial_sidebar_state="collapsed")
    apply_custom_css()
    _render_sidebar()

    if "run_output_dir" not in st.session_state:
        st.session_state.run_output_dir = None
    if "run_process" not in st.session_state:
        st.session_state.run_process = None
    if "uploaded_image_urls" not in st.session_state:
        st.session_state.uploaded_image_urls = []  # list of data URLs or paths
    if "show_image_ref_section" not in st.session_state:
        st.session_state.show_image_ref_section = False
    if "show_prompt_ids_section" not in st.session_state:
        st.session_state.show_prompt_ids_section = False

    # When a run is in progress, show only progress view (no form) and return
    if _render_running_view():
        return

    prompts_pool, images_pool, images_pool_brand_books, max_concurrent_default = load_batch_config()
    default_overrides = load_prompts_config()

    # ----- Header -----
    st.markdown("# Prompt Room")
    st.caption("Batch site generation — define requests, optional reference & brand book, then run.")

    # ----- Past runs (persisted on disk; visible in any tab/window) -----
    past_dirs = sorted(BATCH_RESULTS_DIR.glob("batch_*"), key=lambda p: p.name, reverse=True)
    with st.expander("Past batch results", expanded=False):
        if not past_dirs:
            st.caption("No past batches yet. Results are saved here after each run — even if you close the page.")
        else:
            options = ["— Select a batch —"] + [d.name for d in past_dirs]
            chosen = st.selectbox("Choose a batch to view results", options, key="past_run_select")
            if chosen and chosen != "— Select a batch —":
                batch_dir = BATCH_RESULTS_DIR / chosen
                if batch_dir.exists():
                    _results_table_from_dir(batch_dir, key_prefix=chosen)
                else:
                    st.caption("Batch folder not found.")
            else:
                st.caption("Results are saved in batch_results/ so you can reopen the app and view any past run.")

    # ========== 4. Concurrency ==========
    st.markdown("---")
    st.markdown("### 4. Concurrency")
    concurrency = st.number_input("Browsers at once", min_value=1, max_value=4, value=min(2, max_concurrent_default), key="conc")

    # ----- Wix login (collapsed) -----
    with st.expander("Wix login (one-time per machine)"):
        st.caption(f"Log into Wix in each browser profile. You need **{concurrency}** worker{'s' if concurrency > 1 else ''} for your concurrency setting.")
        cols = st.columns(concurrency)
        for w in range(concurrency):
            with cols[w]:
                if st.button(f"Log in — Worker {w}", key=f"setup{w}"):
                    log_path = PROJECT_ROOT / f".worker_{w}_setup.log"
                    log_file = open(log_path, "w")
                    try:
                        subprocess.Popen(
                            [sys.executable, str(PROJECT_ROOT / "batch_preview.py"), "--setup-worker", str(w)],
                            cwd=str(PROJECT_ROOT), stdout=log_file, stderr=subprocess.STDOUT,
                        )
                        st.info("Browser opening — log in to Wix, then close it.")
                    except Exception as e:
                        log_file.close()
                        st.error(f"Failed to launch worker {w}: {e}")
        for w in range(concurrency):
            log_path = PROJECT_ROOT / f".worker_{w}_setup.log"
            if log_path.exists() and log_path.stat().st_size > 0:
                log_text = log_path.read_text().strip()
                if "error" in log_text.lower() or "traceback" in log_text.lower():
                    with st.expander(f"Worker {w} log (has errors)", expanded=True):
                        st.code(log_text[-2000:])

    # ========== 1. Requests ==========
    st.markdown("---")
    st.markdown("### 1. Requests")
    request_mode = st.radio("Mode", ["Random from pool", "Enter manually"], horizontal=True, key="req_mode")
    if request_mode == "Random from pool":
        count = st.number_input("Number of sites", min_value=1, max_value=50, value=4, key="count")
        if prompts_pool:
            st.caption(f"Pool: {len(prompts_pool)} prompts from batch_config.json")
        else:
            st.caption("Add user_prompts to batch_config.json to use the pool.")
    else:
        manual_prompts_text = st.text_area(
            "One request per line",
            placeholder="Create a website for a Coffee Shop...\nCreate a website for a Yoga Studio...",
            height=100,
            key="manual_prompts",
        )
        manual_prompts = [s.strip() for s in (manual_prompts_text or "").splitlines() if s.strip()]
        count = len(manual_prompts)
        if count == 0:
            st.caption("Enter at least one request (one per line).")

    # ========== 2. Reference images ==========
    st.markdown("---")
    col_2_title, col_2_toggle = st.columns([3, 1])
    with col_2_title:
        st.markdown("### 2. Reference images")
    with col_2_toggle:
        show_image_ref = st.toggle("Override", value=st.session_state.show_image_ref_section, key="toggle_image_ref")
    if show_image_ref != st.session_state.show_image_ref_section:
        st.session_state.show_image_ref_section = show_image_ref
        if not show_image_ref:
            st.session_state.uploaded_image_urls = []
            st.session_state.pop("img_ref", None)
            for k in list(st.session_state.keys()):
                if k.startswith("bb_upload_") or k.startswith("bb_select_") or k == "bb_random_one":
                    del st.session_state[k]
        st.rerun()

    effective_image_urls = []
    image_brand_books = []
    image_ref_override = "Off"

    if not show_image_ref:
        st.caption("Using defaults — random image from pool per run, Copier generates brand book.")
    else:
        image_ref_override = st.radio(
            "Source",
            ["Upload", "Random from pool", "Select from pool"],
            horizontal=True,
            key="img_ref",
        )

        if image_ref_override == "Upload":
            uploaded = st.file_uploader("Upload reference images", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True, key="upload")
            if uploaded:
                for f in uploaded:
                    data = f.read()
                    data_url = image_to_data_url(data, f.type or "image/png")
                    if data_url not in st.session_state.uploaded_image_urls:
                        st.session_state.uploaded_image_urls.append(data_url)
            if st.session_state.uploaded_image_urls:
                effective_image_urls = list(st.session_state.uploaded_image_urls)
                st.caption("Brand book for each image (or leave empty to use Copier for that run):")
                brand_book_mode = st.radio("Brand book", ["Manual (enter per image)", "Copier"], horizontal=True, key="bb_upload")
                if brand_book_mode == "Manual (enter per image)":
                    for i, data_url in enumerate(effective_image_urls):
                        row = st.columns([1, 2])
                        with row[0]:
                            try:
                                st.image(data_url, width="stretch")
                            except Exception:
                                st.caption(f"Image {i + 1}")
                        with row[1]:
                            st.text_area(f"Brand book for image {i + 1}", height=80, key=f"bb_upload_{i}", placeholder="Paste brand book or leave empty for Copier")
            if st.button("Clear uploaded images", key="clear_upload"):
                st.session_state.uploaded_image_urls = []
                st.rerun()

        elif image_ref_override == "Random from pool":
            if not images_pool:
                st.caption("Add reference_images.csv with Image URL column.")
            else:
                effective_image_urls = list(images_pool)
                n = len(images_pool)
                cols = 6
                for start in range(0, n, cols):
                    row_cols = st.columns(cols)
                    for i, col in enumerate(row_cols):
                        idx = start + i
                        if idx < n:
                            with col:
                                try:
                                    st.image(images_pool[idx], width="stretch")
                                except Exception:
                                    st.caption(f"[{idx + 1}]")
                st.caption(f"Pool: {n} images (random per run).")
                has_stored = any(images_pool_brand_books.get(u) for u in images_pool)
                bb_options = ["Stored", "Manual (one for all runs)", "Copier"]
                default_bb = 0 if has_stored else 2  # Stored or Copier
                brand_book_mode = st.radio("Brand book", bb_options, index=default_bb, horizontal=True, key="bb_random")
                if brand_book_mode == "Manual (one for all runs)":
                    manual_bb_all = st.text_area("Brand book for all runs", height=100, key="bb_random_one", placeholder="Paste one brand book used for every run")
                    image_brand_books = [manual_bb_all.strip() or None]
                elif brand_book_mode == "Stored":
                    image_brand_books = []  # resolved per task by URL
                else:
                    image_brand_books = [None]

        else:  # Select from pool
            if not images_pool:
                st.caption("Add reference_images.csv with Image URL column.")
            else:
                selected = []
                n = len(images_pool)
                cols = 6
                for start in range(0, n, cols):
                    row_cols = st.columns(cols)
                    for i, col in enumerate(row_cols):
                        idx = start + i
                        if idx < n:
                            with col:
                                try:
                                    st.image(images_pool[idx], width="stretch")
                                    if st.checkbox("Use", key=f"pool_sel_{idx}"):
                                        selected.append(idx)
                                except Exception:
                                    if st.checkbox("Use", key=f"pool_sel_{idx}"):
                                        selected.append(idx)
                effective_image_urls = [images_pool[i] for i in selected] if selected else []
                if effective_image_urls:
                    has_stored_select = any(images_pool_brand_books.get(u) for u in effective_image_urls)
                    bb_options_select = ["Stored", "Manual (enter per image)", "Copier"]
                    default_bb_select = 0 if has_stored_select else 2
                    brand_book_mode = st.radio("Brand book", bb_options_select, index=default_bb_select, horizontal=True, key="bb_select")
                    if brand_book_mode == "Manual (enter per image)":
                        st.caption("Brand book next to each selected image:")
                        for i, url in enumerate(effective_image_urls):
                            row = st.columns([1, 2])
                            with row[0]:
                                try:
                                    st.image(url, width="stretch")
                                except Exception:
                                    st.caption(f"Image {i + 1}")
                            with row[1]:
                                st.text_area(f"Brand book for image {i + 1}", height=80, key=f"bb_select_{i}", placeholder="Paste brand book or leave empty for Copier")
                        image_brand_books = [None] * len(effective_image_urls)  # filled from session in get_effective_brand_books
                    elif brand_book_mode == "Stored":
                        image_brand_books = [images_pool_brand_books.get(u) for u in effective_image_urls]
                        st.caption("Using brand books from reference_images.csv:")
                        for i, url in enumerate(effective_image_urls):
                            bb_preview = (image_brand_books[i] or "")[:200] + ("..." if (image_brand_books[i] or "") and len(image_brand_books[i] or "") > 200 else "")
                            with st.expander(f"Image {i + 1} — stored brand book preview"):
                                st.text(bb_preview or "(none — Copier will run for this image)")
                    else:
                        image_brand_books = [None] * len(effective_image_urls)
                else:
                    st.caption("Select at least one image.")

    # ========== 3. Prompt IDs ==========
    st.markdown("---")
    col_3_title, col_3_toggle = st.columns([3, 1])
    with col_3_title:
        st.markdown("### 3. Prompt IDs")
    with col_3_toggle:
        show_prompt_ids = st.toggle("Override", value=st.session_state.show_prompt_ids_section, key="toggle_prompt_ids")
    if show_prompt_ids != st.session_state.show_prompt_ids_section:
        st.session_state.show_prompt_ids_section = show_prompt_ids
        if not show_prompt_ids:
            for k in ["arch", "typo", "designer", "copier"]:
                st.session_state.pop(k, None)
        st.rerun()

    prompt_overrides = {}
    if not show_prompt_ids:
        st.caption("Using defaults.")
    else:
        st.caption("Leave blank to use defaults — empty values are not sent in the URL.")
        o = default_overrides
        architect_id = st.text_input("Architect", value=o.get("architectPromptId", ""), key="arch", placeholder="Leave blank for default")
        typography_id = st.text_input("Typography", value=o.get("typographyPromptId", ""), key="typo", placeholder="Leave blank for default")
        designer_id = st.text_input("Designer", value=o.get("designerPromptId", ""), key="designer", placeholder="Leave blank for default")
        copier_id = st.text_input("Copier", value=o.get("copierPromptId", ""), key="copier", placeholder="Leave blank for default")
        if architect_id.strip():
            prompt_overrides["architectPromptId"] = architect_id.strip()
        if typography_id.strip():
            prompt_overrides["typographyPromptId"] = typography_id.strip()
        if designer_id.strip():
            prompt_overrides["designerPromptId"] = designer_id.strip()
        if copier_id.strip():
            prompt_overrides["copierPromptId"] = copier_id.strip()

    # ========== Run ==========
    st.markdown("---")
    run_clicked = st.button("Run batch", type="primary", width="stretch", key="run")

    if run_clicked:
        # Resolve tasks: each task has run_id, user_prompt, reference_image_url, optional brand_book
        tasks = []
        # Resolve brand books from session state or stored CSV when building tasks
        def get_effective_brand_books():
            if image_ref_override == "Upload" and effective_image_urls:
                if st.session_state.get("bb_upload") == "Manual (enter per image)":
                    return [st.session_state.get(f"bb_upload_{i}", "").strip() or None for i in range(len(effective_image_urls))]
                return [None] * len(effective_image_urls)
            if image_ref_override == "Select from pool" and effective_image_urls:
                if st.session_state.get("bb_select") == "Manual (enter per image)":
                    return [st.session_state.get(f"bb_select_{i}", "").strip() or None for i in range(len(effective_image_urls))]
                if st.session_state.get("bb_select") == "Stored":
                    return [images_pool_brand_books.get(u) for u in effective_image_urls]
                return [None] * len(effective_image_urls)
            if image_ref_override == "Random from pool":
                if st.session_state.get("bb_random") == "Manual (one for all runs)":
                    one = st.session_state.get("bb_random_one", "").strip() or None
                    return [one] if one else [None]
                if st.session_state.get("bb_random") == "Stored":
                    return None  # resolve per task by ref_url
                return [None]
            return [None]

        use_brand_books_for_tasks = get_effective_brand_books() if show_image_ref else [None]

        if request_mode == "Random from pool":
            if not prompts_pool:
                st.error("Add user_prompts to batch_config.json, or switch to manual requests.")
            else:
                if not show_image_ref:
                    use_urls = []
                    use_brand_books = [None]
                else:
                    use_urls = effective_image_urls or images_pool or []
                    use_brand_books = use_brand_books_for_tasks if use_brand_books_for_tasks is not None else [None]
                if not show_image_ref:
                    for i in range(count):
                        run_id = f"run_{i+1:03d}"
                        user_prompt = random.choice(prompts_pool)
                        tasks.append({"run_id": run_id, "user_prompt": user_prompt, "reference_image_url": "", "brand_book": None})
                elif not use_urls:
                    st.warning("No reference images. Enable image override or add reference_images.csv.")
                else:
                    for i in range(count):
                        run_id = f"run_{i+1:03d}"
                        user_prompt = random.choice(prompts_pool)
                        ref_url = random.choice(use_urls) if use_urls else ""
                        if use_brand_books_for_tasks is None and st.session_state.get("bb_random") == "Stored":
                            bb = images_pool_brand_books.get(ref_url) if ref_url else None
                        else:
                            bb = use_brand_books[0] if (len(use_brand_books) == 1) else (use_brand_books[i % len(use_brand_books)] if use_brand_books else None)
                        tasks.append({"run_id": run_id, "user_prompt": user_prompt, "reference_image_url": ref_url, "brand_book": bb})
        else:
            if not manual_prompts:
                st.error("Enter at least one request (one per line).")
            else:
                if not show_image_ref:
                    for i, user_prompt in enumerate(manual_prompts):
                        run_id = f"run_{i+1:03d}"
                        tasks.append({"run_id": run_id, "user_prompt": user_prompt, "reference_image_url": "", "brand_book": None})
                else:
                    use_urls = effective_image_urls or images_pool or []
                    use_brand_books = use_brand_books_for_tasks if use_brand_books_for_tasks else [None]
                    for i, user_prompt in enumerate(manual_prompts):
                        run_id = f"run_{i+1:03d}"
                        ref_url = use_urls[i % len(use_urls)] if use_urls else ""
                        bb = use_brand_books[i % len(use_brand_books)] if use_brand_books else None
                        tasks.append({"run_id": run_id, "user_prompt": user_prompt, "reference_image_url": ref_url, "brand_book": bb})

        if tasks:
            has_images = any(t.get("reference_image_url") for t in tasks)
            if not has_images and show_image_ref:
                st.error("Add reference images (upload, select, or add pool in batch_config).")
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_dir = BATCH_RESULTS_DIR / f"batch_{timestamp}"
                output_dir.mkdir(parents=True, exist_ok=True)
                run_config = {
                    "output_dir": str(output_dir),
                    "tasks": tasks,
                    "concurrency": concurrency,
                    "prompt_overrides": prompt_overrides,
                }
                config_path = output_dir / "run_config.json"
                config_path.write_text(json.dumps(run_config, indent=2))
                proc = subprocess.Popen(
                    [sys.executable, str(PROJECT_ROOT / "batch_preview.py"), "--config", str(config_path)],
                    cwd=str(PROJECT_ROOT),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                st.session_state.run_output_dir = str(output_dir)
                st.session_state.run_process = proc
                st.rerun()


if __name__ == "__main__":
    main()
