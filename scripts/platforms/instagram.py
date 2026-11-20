"""Instagram professional (Business/Creator) account: image -> feed post, video -> Reel.
A personal Instagram account must be switched to Creator (free) in the Instagram app first."""
from __future__ import annotations

import time

from common import PublishError
from platforms import _meta as meta

LABEL = "Instagram (Business/Creator)"
MODE = "api"
MEDIA = {"image", "video"}


def check(target, media, info) -> list[str]:
    p, cap = [], target.get("caption") or ""
    if len(cap) > 2200:
        p.append(f"Caption is {len(cap)} characters; Instagram allows 2,200.")
    if cap.count("#") > 30:
        p.append("Instagram allows at most 30 hashtags.")
    if info["kind"] == "text":
        p.append("Instagram needs an image or a video.")
    elif info["kind"] == "image":
        if media.suffix.lower() not in (".jpg", ".jpeg"):
            p.append("Instagram's API accepts JPEG only - point the draft at the .jpg file.")
        w, h = info.get("width") or 1, info.get("height") or 1
        if not 0.79 <= w / h <= 1.92:
            p.append(f"Image is {w}x{h}; Instagram needs an aspect ratio between 4:5 and 1.91:1.")
        if info.get("size_mb", 0) > 8:
            p.append("Image is over Instagram's 8 MB limit.")
    elif info["kind"] == "video":
        if not 3 <= info.get("duration", 0) <= 900:
            p.append("Instagram Reels must be between 3 s and 15 min.")
        if info.get("size_mb", 0) > 300:
            p.append("Video is over Instagram's 300 MB limit.")
    return p


def wait_until_ready(container_id: str, token: str, timeout: int) -> None:
    deadline = time.time() + timeout
    while True:
        s = meta.get(container_id, token, fields="status_code,status")
        code = s.get("status_code")
        if code in ("FINISHED", "PUBLISHED"):
            return
        if code in ("ERROR", "EXPIRED"):
            raise PublishError(f"Instagram could not process the media: {s.get('status') or code}")
        if time.time() > deadline:
            raise PublishError("Instagram is still processing the media. Run the same publish command again in a few minutes.")
        time.sleep(8)


def publish(target, media, account, ctx) -> dict:
    ig, token = account["ig_user_id"], account["token"]
    caption = target.get("caption", "")
    if ctx["kind"] == "image":
        image_url = ctx.get("public_image_url") or meta.host_image(account["page_id"], account["page_token"], media)
        data = {"image_url": image_url, "caption": caption}
        if ctx.get("alt_text"):
            data["alt_text"] = ctx["alt_text"][:1000]
        container = meta.post(f"{ig}/media", token, data=data)
        wait_until_ready(container["id"], token, timeout=180)
    else:
        data = {"media_type": "REELS", "upload_type": "resumable", "caption": caption}
        if ctx.get("thumbnail_at") is not None:
            data["thumb_offset"] = str(int(float(ctx["thumbnail_at"]) * 1000))
        container = meta.post(f"{ig}/media", token, data=data)
        meta.rupload(container.get("uri") or
                     f"https://rupload.facebook.com/ig-api-upload/{meta.version()}/{container['id']}", token, media)
        wait_until_ready(container["id"], token, timeout=900)
    published = meta.post(f"{ig}/media_publish", token, data={"creation_id": container["id"]})
    try:
        link = meta.get(published["id"], token, fields="permalink").get("permalink")
    except PublishError:
        link = None
    return {"id": published["id"], "url": link or f"https://www.instagram.com/{account.get('username', '')}"}
