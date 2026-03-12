"""
Wix Media Upload Utility
========================
Upload images to Wix Media Manager and get back a public static.wixstatic.com URL.

Uses the Wix Media Manager REST API:
  1. POST generate-upload-url → get a signed upload URL
  2. PUT file bytes to that URL → file lands in the site's Media Manager
  3. Return the public wixstatic.com URL

Config is read from wix_media_config.json (gitignored).
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Optional

import requests

CONFIG_PATH = Path(__file__).parent / "wix_media_config.json"

_config_cache: dict | None = None


def _load_config() -> dict:
    global _config_cache
    if _config_cache is None:
        if not CONFIG_PATH.exists():
            raise FileNotFoundError(
                f"Missing {CONFIG_PATH}. Create it with: "
                '{"wix_api_key": "IST.eyJ...", "wix_site_id": "your-site-id"}'
            )
        with open(CONFIG_PATH, "r") as f:
            _config_cache = json.load(f)
    return _config_cache


def _generate_upload_url(api_key: str, site_id: str, filename: str, mime_type: str, file_path: str | None = None) -> dict:
    url = "https://www.wixapis.com/site-media/v1/files/generate-upload-url"
    headers = {
        "Authorization": api_key,
        "wix-site-id": site_id,
        "Content-Type": "application/json",
    }
    payload = {
        "mimeType": mime_type,
        "fileName": filename,
    }
    if file_path:
        payload["filePath"] = file_path
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _put_file(upload_url: str, data: bytes, mime_type: str) -> dict:
    headers = {"Content-Type": mime_type}
    resp = requests.put(upload_url, headers=headers, data=data, timeout=60)
    resp.raise_for_status()
    return resp.json() if resp.text else {}


def _extract_url(upload_info: dict, upload_result: dict, api_key: str, site_id: str) -> str | None:
    """Try multiple strategies to get the public URL from the upload response."""
    # From upload_info
    file_info = upload_info.get("file", {})
    url = file_info.get("url") or file_info.get("fileUrl")
    file_id = file_info.get("id") or file_info.get("_id")

    # From upload_result
    if not url and upload_result:
        if "file" in upload_result:
            url = upload_result["file"].get("url")
            file_id = file_id or upload_result["file"].get("id")
        elif "url" in upload_result:
            url = upload_result["url"]

    # Poll file info if we have an ID but no URL
    if not url and file_id:
        time.sleep(1)
        try:
            resp = requests.get(
                f"https://www.wixapis.com/site-media/v1/files/{file_id}",
                headers={"Authorization": api_key, "wix-site-id": site_id},
                timeout=15,
            )
            resp.raise_for_status()
            info = resp.json()
            url = info.get("file", {}).get("url") or info.get("file", {}).get("fileUrl")
        except Exception:
            pass

    # Construct from file ID
    if not url and file_id:
        url = f"https://static.wixstatic.com/media/{file_id}"

    # Extract media ID from the upload URL itself
    if not url:
        upload_url = upload_info.get("uploadUrl", "")
        match = re.search(r"/media/([a-f0-9_~]+)", upload_url)
        if match:
            url = f"https://static.wixstatic.com/media/{match.group(1)}"

    return url


def _default_folder_path() -> str:
    """Build a monthly folder path: /prompt-room/2026-03."""
    from datetime import datetime
    now = datetime.now()
    return f"/prompt-room/{now.strftime('%Y-%m')}"


def upload_image(
    file_bytes: bytes,
    filename: str,
    mime_type: str = "image/png",
    folder: str | None = None,
) -> str:
    """Upload image bytes to Wix Media and return the public URL.

    Args:
        file_bytes: Raw image data.
        filename: Original filename (e.g. "photo.png").
        mime_type: MIME type (e.g. "image/png", "image/jpeg", "image/webp").
        folder: Wix Media folder path. Defaults to /prompt-room/YYYY-MM.
            For batch runs pass e.g. /prompt-room/2026-03/batch_20260312_115532.

    Returns:
        Public URL on static.wixstatic.com.

    Raises:
        RuntimeError: If the upload fails or no URL can be determined.
    """
    config = _load_config()
    api_key = config["wix_api_key"]
    site_id = config["wix_site_id"]

    file_path = folder or _default_folder_path()

    upload_info = _generate_upload_url(api_key, site_id, filename, mime_type, file_path)
    upload_url = upload_info.get("uploadUrl")
    if not upload_url:
        raise RuntimeError(f"Wix Media API returned no uploadUrl: {upload_info}")

    upload_result = _put_file(upload_url, file_bytes, mime_type)

    url = _extract_url(upload_info, upload_result, api_key, site_id)
    if not url:
        raise RuntimeError(
            f"Could not determine public URL after upload. "
            f"upload_info={upload_info}, upload_result={upload_result}"
        )
    return url
