from __future__ import annotations

import importlib
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Force-reload to avoid stale module cache during Streamlit hot-reload
import shared_ui  # noqa: E402
import screenshot_utils  # noqa: E402
importlib.reload(shared_ui)
importlib.reload(screenshot_utils)

from shared_ui import apply_custom_css, render_sidebar  # noqa: E402
from screenshot_utils import capture_screenshots, capture_scroll_videos  # noqa: E402

RESULTS_ROOT = PROJECT_ROOT / "screenshot_results"


def _open_folder(path: str | Path):
    """Open a folder in the OS file manager."""
    p = str(path)
    system = platform.system()
    if system == "Darwin":
        subprocess.Popen(["open", p])
    elif system == "Windows":
        subprocess.Popen(["explorer", p])
    else:
        subprocess.Popen(["xdg-open", p])


def _render_past_results():
    """Show previous screenshot/video batches in an expander."""
    if not RESULTS_ROOT.exists():
        return
    batches = sorted(
        [d for d in RESULTS_ROOT.iterdir() if d.is_dir()],
        key=lambda d: d.name,
        reverse=True,
    )
    if not batches:
        return

    with st.expander(f"Past batches ({len(batches)})", expanded=False):
        selected = st.selectbox(
            "Select batch",
            batches,
            format_func=lambda d: d.name,
            key="past_screenshot_batch",
        )
        if selected:
            col_info, col_open = st.columns([4, 1])
            images = sorted(selected.glob("*.png"))
            videos = sorted(selected.glob("*.webm"))
            gifs = sorted(selected.glob("*.gif"))
            with col_info:
                if not images and not videos and not gifs:
                    st.caption("No results in this batch.")
                else:
                    parts = []
                    if images:
                        parts.append(f"{len(images)} images")
                    if videos:
                        parts.append(f"{len(videos)} videos")
                    if gifs:
                        parts.append(f"{len(gifs)} GIFs")
                    st.caption(f"{', '.join(parts)} in `{selected.name}/`")
            with col_open:
                if st.button("Open folder", key="open_folder_past"):
                    _open_folder(selected)
            if images or videos or gifs:
                _render_image_grid(images)
                _render_video_list(videos)
                if gifs:
                    st.markdown("**GIFs**")
                    _render_image_grid(gifs)


def _render_image_grid(paths: list[Path]):
    """Show images as a thumbnail grid."""
    cols_per_row = 3
    for row_start in range(0, len(paths), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            idx = row_start + j
            if idx < len(paths):
                with col:
                    st.image(str(paths[idx]), use_container_width=True)
                    st.caption(paths[idx].name)


def _render_video_list(paths: list[Path]):
    """Show videos inline."""
    for p in paths:
        st.caption(p.name)
        st.video(str(p))


def _render_results(results: list[dict], mode: str):
    """Show capture results (images or videos) with status."""
    succeeded = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    label = "screenshots" if mode == "image" else "videos"

    if succeeded:
        st.success(f"{len(succeeded)} of {len(results)} {label} captured successfully.")
    if failed:
        st.error(f"{len(failed)} failed:")
        for r in failed:
            st.caption(f"  {r['url']} — {r['error']}")

    if mode == "image":
        ok_paths = [Path(r["path"]) for r in succeeded if Path(r["path"]).exists()]
        _render_image_grid(ok_paths)
    else:
        for r in succeeded:
            p = Path(r["path"])
            if p.exists():
                url_label = r["url"]
                if len(url_label) > 80:
                    url_label = url_label[:77] + "..."
                info_parts = [url_label]
                if r.get("scroll_height"):
                    info_parts.append(f"{r['scroll_height']}px")
                if r.get("scroll_duration_sec"):
                    info_parts.append(f"{r['scroll_duration_sec']}s scroll")
                gif_path = Path(r["gif_path"]) if r.get("gif_path") else None
                if gif_path and gif_path.exists():
                    gif_size_mb = gif_path.stat().st_size / (1024 * 1024)
                    info_parts.append(f"GIF {gif_size_mb:.1f} MB")
                st.caption(" — ".join(info_parts))
                st.video(str(p))
                if gif_path and gif_path.exists():
                    with st.expander("Preview GIF"):
                        st.image(str(gif_path))


def main():
    st.set_page_config(page_title="Screenshots — Prompt Room", page_icon="◐", layout="wide", initial_sidebar_state="collapsed")
    apply_custom_css()
    render_sidebar()

    st.markdown("# Screenshots & Videos")
    st.caption("Capture full-page scrolling screenshots or smooth-scroll videos for a list of URLs.")

    _render_past_results()

    st.markdown("## URLs")
    urls_text = st.text_area(
        "One URL per line",
        height=180,
        placeholder="https://example.com\nhttps://another-site.com/page",
        key="screenshot_urls",
    )

    st.markdown("## Options")
    col1, col2, col3 = st.columns(3)
    with col1:
        capture_mode = st.radio("Capture mode", ["Image (screenshot)", "Video (scroll recording)"], key="capture_mode")
    with col2:
        viewport_width = st.number_input("Viewport width (px)", min_value=320, max_value=3840, value=1280, step=10, key="vp_width")
    with col3:
        if "Video" in capture_mode:
            scroll_speed = st.radio(
                "Scroll speed",
                ["Slow", "Medium", "Fast"],
                index=1,
                key="scroll_speed",
                help="Slow ~200 px/s, Medium ~350 px/s, Fast ~600 px/s. Duration adapts to each page's length.",
            )
        else:
            scroll_speed = "Medium"

    is_video = "Video" in capture_mode

    easing = "gentle"
    pre_scroll = True
    scroll_style = "cinematic"
    export_gif = False
    if is_video:
        with st.expander("Advanced video settings"):
            scroll_style = st.radio(
                "Scroll style",
                ["Cinematic", "Human-like"],
                index=0,
                key="scroll_style",
                help=(
                    "Cinematic: one continuous smooth sweep. "
                    "Human-like: natural trackpad scrolling with short momentum bursts."
                ),
            )
            scroll_style = "human" if "Human" in scroll_style else "cinematic"
            if scroll_style == "cinematic":
                easing = st.select_slider(
                    "Scroll easing (acceleration / deceleration)",
                    options=["None", "Gentle", "Moderate", "Strong"],
                    value="Gentle",
                    key="scroll_easing",
                    help=(
                        "Controls how much the scroll accelerates at the start and decelerates at the end. "
                        "'None' = constant speed (linear), 'Strong' = pronounced ease-in and ease-out."
                    ),
                )
                easing = easing.lower()
            pre_scroll = st.checkbox(
                "Pre-scroll to load all content",
                value=True,
                key="pre_scroll",
                help=(
                    "Fast-scrolls the page before recording to trigger lazy-loaded content. "
                    "Turn off to capture one-time entrance animations."
                ),
            )
            export_gif = st.checkbox(
                "Also export as GIF",
                value=False,
                key="export_gif",
                help="Convert each video to an animated GIF (requires FFmpeg).",
            )

    urls = [u.strip() for u in urls_text.strip().splitlines() if u.strip()] if urls_text else []

    st.markdown("---")

    btn_label = "Capture videos" if is_video else "Capture screenshots"
    if st.button(btn_label, type="primary", disabled=len(urls) == 0):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = "videos" if is_video else "screenshots"
        output_dir = RESULTS_ROOT / f"{suffix}_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)

        progress_bar = st.progress(0, text=f"Starting... 0 / {len(urls)}")
        status_area = st.empty()
        results_container = st.container()

        current_idx = [0]
        all_results: list[dict] = []

        def on_status(msg: str):
            url_label = urls[current_idx[0]] if current_idx[0] < len(urls) else ""
            if len(url_label) > 50:
                url_label = url_label[:47] + "..."
            status_area.caption(f"[{current_idx[0] + 1}/{len(urls)}] {url_label} — {msg}")

        def on_progress(i: int, total: int, result: dict):
            current_idx[0] = i + 1
            frac = (i + 1) / total
            if result["success"] and result.get("scroll_duration_sec"):
                status = f"OK — {result['scroll_height']}px, {result['scroll_duration_sec']}s scroll"
            elif result["success"]:
                status = "OK"
            else:
                status = f"FAILED: {result['error']}"
            progress_bar.progress(frac, text=f"{i + 1} / {total} — {status}")
            all_results.append(result)

            with results_container:
                if result["success"]:
                    p = Path(result["path"])
                    if p.exists():
                        url_label = result["url"]
                        if len(url_label) > 80:
                            url_label = url_label[:77] + "..."
                        info_parts = [url_label]
                        if is_video:
                            if result.get("scroll_height"):
                                info_parts.append(f"{result['scroll_height']}px")
                            if result.get("scroll_duration_sec"):
                                info_parts.append(f"{result['scroll_duration_sec']}s scroll")
                            gif_path = Path(result["gif_path"]) if result.get("gif_path") else None
                            if gif_path and gif_path.exists():
                                gif_size_mb = gif_path.stat().st_size / (1024 * 1024)
                                info_parts.append(f"GIF {gif_size_mb:.1f} MB")
                            st.caption(" — ".join(info_parts))
                            st.video(str(p))
                            if gif_path and gif_path.exists():
                                with st.expander("Preview GIF"):
                                    st.image(str(gif_path))
                        else:
                            st.caption(" — ".join(info_parts))
                            st.image(str(p), width="stretch")
                else:
                    with results_container:
                        st.caption(f"Failed: {result['url']} — {result['error']}")

        if is_video:
            capture_scroll_videos(
                urls,
                output_dir,
                viewport_width=viewport_width,
                scroll_speed=scroll_speed.lower(),
                easing=easing,
                pre_scroll=pre_scroll,
                scroll_style=scroll_style,
                export_gif=export_gif,
                on_progress=on_progress,
                on_status=on_status,
            )
        else:
            capture_screenshots(
                urls,
                output_dir,
                viewport_width=viewport_width,
                on_progress=on_progress,
            )

        status_area.empty()
        progress_bar.progress(1.0, text=f"Done — {len(all_results)} {suffix}")
        st.session_state["last_screenshot_results"] = all_results
        st.session_state["last_screenshot_dir"] = str(output_dir)
        st.session_state["last_capture_mode"] = "video" if is_video else "image"

        with results_container:
            succeeded = [r for r in all_results if r["success"]]
            failed = [r for r in all_results if not r["success"]]
            if succeeded:
                st.success(f"{len(succeeded)} of {len(all_results)} {suffix} captured successfully.")
            if failed:
                st.error(f"{len(failed)} failed.")
            col_path, col_btn = st.columns([4, 1])
            with col_path:
                st.markdown(f"Saved to `{output_dir.relative_to(PROJECT_ROOT)}/`")
            with col_btn:
                if st.button("Open folder", key="open_folder_new"):
                    _open_folder(output_dir)

    elif "last_screenshot_results" in st.session_state and st.session_state["last_screenshot_results"]:
        out = st.session_state.get("last_screenshot_dir", "")
        mode = st.session_state.get("last_capture_mode", "image")
        if out:
            col_path, col_btn = st.columns([4, 1])
            with col_path:
                st.caption(f"Last batch: `{Path(out).relative_to(PROJECT_ROOT)}/`")
            with col_btn:
                if st.button("Open folder", key="open_folder_last"):
                    _open_folder(out)
        _render_results(st.session_state["last_screenshot_results"], mode)


if __name__ == "__main__":
    main()
