"""LinkedIn Company page post. Posting as a Page through the API needs LinkedIn's Community
Management API approval, so this is assisted: the caption goes to your clipboard and the Page's
admin view opens - you click "Create" > "Start a post", paste and post.
Target example: {"platform": "linkedin_page", "account": "145491938", "caption": "..."}
(account = the Page's numeric ID from its admin URL)."""
from __future__ import annotations

from platforms import _assisted

LABEL = "LinkedIn Company page (you click Post)"
MODE = "assisted"
MEDIA = {"image", "video", "text"}


def check(target, media, info) -> list[str]:
    p = []
    if not str(target.get("account") or "").isdigit():
        p.append("Set account to the Page's numeric ID (from linkedin.com/company/<ID>/admin/).")
    if len(target.get("caption") or "") > 3000:
        p.append("Caption is over LinkedIn's 3,000 characters.")
    if info["kind"] == "text" and not (target.get("caption") or "").strip():
        p.append("A text post needs a caption.")
    return p


def publish(target, media, account, ctx) -> dict:
    url = f"https://www.linkedin.com/company/{target['account']}/admin/dashboard/"
    steps = ["Your Company page admin view is open in the browser.",
             "Click 'Create' (or 'Start a post'), make sure it says posting as the Page, press Ctrl+V.",
             *(["Click the image/video icon and drag in the file from the folder that just opened."] if media else []),
             "Click Post, then tell Claude it's done (paste the post link if you have it)."]
    return _assisted.prepare(ctx, f"linkedin_page_{target['account']}", target.get("caption", ""), media, url, steps)
