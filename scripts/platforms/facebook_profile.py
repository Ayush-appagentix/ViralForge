"""Personal Facebook profile. Meta's API cannot post to personal profiles, so this is assisted:
the caption is copied to your clipboard and Facebook opens - you paste and click Post."""
from __future__ import annotations

from platforms import _assisted

LABEL = "Facebook personal profile (you click Post)"
MODE = "assisted"
MEDIA = {"image", "video", "text"}


def check(target, media, info) -> list[str]:
    return [] if (target.get("caption") or "").strip() or media else ["Nothing to post."]


def publish(target, media, account, ctx) -> dict:
    steps = ["Facebook is open in the browser (make sure you're on the right profile).",
             "Click \"What's on your mind?\", press Ctrl+V to paste the caption.",
             *(["Click Photo/video and drag in the file from the folder that just opened."] if media else []),
             "Click Post, then tell Claude it's done (paste the post link if you have it)."]
    return _assisted.prepare(ctx, "facebook_profile", target.get("caption", ""), media,
                             "https://www.facebook.com/", steps)
