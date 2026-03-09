from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared_ui import apply_custom_css, render_sidebar
from screenshot_utils import capture_screenshots, capture_scroll_videos

RESULTS_ROOT = PROJECT_ROOT / "screenshot_results"


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
            images = sorted(selected.glob("*.png"))
            videos = sorted(selected.glob("*.webm"))
            if not images and not videos:
                st.caption("No results in this batch.")
            else:
                st.caption(f"{len(images)} images, {len(videos)} videos in `{selected.name}/`")
                _render_image_grid(images)
                _render_video_list(videos)


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
                st.caption(" — ".join(info_parts))
                st.video(str(p))


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
    if is_video:
        with st.expander("Advanced video settings"):
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

        current_idx = [0]

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

        if is_video:
            final_results = capture_scroll_videos(
                urls,
                output_dir,
                viewport_width=viewport_width,
                scroll_speed=scroll_speed.lower(),
                easing=easing,
                pre_scroll=pre_scroll,
                on_progress=on_progress,
                on_status=on_status,
            )
        else:
            final_results = capture_screenshots(
                urls,
                output_dir,
                viewport_width=viewport_width,
                on_progress=on_progress,
            )

        progress_bar.progress(1.0, text=f"Done — {len(final_results)} {suffix}")
        st.session_state["last_screenshot_results"] = final_results
        st.session_state["last_screenshot_dir"] = str(output_dir)
        st.session_state["last_capture_mode"] = "video" if is_video else "image"

        st.markdown(f"Saved to `{output_dir.relative_to(PROJECT_ROOT)}/`")
        _render_results(final_results, "video" if is_video else "image")

    elif "last_screenshot_results" in st.session_state and st.session_state["last_screenshot_results"]:
        out = st.session_state.get("last_screenshot_dir", "")
        mode = st.session_state.get("last_capture_mode", "image")
        if out:
            st.caption(f"Last batch: `{Path(out).relative_to(PROJECT_ROOT)}/`")
        _render_results(st.session_state["last_screenshot_results"], mode)


if __name__ == "__main__":
    main()
