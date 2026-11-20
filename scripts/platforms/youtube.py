"""YouTube video upload. Vertical/square videos up to 3 min become Shorts automatically."""
from __future__ import annotations

import json

from common import PublishError, save_account

LABEL = "YouTube (video / Shorts)"
MODE = "api"
MEDIA = {"video"}
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly"]


def check(target, media, info) -> list[str]:
    p = []
    title, desc = target.get("title") or "", target.get("description") or ""
    if info["kind"] != "video":
        p.append("YouTube uploads need a video (use youtube_community for image/text posts).")
    if not title.strip():
        p.append("YouTube needs a title.")
    if len(title) > 100:
        p.append(f"YouTube title is {len(title)} characters; the limit is 100.")
    if len(desc.encode()) > 5000:
        p.append("YouTube description is over 5,000 bytes.")
    if any(c in title + desc for c in "<>"):
        p.append("YouTube rejects '<' and '>' in titles and descriptions.")
    if len(",".join(target.get("tags") or [])) > 450:
        p.append("YouTube tags are too long in total (keep under ~450 characters).")
    if target.get("privacy", "public") not in ("public", "unlisted", "private"):
        p.append("privacy must be public, unlisted or private.")
    return p


def credentials(account: dict):
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = Credentials.from_authorized_user_info(account["token"], SCOPES)
    if not creds.valid:
        if not creds.refresh_token:
            raise PublishError("YouTube login has no refresh token - run ./sa connect youtube again.")
        try:
            creds.refresh(Request())
        except RefreshError as e:
            raise PublishError(f"YouTube login expired or was revoked ({e}). Run ./sa connect youtube again.")
        alias = account.get("_alias")
        if alias:
            saved = {k: v for k, v in account.items() if k != "_alias"}
            saved["token"] = json.loads(creds.to_json())
            save_account("youtube", alias, saved)
    return creds


def publish(target, media, account, ctx) -> dict:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    yt = build("youtube", "v3", credentials=credentials(account), cache_discovery=False)
    body = {
        "snippet": {"title": target["title"][:100], "description": target.get("description", ""),
                    "tags": target.get("tags") or [], "categoryId": str(target.get("category_id", "22"))},
        "status": {"privacyStatus": target.get("privacy", "public"),
                   "selfDeclaredMadeForKids": bool(target.get("made_for_kids", False))},
    }
    request = yt.videos().insert(part="snippet,status", body=body,
                                 media_body=MediaFileUpload(str(media), mimetype="video/mp4",
                                                            chunksize=8 * 1024 * 1024, resumable=True))
    try:
        response = None
        while response is None:
            _, response = request.next_chunk(num_retries=3)
    except HttpError as e:
        raise PublishError(f"YouTube upload failed: {e.reason if hasattr(e, 'reason') else e}")
    vid = response["id"]
    short = ctx.get("orientation") in ("vertical", "square") and ctx.get("duration", 999) <= 180
    return {"id": vid, "url": f"https://youtube.com/shorts/{vid}" if short else f"https://youtu.be/{vid}"}
