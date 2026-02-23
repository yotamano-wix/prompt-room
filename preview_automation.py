"""
Wix Preview Automation
======================
Automates the full preview flow:
  1. Run Copier to generate Brand Book (or reuse latest)
  2. Open Wix preview URL with referenceImage pre-filled
  3. Playwright fills the brand book input and clicks "Generate Site"
  4. Waits for site generation (Publish button to become enabled)
  5. Clicks Publish (top-right), then Publish in the popover
  6. Extracts published URL, opens it in a new tab, takes full-page screenshot

Usage:
  source .venv/bin/activate

  # First time: set up your Wix login
  python preview_automation.py --setup

  # Full flow (runs copier, then automates browser)
  python preview_automation.py

  # Skip copier (reuse latest brand book)
  python preview_automation.py --skip-copier

  Note: The full flow takes ~5-10 min. Run from a dedicated terminal (not
  Cursor background) so the process is not killed before generation completes.

  # Custom reference image URL
  python preview_automation.py --skip-copier --image-url "https://example.com/img.png"
"""

import json
import os
import re
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


# ============================================================================
# CONFIGURATION
# ============================================================================

def load_config():
    with open("prompts_config.json", "r") as f:
        config = json.load(f)
    return (
        config["prompts"],
        config.get("default_test_data", {}),
        config.get("wix_preview", {})
    )

PROMPTS, DEFAULT_TEST_DATA, WIX_PREVIEW = load_config()
RESULTS_DIR = Path("test_results")
PROFILE_DIR = Path(".playwright-profile")


# ============================================================================
# HELPERS
# ============================================================================

def build_preview_url(reference_image_url: str = "", site_data_overrides: dict | None = None, prompt_overrides: dict | None = None) -> str:
    """Build the Wix preview URL with siteData, prompt overrides, and reference image.
    If prompt_overrides is provided, use it; otherwise use WIX_PREVIEW.prompt_overrides."""
    site_data = {
        "business_term": DEFAULT_TEST_DATA.get("editor_business_type", ""),
        "site_name": DEFAULT_TEST_DATA.get("editor_business_name", ""),
        "site_description": DEFAULT_TEST_DATA.get("editor_site_description", ""),
        "photo_theme": DEFAULT_TEST_DATA.get("editor_photo_theme", ""),
        "tone_of_voice": "",
        "installed_apps": []
    }
    if site_data_overrides:
        site_data.update(site_data_overrides)

    site_data_json = json.dumps(site_data, separators=(',', ':'))
    encoded_site_data = quote(site_data_json, safe='{},:[]')

    base_url = "https://manage.wix.com/edit-template/from"
    template_id = WIX_PREVIEW.get("origin_template_id", "")
    overrides = prompt_overrides if prompt_overrides is not None else WIX_PREVIEW.get("prompt_overrides", {})

    url = f"{base_url}?originTemplateId={template_id}"
    url += "&aiSiteCreation=true"
    url += f"&siteData={encoded_site_data}"
    url += "&debug=true"

    for key, value in overrides.items():
        if value:
            url += f"&{key}={value}"

    if reference_image_url:
        url += f"&referenceImage={quote(reference_image_url, safe='')}"

    return url


def get_latest_brand_book() -> str | None:
    """Get the brand book text from the latest copier result."""
    if not RESULTS_DIR.exists():
        return None
    files = sorted(RESULTS_DIR.glob("copier_*.json"), reverse=True)
    if not files:
        return None
    with open(files[0], "r") as f:
        result = json.load(f)
    return result.get("output")


def run_copier() -> str:
    """Run the Copier prompt and return the brand book text."""
    sys.path.insert(0, str(Path(__file__).parent))
    from pipeline_test import run_prompt
    result = run_prompt("copier", use_defaults=True)
    if not result or not result.get("output"):
        raise RuntimeError("Copier failed to generate a brand book")
    return result["output"]


# ============================================================================
# BROWSER
# ============================================================================

def clean_profile():
    """Fix profile state so Chrome doesn't show crash/restore dialogs."""
    import shutil

    # Fix preferences to indicate clean exit
    prefs_path = PROFILE_DIR / "Default" / "Preferences"
    if prefs_path.exists():
        with open(prefs_path, "r") as f:
            prefs = json.load(f)
        prefs.setdefault("profile", {})["exit_type"] = "Normal"
        prefs.setdefault("profile", {})["exited_cleanly"] = True
        with open(prefs_path, "w") as f:
            json.dump(prefs, f)

    # Fix Local State too
    local_state_path = PROFILE_DIR / "Local State"
    if local_state_path.exists():
        with open(local_state_path, "r") as f:
            state = json.load(f)
        # Clear any crash recovery flags
        if "profile" in state:
            state["profile"]["metrics_last_started_with_crash"] = False
        if "user_experience_metrics" in state:
            state["user_experience_metrics"]["stability"] = {
                "exited_cleanly": True,
                "launch_count": 1,
            }
        with open(local_state_path, "w") as f:
            json.dump(state, f)

    # Remove stale lock files and crash data
    for lock_file in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
        (PROFILE_DIR / lock_file).unlink(missing_ok=True)

    crashpad = PROFILE_DIR / "Crashpad"
    if crashpad.exists():
        shutil.rmtree(crashpad, ignore_errors=True)


def dismiss_chrome_dialogs():
    """Auto-dismiss macOS 'Something went wrong' Chrome dialogs in background."""
    dismiss_script = '''
    tell application "System Events"
        repeat 15 times
            try
                if exists (button "OK" of window 1 of application process "Chromium")
                    click button "OK" of window 1 of application process "Chromium"
                end if
            end try
            delay 0.5
        end repeat
    end tell
    '''
    subprocess.Popen(
        ["osascript", "-e", dismiss_script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def launch_browser(playwright, profile_dir=None):
    """Launch Chromium with persistent profile (remembers Wix login). profile_dir overrides for batch workers."""
    user_data_dir = str((profile_dir or PROFILE_DIR).resolve())
    if profile_dir is None:
        clean_profile()
        dismiss_chrome_dialogs()
    else:
        Path(user_data_dir).mkdir(parents=True, exist_ok=True)
    return playwright.chromium.launch_persistent_context(
        user_data_dir=user_data_dir,
        headless=False,
        slow_mo=300,
        viewport={"width": 1280, "height": 900},
        args=[
            "--disable-infobars",
            "--disable-session-crashed-bubble",
            "--no-first-run",
            "--no-default-browser-check",
            "--hide-crash-restore-bubble",
            "--noerrdialogs",
            "--disable-features=DestroyProfileOnBrowserClose",
        ],
        ignore_default_args=[
            "--enable-automation",
        ],
    )


def wait_for_aria_page(page, timeout=120000):
    """Wait for the 'Design your site with Aria' page to load. Returns True if found."""
    try:
        page.get_by_text("Design your site with Aria").wait_for(
            state="visible", timeout=timeout
        )
        return True
    except PlaywrightTimeout:
        return False


def keep_alive():
    """Block until user presses Enter or kills the process."""
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        try:
            signal.pause()
        except KeyboardInterrupt:
            pass


# ============================================================================
# COMMANDS
# ============================================================================

def setup_profile():
    """Open browser for one-time Wix login."""
    print("\n🔧 Profile Setup")
    print("=" * 50)
    print("   Log into Wix in the browser that opens.")
    print("   Your session will be saved for future runs.\n")

    with sync_playwright() as p:
        context = launch_browser(p)
        page = context.new_page()
        page.goto("https://www.wix.com/account/sites")
        print("   ⏳ Browser open. Log in, then press Enter here (or close the browser)...")
        keep_alive()
        context.close()

    print("   ✅ Profile saved!")


def automate_preview(brand_book: str, reference_image_url: str, site_data_overrides: dict | None = None, result_dir: Path | None = None, profile_dir_override: Path | None = None, prompt_overrides: dict | None = None):
    """Open preview, fill brand book, click Generate Site, wait for generation, publish, capture.
    When result_dir is set (batch mode), saves screenshot and run_result.json there and closes without keep_alive.
    editor_url (the preview URL) is included in run_result when result_dir is set."""
    if result_dir is None:
        RESULTS_DIR.mkdir(exist_ok=True)
    url = build_preview_url(reference_image_url=reference_image_url, site_data_overrides=site_data_overrides, prompt_overrides=prompt_overrides)
    editor_url = url

    print(f"\n🌐 Launching browser...")

    with sync_playwright() as p:
        context = launch_browser(p, profile_dir=profile_dir_override)
        page = context.new_page()

        # ----- Navigate -----
        print("[1/6] Opening preview URL...")
        page.goto(url, timeout=120000)

        if not wait_for_aria_page(page):
            print("   ❌ Page didn't load. You may need to run --setup first to log in.")
            print("   Keeping browser open so you can log in manually...")
            keep_alive()
            context.close()
            return

        print("   ✅ Page loaded!")
        page.wait_for_timeout(3000)

        # ----- Fill brand book -----
        print("[2/6] Filling Brand Book...")
        # Try multiple selectors for the brand book input
        brand_book_input = None
        selectors = [
            'input[placeholder*="brand book" i]',
            'textarea[placeholder*="brand book" i]',
            'input[placeholder*="Brand Book" i]',
            'textarea[placeholder*="Brand Book" i]',
        ]
        for sel in selectors:
            loc = page.locator(sel).first
            try:
                loc.wait_for(state="visible", timeout=5000)
                brand_book_input = loc
                break
            except PlaywrightTimeout:
                continue

        if not brand_book_input:
            print("   ⚠️  Brand Book input not found. Taking screenshot for debugging...")
            page.screenshot(path="test_results/debug_screenshot.png")
            print("   Saved: test_results/debug_screenshot.png")
            print("   Keeping browser open...")
            keep_alive()
            context.close()
            return

        brand_book_input.click()
        brand_book_input.fill(brand_book)
        print(f"   ✅ Brand Book filled! ({len(brand_book)} chars)")

        # ----- Click Generate Site -----
        print("[3/6] Clicking 'Generate Site'...")
        generate_btn = page.get_by_role("button", name="Generate Site")
        try:
            generate_btn.wait_for(state="visible", timeout=10000)
            generate_btn.click()
            print("   ✅ Generate Site clicked!")
        except PlaywrightTimeout:
            print("   ⚠️  'Generate Site' button not found. Taking screenshot...")
            page.screenshot(path="test_results/debug_screenshot.png")

        # ----- Step 4: Wait for generation (Publish button becomes enabled) -----
        print("\n[4/6] Waiting for site generation (Publish button to enable)...")
        print("   (Generation takes ~4-5 min. Run from a terminal so the process is not killed.)")
        # Let the page settle before we start polling (avoid touching DOM during heavy load)
        page.wait_for_timeout(60 * 1000)  # 1 minute
        poll_interval_sec = 15
        max_wait_sec = 6 * 60
        elapsed = 60  # we already waited 1 min
        while elapsed < max_wait_sec:
            try:
                # Re-query each time to avoid stale element after page updates
                publish_btn = page.get_by_role("button", name="Publish").first
                if publish_btn.is_visible() and publish_btn.is_enabled():
                    print("\n   ✅ Publish button enabled!")
                    break
            except Exception:
                pass
            print(".", end="", flush=True)
            page.wait_for_timeout(poll_interval_sec * 1000)
            elapsed += poll_interval_sec
        else:
            print("\n   ⚠️  Timeout waiting for Publish. Taking debug screenshot...")
            page.screenshot(path="test_results/debug_screenshot.png")
            keep_alive()
            context.close()
            return

        page.wait_for_timeout(2000)

        # ----- Step 5: Click Publish (top-right, then in popover) -----
        print("[5/6] Clicking Publish...")
        publish_btn.click()
        page.wait_for_timeout(800)

        # Publish button inside the popover/modal
        popover_publish = page.locator("role=dialog").get_by_role("button", name="Publish")
        try:
            popover_publish.wait_for(state="visible", timeout=10000)
            popover_publish.click()
            print("   ✅ Published!")
        except PlaywrightTimeout:
            # Fallback: try second Publish button by index
            all_publish = page.get_by_role("button", name="Publish")
            if all_publish.count() >= 2:
                all_publish.nth(1).click()
                print("   ✅ Published (fallback)!")
            else:
                print("   ⚠️  Popover Publish not found. Taking screenshot...")
                page.screenshot(path="test_results/debug_screenshot.png")

        # Wait for "Congrats, your site is published!" modal to appear
        page.wait_for_timeout(1000)
        try:
            page.get_by_text("Congrats", exact=False).wait_for(state="visible", timeout=15000)
            page.wait_for_timeout(500)
        except PlaywrightTimeout:
            pass

        # ----- Step 6: Get published URL, open in new tab, full-page screenshot -----
        print("[6/6] Capturing published site...")
        wix_url = None

        # Strategy 1: Click "View Site" link (opens published site; we then capture from new tab or same page)
        try:
            view_site = page.get_by_role("link", name="View Site")
            view_site.wait_for(state="visible", timeout=5000)
            href = view_site.get_attribute("href")
            if href and "wixsite.com" in href:
                wix_url = href
                print("   Found URL via View Site link")
        except PlaywrightTimeout:
            pass

        # Strategy 2: Any link in the dialog with wixsite.com
        if not wix_url:
            try:
                dialog = page.locator("role=dialog")
                link = dialog.locator('a[href*="wixsite.com"]').first
                link.wait_for(state="visible", timeout=3000)
                wix_url = link.get_attribute("href")
                if wix_url:
                    print("   Found URL via wixsite link")
            except PlaywrightTimeout:
                pass

        # Strategy 3: Extract from dialog text (e.g. "yotamm9.wixsite.com/my-site-321" without protocol)
        if not wix_url:
            try:
                dialog = page.locator("role=dialog")
                text = dialog.inner_text()
                # Match https://... or bare host like something.wixsite.com/path
                match = re.search(r"(https?://[^\s]+wixsite\.com[^\s]*)|([a-z0-9-]+\.wixsite\.com/[^\s]*)", text, re.IGNORECASE)
                if match:
                    wix_url = (match.group(1) or match.group(2) or "").strip()
                    if wix_url and not wix_url.startswith("http"):
                        wix_url = "https://" + wix_url
                    if wix_url:
                        print("   Found URL via dialog text")
            except Exception:
                pass

        screenshot_path = None
        if not wix_url:
            print("   ⚠️  Could not extract published URL. Taking editor screenshot...")
            screenshot_path = (result_dir / "preview_screenshot.png") if result_dir else Path("test_results/preview_screenshot.png")
            page.screenshot(path=str(screenshot_path))
        else:
            print(f"   URL: {wix_url}")
            new_page = context.new_page()
            try:
                new_page.goto(wix_url, timeout=30000, wait_until="domcontentloaded")
                new_page.wait_for_load_state("load", timeout=15000)
                new_page.wait_for_timeout(2000)

                print("   Scrolling page to load all content...")
                new_page.evaluate("""() => {
                    return new Promise((resolve) => {
                        const step = 400;
                        const delay = 300;
                        let scrollTop = 0;
                        const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
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
                }""")
                new_page.wait_for_timeout(1500)

                if result_dir:
                    screenshot_path = result_dir / "published_site.png"
                else:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    screenshot_path = Path(f"test_results/published_site_{timestamp}.png")
                new_page.screenshot(path=str(screenshot_path), full_page=True)
                print(f"   📸 Full-page screenshot: {screenshot_path}")
            except PlaywrightTimeout:
                if result_dir:
                    screenshot_path = result_dir / "published_site.png"
                else:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    screenshot_path = Path(f"test_results/published_site_{timestamp}.png")
                new_page.screenshot(path=str(screenshot_path), full_page=True)
                print(f"   📸 Full-page screenshot: {screenshot_path}")
            finally:
                new_page.close()

        if result_dir:
            run_result = {
                "publish_url": wix_url,
                "editor_url": editor_url,
                "screenshot_path": str(screenshot_path) if screenshot_path else None,
            }
            result_dir.mkdir(parents=True, exist_ok=True)
            (result_dir / "run_result.json").write_text(json.dumps(run_result, indent=2))
            print("\n✅ Batch run complete.")
            context.close()
        else:
            print("\n" + "=" * 50)
            print("✅ Automation complete! Browser stays open.")
            print("   Press Enter to close.")
            keep_alive()
            context.close()


def run_single_batch_flow(run_id: str, user_prompt: str, reference_image_url: str, worker_id: int, batch_results_dir: Path, prompt_overrides: dict | None = None, manual_brand_book: str | None = None, copier_prompt_id: str | None = None) -> dict:
    """Run one full flow for batch: copier (or manual brand book) -> automate_preview. Uses a separate profile per worker.
    Returns run metadata for the report.
    If manual_brand_book is provided, skip Copier and use that text. Otherwise run Copier with reference_image_url.
    copier_prompt_id: optional prompt ID override for Copier (when not using manual brand book)."""
    run_dir = batch_results_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    if manual_brand_book and manual_brand_book.strip():
        brand_book = manual_brand_book.strip()
        copier_path = None
    else:
        from pipeline_test import run_prompt
        extra = {"reference_image_url": reference_image_url}
        if copier_prompt_id:
            # pipeline_test uses prompt IDs from prompts_config; we'd need to temporarily override.
            # For now we don't change copier ID in pipeline_test; config is the source of truth.
            pass
        run_prompt("copier", use_defaults=True, extra_params=extra, output_dir=run_dir)
        copier_path = run_dir / "copier_output.json"
        with open(copier_path, "r") as f:
            copier_data = json.load(f)
        brand_book = copier_data.get("output", "")

    if not brand_book:
        return {"run_id": run_id, "error": "Copier produced no output", "run_dir": str(run_dir), "editor_url": None, "publish_url": None, "screenshot_path": None, "brand_book_preview": None}

    # Site data overrides from user prompt
    site_data_overrides = {
        "site_description": user_prompt,
        "business_term": "",
    }
    profile_dir = Path(f".playwright-profile-batch-{worker_id}")
    automate_preview(
        brand_book,
        reference_image_url,
        site_data_overrides=site_data_overrides,
        result_dir=run_dir,
        profile_dir_override=profile_dir,
        prompt_overrides=prompt_overrides,
    )

    run_result_path = run_dir / "run_result.json"
    if run_result_path.exists():
        with open(run_result_path, "r") as f:
            run_result = json.load(f)
    else:
        run_result = {}
    return {
        "run_id": run_id,
        "user_prompt": user_prompt,
        "reference_image_url": reference_image_url,
        "copier_output_path": str(copier_path) if copier_path else None,
        "brand_book_preview": brand_book[:500] + "..." if len(brand_book) > 500 else brand_book,
        "publish_url": run_result.get("publish_url"),
        "editor_url": run_result.get("editor_url"),
        "screenshot_path": run_result.get("screenshot_path"),
        "run_dir": str(run_dir),
    }


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Wix Preview Automation")
    parser.add_argument("--setup", action="store_true",
                        help="Open browser for one-time Wix login")
    parser.add_argument("--skip-copier", action="store_true",
                        help="Reuse latest brand book from test_results/")
    parser.add_argument("--image-url", type=str, default=None,
                        help="Custom reference image URL")
    args = parser.parse_args()

    if args.setup:
        setup_profile()
        return

    print("\n🤖 Wix Preview Automation")
    print("=" * 50)

    # Get brand book
    if args.skip_copier:
        print("\n[Copier] Using latest brand book...")
        brand_book = get_latest_brand_book()
        if not brand_book:
            print("❌ No brand book found. Run without --skip-copier first.")
            sys.exit(1)
    else:
        print("\n[Copier] Generating Brand Book...")
        brand_book = run_copier()
    print(f"   ✅ Brand Book ready ({len(brand_book)} chars)")

    # Get reference image URL
    reference_image_url = args.image_url or DEFAULT_TEST_DATA.get("reference_image_url", "")
    print(f"   🖼️  Image: {reference_image_url[:60]}...")

    # Run automation
    automate_preview(brand_book, reference_image_url)


if __name__ == "__main__":
    main()
