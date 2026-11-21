"""Facebook Page: image -> photo post, video -> Reel (3-90 s), text -> feed post.
Meta's API cannot post to personal profiles; use facebook_profile (assisted) for that."""
from __future__ import annotations

from common import PublishError
from platforms import _meta as meta

LABEL = "Facebook Page"
MODE = "api"
MEDIA = {"image", "video", "text"}


def check(target, media, info) -> list[str]:
    p, cap = [], target.get("caption") or ""
    if len(cap) > 63000:
        p.append("Caption is longer than Facebook allows.")
    if info["kind"] == "text" and not cap.strip():
        p.append("A text post needs a caption.")
    if info["kind"] == "image" and info.get("size_mb", 0) > 10:
        p.append("Image is over Facebook's 10 MB limit.")
    if info["kind"] == "video" and not 3 <= info.get("duration", 0) <= 90:
        p.append(f"Facebook Reels must be 3-90 s long (this video is {info.get('duration', 0):.0f} s).")
    return p


def permalink(obj_id: str, token: str) -> str:
    try:
        return meta.get(obj_id, token, fields="permalink_url").get("permalink_url") or f"https://www.facebook.com/{obj_id}"
    except PublishError:
        return f"https://www.facebook.com/{obj_id}"


def publish(target, media, account, ctx) -> dict:
    page, token = account["page_id"], account["page_token"]
    caption = target.get("caption", "")
    if ctx["kind"] == "image":
        with media.open("rb") as f:
            d = meta.post(f"{page}/photos", token, data={"caption": caption},
                          files={"source": (media.name, f, "image/jpeg")}, final=True)
        try:
            ctx["public_image_url"] = meta.largest_image_url(d["id"], token)
        except PublishError:
            pass
        post_id = d.get("post_id") or d["id"]
        return {"id": post_id, "url": permalink(post_id, token)}
    if ctx["kind"] == "video":
        start = meta.post(f"{page}/video_reels", token, data={"upload_phase": "start"})
        vid = start["video_id"]
        meta.rupload(start.get("upload_url") or f"https://rupload.facebook.com/video-upload/{meta.version()}/{vid}",
                     token, media, {"Content-Type": "application/octet-stream"})
        meta.post(f"{page}/video_reels", token, data={"video_id": vid, "upload_phase": "finish",
                                                      "video_state": "PUBLISHED", "description": caption}, final=True)
        return {"id": vid, "url": f"https://www.facebook.com/reel/{vid}"}
    d = meta.post(f"{page}/feed", token, data={"message": caption}, final=True)
    return {"id": d["id"], "url": permalink(d["id"], token)}
