from __future__ import annotations

"""
Screenshot & Video Utilities
=============================
Standalone full-page screenshot and smooth-scroll video capture using Playwright.
Navigates to each URL, scrolls to trigger lazy-loaded content,
waits for network to settle, and captures a full-page screenshot or video.
"""

import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


DEFAULT_VIEWPORT_WIDTH = 1280
DEFAULT_VIEWPORT_HEIGHT = 800

# Fast scroll used for screenshots — triggers lazy content quickly.
SCROLL_JS = """() => {
    return new Promise((resolve) => {
        const step = 400;
        const delay = 300;
        let scrollTop = 0;
        const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
        if (maxScroll <= 0) { resolve(); return; }
        function scroll() {
            scrollTop = Math.min(scrollTop + step, maxScroll);
            window.scrollTo(0, scrollTop);
            if (scrollTop < maxScroll) {
                setTimeout(scroll, delay);
            } else {
                setTimeout(() => { window.scrollTo(0, 0); resolve(); }, delay);
            }
        }
        scroll();
    });
}"""

EASING_PRESETS: dict[str, float] = {
    "none": 1.0,
    "gentle": 1.5,
    "moderate": 2.0,
    "strong": 3.0,
}


def _smooth_scroll_js(
    duration_ms: int = 12000,
    pause_bottom_ms: int = 2000,
    easing: str | float = "gentle",
) -> str:
    """Return JS that performs a requestAnimationFrame-based smooth scroll
    from top to bottom, then pauses at the bottom.

    *easing*: preset name ("none"/"gentle"/"moderate"/"strong") or a float
    power value. 1.0 = linear (constant speed), higher = more ease in/out.
    """
    if isinstance(easing, str):
        power = EASING_PRESETS.get(easing, EASING_PRESETS["gentle"])
    else:
        power = max(1.0, float(easing))

    return f"""() => {{
    return new Promise((resolve) => {{
        const duration = {duration_ms};
        const pauseBottom = {pause_bottom_ms};
        const power = {power};
        const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
        if (maxScroll <= 0) {{ setTimeout(resolve, 500); return; }}

        window.scrollTo(0, 0);

        function ease(t) {{
            if (power <= 1) return t;
            if (t < 0.5) return Math.pow(2, power - 1) * Math.pow(t, power);
            return 1 - Math.pow(-2 * t + 2, power) / 2;
        }}

        const start = performance.now();
        function step(now) {{
            const t = Math.min((now - start) / duration, 1);
            window.scrollTo(0, maxScroll * ease(t));
            if (t < 1) {{
                requestAnimationFrame(step);
            }} else {{
                setTimeout(resolve, pauseBottom);
            }}
        }}
        requestAnimationFrame(step);
    }});
}}"""


def _sanitize_filename(url: str) -> str:
    """Turn a URL into a safe, readable filename (without extension)."""
    parsed = urlparse(url)
    name = parsed.netloc + parsed.path
    name = name.strip("/").replace("/", "_").replace(".", "_")
    if len(name) > 120:
        name = name[:120]
    return name or "screenshot"


def capture_full_page_screenshot(
    url: str,
    output_path: Path,
    page,
) -> dict:
    """Navigate to *url* in an existing Playwright page, scroll to load lazy
    content, and save a full-page screenshot to *output_path*.

    Returns a result dict: {url, path, success, error}.
    """
    result = {"url": url, "path": str(output_path), "success": False, "error": None}
    try:
        page.goto(url, timeout=30_000, wait_until="domcontentloaded")
        page.wait_for_load_state("load", timeout=15_000)
        try:
            page.wait_for_load_state("networkidle", timeout=10_000)
        except PlaywrightTimeout:
            pass

        _trigger_deferred_loading(page)
        try:
            page.wait_for_load_state("networkidle", timeout=8_000)
        except PlaywrightTimeout:
            pass

        page.evaluate(SCROLL_JS)

        try:
            page.wait_for_load_state("networkidle", timeout=10_000)
        except PlaywrightTimeout:
            pass
        page.wait_for_timeout(1000)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(output_path), full_page=True)
        result["success"] = True
    except Exception as exc:
        result["error"] = str(exc)
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(output_path), full_page=True)
            result["success"] = True
            result["error"] = f"partial: {result['error']}"
        except Exception:
            pass
    return result


def capture_screenshots(
    urls: list[str],
    output_dir: Path,
    viewport_width: int = DEFAULT_VIEWPORT_WIDTH,
    on_progress: Callable[[int, int, dict], None] | None = None,
) -> list[dict]:
    """Capture full-page screenshots for a list of URLs sequentially.

    Uses a single browser instance with a fresh tab per URL.
    *on_progress(index, total, result)* is called after each capture.
    Returns list of result dicts.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": viewport_width, "height": DEFAULT_VIEWPORT_HEIGHT},
        )

        for i, url in enumerate(urls):
            url = url.strip()
            if not url:
                continue
            if not url.startswith(("http://", "https://")):
                url = "https://" + url

            filename = f"{i + 1:03d}_{_sanitize_filename(url)}.png"
            out_path = output_dir / filename

            page = context.new_page()
            try:
                result = capture_full_page_screenshot(url, out_path, page)
            finally:
                page.close()

            results.append(result)
            if on_progress:
                on_progress(i, len(urls), result)

        context.close()
        browser.close()

    return results


# --------------- Video (smooth-scroll recording) ---------------


def _trigger_deferred_loading(page):
    """Simulate user interaction to wake up sites that defer JS until first
    mousemove / touchstart / scroll / keydown (common WP Rocket, NitroPack,
    LiteSpeed Cache optimization pattern).
    """
    page.mouse.move(100, 200)
    page.mouse.move(300, 400)
    page.evaluate("""() => {
        for (const evt of ['mousemove', 'touchstart', 'scroll', 'keydown']) {
            document.dispatchEvent(new Event(evt));
            window.dispatchEvent(new Event(evt));
        }
    }""")


def _wait_for_page_ready(page):
    """Wait for page to be fully loaded including lazy/deferred content."""
    page.wait_for_load_state("load", timeout=15_000)
    try:
        page.wait_for_load_state("networkidle", timeout=10_000)
    except PlaywrightTimeout:
        pass
    _trigger_deferred_loading(page)
    try:
        page.wait_for_load_state("networkidle", timeout=8_000)
    except PlaywrightTimeout:
        pass


PAUSE_BEFORE_SCROLL_SEC = 1.5
PAUSE_AFTER_SCROLL_SEC = 2.0
TRIM_PADDING_SEC = 0.3

# Scroll speed presets (pixels per second).
# Calibrated against an 800px viewport:
#   Slow  ≈ 3s per viewport height — cinematic, good for detail-heavy pages
#   Medium ≈ 1.6s per viewport height — comfortable viewing
#   Fast  ≈ 0.8s per viewport height — quick overview
SCROLL_SPEEDS: dict[str, int] = {
    "slow": 200,
    "medium": 350,
    "fast": 600,
}
MIN_SCROLL_DURATION_MS = 3000
MAX_SCROLL_DURATION_MS = 90000


def _duration_from_speed(scroll_height_px: int, speed: str | int) -> int:
    """Calculate scroll duration (ms) from page height and speed preset or px/s.

    *speed* can be a preset name ("slow"/"medium"/"fast") or an int (px/s).
    Returns clamped duration in milliseconds.
    """
    if isinstance(speed, str):
        px_per_sec = SCROLL_SPEEDS.get(speed, SCROLL_SPEEDS["medium"])
    else:
        px_per_sec = max(50, int(speed))
    duration_ms = int((scroll_height_px / px_per_sec) * 1000)
    return max(MIN_SCROLL_DURATION_MS, min(MAX_SCROLL_DURATION_MS, duration_ms))


def _has_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def _ffmpeg_trim(src: Path, dst: Path, start_sec: float, duration_sec: float):
    """Trim a video with ffmpeg. Re-encodes to ensure accurate seek."""
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-ss", f"{start_sec:.2f}",
            "-i", str(src),
            "-t", f"{duration_sec:.2f}",
            "-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0",
            "-an",
            str(dst),
        ],
        capture_output=True,
        timeout=120,
        check=True,
    )


def capture_scroll_video(
    url: str,
    output_path: Path,
    viewport_width: int = DEFAULT_VIEWPORT_WIDTH,
    scroll_speed: str | int = "medium",
    easing: str | float = "gentle",
    pre_scroll: bool = True,
    on_status: Callable[[str], None] | None = None,
) -> dict:
    """Record a smooth-scroll video of *url* using Playwright's built-in
    video recorder and requestAnimationFrame-based eased scrolling.

    *scroll_speed*: preset name ("slow"/"medium"/"fast") or px/s int.
    *easing*: preset ("none"/"gentle"/"moderate"/"strong") or float power.
    *pre_scroll*: if True, fast-scroll the page before recording to trigger
        lazy-loaded content. Set False to capture entrance animations.
    Duration is calculated automatically from the page's scroll height.

    Returns result dict: {url, path, success, error, scroll_height, scroll_duration_sec}.
    """
    result = {"url": url, "path": str(output_path), "success": False, "error": None,
              "scroll_height": 0, "scroll_duration_sec": 0}
    tmp_dir = tempfile.mkdtemp(prefix="pw_video_")
    has_ffmpeg = _has_ffmpeg()
    _status = on_status or (lambda _: None)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)

            # --- Phase 1: pre-load + measure scroll height ---
            _status("Loading page...")
            warmup_ctx = browser.new_context(
                viewport={"width": viewport_width, "height": DEFAULT_VIEWPORT_HEIGHT},
            )
            warmup_page = warmup_ctx.new_page()
            warmup_page.goto(url, timeout=30_000, wait_until="domcontentloaded")
            _wait_for_page_ready(warmup_page)
            _status("Measuring page height...")
            warmup_page.evaluate(SCROLL_JS)
            _wait_for_page_ready(warmup_page)

            scroll_height = warmup_page.evaluate(
                "() => document.documentElement.scrollHeight"
            )
            result["scroll_height"] = scroll_height

            warmup_page.close()
            warmup_ctx.close()

            scroll_duration_ms = _duration_from_speed(scroll_height, scroll_speed)
            result["scroll_duration_sec"] = round(scroll_duration_ms / 1000, 1)
            _status(f"Page is {scroll_height}px — scroll will take {result['scroll_duration_sec']}s")

            # --- Phase 2: record ---
            _status("Preparing recording...")
            rec_ctx = browser.new_context(
                viewport={"width": viewport_width, "height": DEFAULT_VIEWPORT_HEIGHT},
                record_video_dir=tmp_dir,
                record_video_size={"width": viewport_width, "height": DEFAULT_VIEWPORT_HEIGHT},
            )
            rec_page = rec_ctx.new_page()
            t_page_created = time.monotonic()

            rec_page.goto(url, timeout=30_000, wait_until="load")
            if pre_scroll:
                _status("Pre-scrolling to load content...")
                _trigger_deferred_loading(rec_page)
                rec_page.evaluate(SCROLL_JS)
                _wait_for_page_ready(rec_page)
                rec_page.evaluate("() => window.scrollTo(0, 0)")
                rec_page.wait_for_timeout(300)
            else:
                rec_page.wait_for_timeout(500)

            _status(f"Recording scroll ({result['scroll_duration_sec']}s)...")
            t_scroll_start = time.monotonic()
            scroll_js = _smooth_scroll_js(
                duration_ms=scroll_duration_ms,
                pause_bottom_ms=int(PAUSE_AFTER_SCROLL_SEC * 1000),
                easing=easing,
            )
            rec_page.evaluate(scroll_js)

            _status("Saving video...")
            video_tmp = rec_page.video.path()
            rec_page.close()
            rec_ctx.close()
            browser.close()

        # --- Phase 3: trim ---
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pre_scroll_sec = t_scroll_start - t_page_created
        useful_duration = PAUSE_BEFORE_SCROLL_SEC + (scroll_duration_ms / 1000) + PAUSE_AFTER_SCROLL_SEC
        trim_start = max(0, pre_scroll_sec - PAUSE_BEFORE_SCROLL_SEC - TRIM_PADDING_SEC)

        raw_video = Path(video_tmp)
        if has_ffmpeg and trim_start > 1.0:
            _status("Trimming video...")
            try:
                _ffmpeg_trim(raw_video, output_path, trim_start, useful_duration + TRIM_PADDING_SEC)
            except Exception:
                shutil.move(str(raw_video), str(output_path))
        else:
            shutil.move(str(raw_video), str(output_path))

        result["success"] = True
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return result


def capture_scroll_videos(
    urls: list[str],
    output_dir: Path,
    viewport_width: int = DEFAULT_VIEWPORT_WIDTH,
    scroll_speed: str | int = "medium",
    easing: str | float = "gentle",
    pre_scroll: bool = True,
    on_progress: Callable[[int, int, dict], None] | None = None,
    on_status: Callable[[str], None] | None = None,
) -> list[dict]:
    """Record smooth-scroll videos for a list of URLs sequentially.

    *scroll_speed*: preset name ("slow"/"medium"/"fast") or px/s int.
    *easing*: preset ("none"/"gentle"/"moderate"/"strong") or float power.
    *pre_scroll*: fast-scroll before recording to load lazy content.
    *on_progress(index, total, result)* is called after each URL completes.
    *on_status(message)* is called with phase updates during each capture.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []

    for i, url in enumerate(urls):
        url = url.strip()
        if not url:
            continue
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        filename = f"{i + 1:03d}_{_sanitize_filename(url)}.webm"
        out_path = output_dir / filename

        r = capture_scroll_video(
            url, out_path, viewport_width, scroll_speed, easing, pre_scroll,
            on_status=on_status,
        )
        results.append(r)
        if on_progress:
            on_progress(i, len(urls), r)

    return results
