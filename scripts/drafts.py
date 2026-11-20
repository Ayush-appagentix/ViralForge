"""Manage drafts (nothing here posts anything).

Usage:
  ./sa drafts list                                  drafts waiting for you (pending, scheduled, needs action)
  ./sa drafts new <video|image|text|slideshow> <title words...> [--brand main]
  ./sa drafts show <draft>                          everything about one draft
  ./sa drafts check <draft>                         will it post cleanly? (limits, formats, accounts)
  ./sa drafts reject <draft>                        throw it away (moved to drafts/_rejected)
  ./sa drafts mark-posted <draft> <platform:account> [post-url]   after you clicked Post yourself
  ./sa drafts history [--days 30]                   what was posted recently
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timedelta

from common import (DRAFTS, HISTORY, ROOT, load_draft, now_iso, resolve_draft, save_draft, slug,
                    target_key)
from publish import check_draft, finalize

WAITING = ("pending", "scheduled", "awaiting_manual", "partial", "failed")


def cmd_list(_):
    rows = []
    for f in sorted(DRAFTS.glob("*/draft.json")):
        if f.parent.name.startswith("_"):
            continue
        dr = json.loads(f.read_text(encoding="utf-8"))
        if dr.get("status") in WAITING or dr.get("status") == "drafting":
            targets = ", ".join(target_key(t) for t in dr.get("targets", []))
            when = f" @ {dr['scheduled_for']}" if dr.get("scheduled_for") else ""
            rows.append(f"{dr.get('status', '?'):16} {f.parent.relative_to(ROOT)}  |  {dr.get('title', '')}{when}  ->  {targets}")
    print("\n".join(rows) if rows else "No drafts waiting.")


def cmd_new(a):
    title = " ".join(a.title)
    d = DRAFTS / f"{datetime.now():%Y%m%d-%H%M}-{slug(title)}"
    n = 2
    while d.exists():
        d = DRAFTS / f"{datetime.now():%Y%m%d-%H%M}-{slug(title)}-{n}"
        n += 1
    d.mkdir(parents=True)
    save_draft(d, {"id": d.name, "title": title, "kind": a.kind, "brand": a.brand, "topic": None,
                   "status": "drafting", "created_at": now_iso(), "media": None, "alt_text": None,
                   "targets": [], "results": {}})
    print(d.relative_to(ROOT))


def cmd_show(a):
    d = resolve_draft(a.draft)
    dr = load_draft(d)
    print(f"{dr.get('title')}  [{dr.get('status')}]  {d.relative_to(ROOT)}")
    print(f"kind: {dr.get('kind')}   media: {dr.get('media')}   brand: {dr.get('brand')}")
    if dr.get("scheduled_for"):
        print(f"scheduled for: {dr['scheduled_for']}")
    for t in dr.get("targets", []):
        res = dr.get("results", {}).get(target_key(t), {})
        print(f"\n== {target_key(t)}   {res.get('status', 'not posted')}  {res.get('url') or res.get('error') or ''}")
        for k, v in t.items():
            if k not in ("platform", "account"):
                print(f"{k}: {v}")


def cmd_check(a):
    d = resolve_draft(a.draft)
    problems = check_draft(d, load_draft(d))
    if problems:
        print("Problems:\n" + "\n".join(f"  - {p}" for p in problems))
        sys.exit(1)
    print("OK - ready to post.")


def cmd_reject(a):
    d = resolve_draft(a.draft)
    dr = load_draft(d)
    dr["status"] = "rejected"
    save_draft(d, dr)
    dest = DRAFTS / "_rejected" / d.name
    dest.parent.mkdir(exist_ok=True)
    shutil.move(str(d), str(dest))
    print(f"Rejected -> {dest.relative_to(ROOT)}")


def cmd_mark_posted(a):
    d = resolve_draft(a.draft)
    dr = load_draft(d)
    keys = {target_key(t) for t in dr.get("targets", [])}
    if a.target not in keys:
        sys.exit(f"Unknown target {a.target}. This draft has: {', '.join(sorted(keys))}")
    dr.setdefault("results", {})[a.target] = {"status": "posted", "url": a.url, "at": now_iso(), "manual": True}
    final = finalize(d, dr)
    print(f"Marked {a.target} as posted. Draft status: {load_draft(final)['status']}")


def cmd_history(a):
    if not HISTORY.exists():
        print("Nothing posted yet.")
        return
    since = datetime.now().astimezone() - timedelta(days=a.days)
    for line in HISTORY.read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        if datetime.fromisoformat(e["date"]) >= since:
            print(f"{e['date'][:10]}  [{e.get('brand')}] {e.get('title')}  (topic: {e.get('topic')})  "
                  f"-> {', '.join(e.get('posts', {}))}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    p = sub.add_parser("new")
    p.add_argument("kind", choices=["video", "image", "text", "slideshow"])
    p.add_argument("title", nargs="+")
    p.add_argument("--brand", default="main")
    p.set_defaults(fn=cmd_new)
    for name, fn in (("show", cmd_show), ("check", cmd_check), ("reject", cmd_reject)):
        p = sub.add_parser(name)
        p.add_argument("draft")
        p.set_defaults(fn=fn)
    p = sub.add_parser("mark-posted")
    p.add_argument("draft")
    p.add_argument("target")
    p.add_argument("url", nargs="?")
    p.set_defaults(fn=cmd_mark_posted)
    p = sub.add_parser("history")
    p.add_argument("--days", type=int, default=30)
    p.set_defaults(fn=cmd_history)
    args = ap.parse_args()
    args.fn(args)
