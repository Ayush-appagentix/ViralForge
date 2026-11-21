"""LinkedIn personal profile (Share on LinkedIn): text, image or video posts.
Company pages need LinkedIn's Community Management API approval and are not covered here."""
from __future__ import annotations

import re
import time
from urllib.parse import quote

import requests

from common import PublishError, env, http

LABEL = "LinkedIn (personal profile)"
MODE = "api"
MEDIA = {"image", "video", "text"}
API = "https://api.linkedin.com/rest"
RESERVED = set("\\|{}@[]()<>#*_~")


def escape(text: str) -> str:
    """LinkedIn 'little text' format: escape reserved characters, keep #hashtags as hashtags and
    mentions written as @[Name](urn:li:organization:123) / @[Name](urn:li:person:abc) as real tags."""
    out = []
    for part in re.split(r"(@\[[^\]]+\]\(urn:li:(?:organization|person):[\w-]+\)|#\w+)", text):
        m = re.fullmatch(r"@\[([^\]]+)\]\((urn:li:(?:organization|person):[\w-]+)\)", part)
        if m:
            name = "".join("\\" + c if c in RESERVED else c for c in m.group(1))
            out.append(f"@[{name}]({m.group(2)})")
        elif re.fullmatch(r"#\w+", part):
            out.append("{hashtag|\\#|" + part[1:] + "}")
        else:
            out.append("".join("\\" + c if c in RESERVED else c for c in part))
    return "".join(out)


def check(target, media, info) -> list[str]:
    p, cap = [], target.get("caption") or ""
    if len(cap) > 3000:
        p.append(f"Caption is {len(cap)} characters; LinkedIn allows 3,000.")
    if info["kind"] == "text" and not cap.strip():
        p.append("A text post needs a caption.")
    if info["kind"] == "video":
        if not 3 <= info.get("duration", 0) <= 1800:
            p.append("LinkedIn videos must be between 3 s and 30 min.")
        if info.get("size_mb", 0) > 500:
            p.append("Video is over 500 MB.")
    return p


def headers(token: str, json_body: bool = True) -> dict:
    h = {"Authorization": f"Bearer {token}", "LinkedIn-Version": env("LINKEDIN_VERSION", "202611"),
         "X-Restli-Protocol-Version": "2.0.0"}
    if json_body:
        h["Content-Type"] = "application/json"
    return h


def ok(r: requests.Response) -> requests.Response:
    if r.status_code >= 400:
        try:
            msg = r.json().get("message") or r.text[:300]
        except ValueError:
            msg = r.text[:300]
        raise PublishError(f"LinkedIn error {r.status_code}: {msg}")
    return r


def upload_image(path, owner: str, token: str) -> str:
    r = ok(http("POST", f"{API}/images?action=initializeUpload", headers=headers(token),
                json={"initializeUploadRequest": {"owner": owner}}, what="LinkedIn image init")).json()["value"]
    with path.open("rb") as f:
        ok(http("PUT", r["uploadUrl"], headers={"Authorization": f"Bearer {token}"}, data=f, timeout=600,
                what="LinkedIn image upload"))
    return r["image"]


def upload_video(path, owner: str, token: str) -> str:
    size = path.stat().st_size
    v = ok(http("POST", f"{API}/videos?action=initializeUpload", headers=headers(token), what="LinkedIn video init",
                         json={"initializeUploadRequest": {"owner": owner, "fileSizeBytes": size,
                                                           "uploadCaptions": False,
                                                           "uploadThumbnail": False}})).json()["value"]
    etags = []
    with path.open("rb") as f:
        for part in v["uploadInstructions"]:
            f.seek(part["firstByte"])
            chunk = f.read(part["lastByte"] - part["firstByte"] + 1)
            r = ok(http("PUT", part["uploadUrl"], data=chunk, timeout=600, what="LinkedIn video upload",
                        headers={"Content-Type": "application/octet-stream"}))
            etags.append(r.headers.get("etag") or r.headers.get("ETag"))
    ok(http("POST", f"{API}/videos?action=finalizeUpload", headers=headers(token), what="LinkedIn video finalize",
                     json={"finalizeUploadRequest": {"video": v["video"], "uploadToken": v.get("uploadToken") or "",
                                                     "uploadedPartIds": etags}}))
    deadline = time.time() + 600
    while time.time() < deadline:  # wait until LinkedIn finishes processing
        r = http("GET", f"{API}/videos/{quote(v['video'], safe='')}", headers=headers(token, False),
                 what="LinkedIn video status")
        if r.status_code == 200 and r.json().get("status") == "AVAILABLE":
            break
        if r.status_code == 200 and r.json().get("status") == "PROCESSING_FAILED":
            raise PublishError("LinkedIn could not process the video.")
        if r.status_code != 200:  # status not readable with this login: give it time, the post step retries
            time.sleep(30)
            break
        time.sleep(10)
    return v["video"]


def publish(target, media, account, ctx) -> dict:
    if account.get("expires_at") and time.time() > account["expires_at"]:
        raise PublishError("LinkedIn login expired (they last 60 days). Run ./sa connect linkedin again.")
    token, author = account["access_token"], account["person_urn"]
    body = {"author": author, "commentary": escape(target.get("caption", "")), "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [],
                             "thirdPartyDistributionChannels": []},
            "lifecycleState": "PUBLISHED", "isReshareDisabledByAuthor": False}
    if ctx["kind"] == "image":
        body["content"] = {"media": {"id": upload_image(media, author, token),
                                     "altText": (ctx.get("alt_text") or "")[:4000]}}
    elif ctx["kind"] == "video":
        body["content"] = {"media": {"id": upload_video(media, author, token),
                                     "title": target.get("title") or ctx.get("title", "")}}
    for attempt in range(6):
        r = http("POST", f"{API}/posts", headers=headers(token), json=body, final=True, what="LinkedIn create post")
        if r.status_code < 400 or ctx["kind"] != "video" or attempt == 5:
            break
        time.sleep(15)  # video may still be processing
    ok(r)
    post_id = r.headers.get("x-restli-id") or r.headers.get("X-RestLi-Id") or ""
    return {"id": post_id, "url": f"https://www.linkedin.com/feed/update/{post_id}/" if post_id else None}
