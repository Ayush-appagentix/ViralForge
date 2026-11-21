"""Change the caption of a post that is already live (needs approval, like publish).

Usage:
  1. Change the target's "caption" in the posted draft's draft.json (posted/<id>/draft.json).
  2. ./sa edit-post <draft> <platform:account>

Likes and comments stay. Supported where the platform allows editing through its API:
linkedin (personal profile). Everything else: edit it in the app.
"""
from __future__ import annotations

import argparse
import sys

import platforms
from common import PublishError, get_account, load_draft, now_iso, resolve_draft, save_draft, target_key
from voice import ai_tells


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("draft")
    ap.add_argument("target", help="platform:account, e.g. linkedin:me")
    a = ap.parse_args()

    d = resolve_draft(a.draft)
    draft = load_draft(d)
    target = next((t for t in draft.get("targets") or [] if target_key(t) == a.target), None)
    if not target:
        sys.exit(f"{a.target} is not a target of this draft "
                 f"({', '.join(target_key(t) for t in draft.get('targets') or [])}).")
    res = draft.get("results", {}).get(a.target) or {}
    if res.get("status") != "posted" or not res.get("id"):
        sys.exit(f"{a.target} has no live post with an id to edit (status: {res.get('status', 'not posted')}).")
    mod = platforms.load(target["platform"])
    if not hasattr(mod, "edit"):
        sys.exit(f"{mod.LABEL} can't be edited through its API - open the post and edit it there.")
    caption = target.get("caption") or ""
    if caption == res.get("caption_live"):
        sys.exit("The caption in draft.json is the same as the live one - change it first.")
    problems = mod.check(target, None, {"kind": draft.get("kind") if draft.get("kind") == "text" else "image"})
    problems = [p for p in problems if "caption" in p.lower()]
    if problems:
        sys.exit("Not editing - fix these first:\n" + "\n".join(f"  - {p}" for p in problems))
    for w in ai_tells(caption, target["platform"]):
        print(f"Voice warning: {w}")

    try:
        alias, account = get_account(getattr(mod, "ACCOUNTS_FROM", target["platform"]), target.get("account"))
        mod.edit(target, {**account, "_alias": alias}, res["id"], caption)
    except PublishError as e:
        sys.exit(f"Edit failed: {e}")
    res.setdefault("edits", []).append({"at": now_iso()})
    res["caption_live"] = caption
    save_draft(d, draft)
    print(f"Caption updated: {res.get('url')}")


if __name__ == "__main__":
    main()
