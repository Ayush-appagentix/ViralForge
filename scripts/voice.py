"""Spot phrasing that makes a caption read as AI-written.

Usage: ./sa voice <draft>          check every caption in a draft
       ./sa voice --text "..."     check one piece of text

These are warnings, not hard rules: the agent rewrites flagged captions before showing them to you.
`./sa drafts check` runs the same check.
"""
from __future__ import annotations

import argparse
import re
import sys

# Stock phrases that show up far more in AI text than in people's own posts.
PHRASES = [
    "here's the thing", "here's the kicker", "notice the pattern", "let that sink in", "game-changer",
    "game changer", "in today's fast-paced", "in a world where", "the best part?", "the result?",
    "spoiler:", "let's dive in", "dive into", "delve", "buckle up", "unlock the power", "unleash",
    "it's not just", "isn't just about", "the secret sauce", "the real magic", "a testament to",
    "navigate the complexities", "ever-evolving", "landscape of", "supercharge", "elevate your",
    "harness the power", "seamlessly", "revolutionize", "hot take:", "but here's",
]
NOT_X_ITS_Y = re.compile(r"\b(?:isn't|is not|aren't|wasn't|not)\b[^.\n]{1,60}[.,;:]\s*(?:it's|it is|they're)\b", re.I)
ARROW = re.compile(r"[→➡⟶➜▶►]")
HASHTAG = re.compile(r"(?<!\w)#\w+")
MAX_HASHTAGS = {"instagram": 8, "youtube": 3}  # everything else: 3


def ai_tells(text: str, platform: str = "linkedin") -> list[str]:
    found, low = [], text.lower()
    hits = sorted({p for p in PHRASES if p in low})
    if hits:
        found.append("stock phrases: " + ", ".join(f'"{h}"' for h in hits))
    arrows = len(ARROW.findall(text))
    if arrows >= 2:
        found.append(f"{arrows} arrow characters (→): looks like a template. Write sentences instead.")
    m = NOT_X_ITS_Y.search(text)
    if m:
        found.append(f'"not X, it\'s Y" formula: "{m.group(0).strip()}"')
    dashes = text.count("—")
    if dashes > 2:
        found.append(f"{dashes} em dashes (—): use fewer, or commas and full stops.")
    tags = len(HASHTAG.findall(text))
    limit = MAX_HASHTAGS.get(platform, 3)
    if tags > limit:
        found.append(f"{tags} hashtags: keep it to {limit} or fewer on {platform}.")
    bullets = sum(1 for line in text.splitlines() if re.match(r"\s*(?:[-•✅✔️🔹▪]|\d{1,2}[.)])\s", line))
    if bullets >= 5:
        found.append(f"{bullets} list lines: a person posting usually writes a few short paragraphs.")
    return found


def draft_warnings(draft: dict) -> list[str]:
    out = []
    for t in draft.get("targets") or []:
        key = f"{t['platform']}:{t.get('account') or 'default'}"
        for field in ("caption", "description"):
            if t.get(field):
                out += [f"{key} {field}: {w}" for w in ai_tells(t[field], t["platform"])]
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("draft", nargs="?")
    ap.add_argument("--text")
    ap.add_argument("--platform", default="linkedin")
    a = ap.parse_args()
    if a.text is not None:
        warnings = ai_tells(a.text, a.platform)
    elif a.draft:
        from common import load_draft, resolve_draft
        warnings = draft_warnings(load_draft(resolve_draft(a.draft)))
    else:
        sys.exit(__doc__)
    if warnings:
        print("Sounds AI-written:\n" + "\n".join(f"  - {w}" for w in warnings))
        sys.exit(1)
    print("OK - no AI tells found.")
