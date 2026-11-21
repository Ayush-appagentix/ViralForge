"""Shared Meta Graph API helpers for the facebook and instagram plug-ins."""
from __future__ import annotations

from pathlib import Path

import requests

from common import PublishError, env, http

GRAPH = "https://graph.facebook.com"


def version() -> str:
    return env("META_GRAPH_VERSION", "v27.0")


def url(path: str) -> str:
    return f"{GRAPH}/{version()}/{path.lstrip('/')}"


def check(r: requests.Response) -> dict:
    try:
        data = r.json()
    except ValueError:
        if r.ok:
            return {}
        raise PublishError(f"Meta API HTTP {r.status_code}: {r.text[:300]}")
    if not r.ok or (isinstance(data, dict) and "error" in data):
        e = data.get("error", {}) if isinstance(data, dict) else {}
        msg = e.get("error_user_msg") or e.get("message") or r.text[:300]
        raise PublishError(f"Meta API error {r.status_code}: {msg} "
                           f"(code {e.get('code')}, subcode {e.get('error_subcode')})")
    return data


def get(path: str, token: str, **params) -> dict:
    return check(http("GET", url(path), params={**params, "access_token": token}, what=f"Meta GET {path}"))


def post(path: str, token: str, data: dict | None = None, files: dict | None = None,
         timeout: int = 300, final: bool = False) -> dict:
    """final=True for the call that makes the post public (see common.http)."""
    return check(http("POST", url(path), data={**(data or {}), "access_token": token}, files=files,
                      timeout=timeout, final=final, what=f"Meta POST {path}"))


def rupload(upload_url: str, token: str, file: Path, extra_headers: dict | None = None) -> dict:
    """Send a local file to Meta's resumable upload host in one request."""
    headers = {"Authorization": f"OAuth {token}", "offset": "0",
               "file_size": str(file.stat().st_size), **(extra_headers or {})}
    with file.open("rb") as f:
        return check(http("POST", upload_url, headers=headers, data=f, timeout=1800, what="Meta upload"))


def largest_image_url(photo_id: str, token: str) -> str:
    images = get(photo_id, token, fields="images").get("images", [])
    if not images:
        raise PublishError("Facebook did not return an image URL for the uploaded photo.")
    return max(images, key=lambda i: i.get("width", 0))["source"]


def host_image(page_id: str, page_token: str, media: Path) -> str:
    """Instagram fetches images from a public URL. Get one by uploading the photo to the
    Page *unpublished* (nothing appears on the Page). Optional fallback: IG_IMAGE_HOST=litterbox
    uploads to a free temporary host instead (opt-in, set in .env)."""
    if env("IG_IMAGE_HOST", "facebook") == "litterbox":
        with media.open("rb") as f:
            r = http("POST", "https://litterbox.catbox.moe/resources/internals/api.php",
                     data={"reqtype": "fileupload", "time": "1h"},
                     files={"fileToUpload": (media.name, f, "image/jpeg")}, timeout=300, what="temp image host")
        if r.ok and r.text.strip().startswith("https://"):
            return r.text.strip()
        raise PublishError(f"Temporary image host failed: {r.text[:200]}")
    with media.open("rb") as f:
        d = post(f"{page_id}/photos", page_token, data={"published": "false"},
                 files={"source": (media.name, f, "image/jpeg")})
    return largest_image_url(d["id"], page_token)
