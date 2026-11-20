"""Assisted posting for places with no posting API: Claude prepares everything,
copies the caption to your clipboard, opens the right page and the media folder - you click Post."""
from __future__ import annotations

from pathlib import Path

from common import copy_to_clipboard, open_folder, open_url


def prepare(ctx: dict, key: str, caption: str, media: Path | None, url: str, steps: list[str]) -> dict:
    draft_dir: Path = ctx["draft_dir"]
    txt = draft_dir / f"caption_{key.replace(':', '_')}.txt"
    txt.write_text(caption, encoding="utf-8")
    copied = copy_to_clipboard(txt)
    if media:
        open_folder(media.parent)
    open_url(url)
    return {"manual": True, "url": url, "caption_file": str(txt), "clipboard": copied, "steps": steps}
