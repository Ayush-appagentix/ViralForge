"""YouTube community post (text or image). YouTube has no API for these, so this is assisted:
the caption is copied to your clipboard and your channel's Posts page opens - you paste and click Post."""
from __future__ import annotations

from platforms import _assisted

LABEL = "YouTube community post (you click Post)"
MODE = "assisted"
MEDIA = {"image", "text"}
ACCOUNTS_FROM = "youtube"


def check(target, media, info) -> list[str]:
    p = []
    if info["kind"] == "video":
        p.append("Community posts take text or an image; upload videos with the youtube platform.")
    if not (target.get("caption") or "").strip():
        p.append("A community post needs text.")
    return p


def publish(target, media, account, ctx) -> dict:
    channel = account.get("channel_id")
    url = f"https://www.youtube.com/channel/{channel}/posts" if channel else "https://studio.youtube.com"
    steps = ["Your channel's Posts tab is open in the browser (signed in as the channel owner).",
             "Click the post box, press Ctrl+V to paste the caption.",
             *(["Click 'Image', and drag in the image from the folder that just opened."] if media else []),
             "Click Post, then tell Claude it's done (paste the post link if you have it)."]
    return _assisted.prepare(ctx, "youtube_community", target.get("caption", ""), media, url, steps)
