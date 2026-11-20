"""Platform plug-ins: each .py file in this folder is one place the agent can post to.

To add a platform, drop in <name>.py with:
  LABEL = "Human name"
  MODE = "api"        # api: posts automatically | assisted: Claude prepares it, you click Post
  MEDIA = {"image", "video", "text"}       # what it can post
  ACCOUNTS_FROM = "<name>"                 # optional: reuse another platform's connected accounts
  def check(target, media, info) -> list[str]      # problems that would make posting fail
  def publish(target, media, account, ctx) -> dict # {"id", "url"}; assisted returns {"manual": True, ...}
"""
from __future__ import annotations

import importlib
from pathlib import Path

# Facebook runs before Instagram so Instagram can reuse the image Facebook already hosts.
ORDER = ["facebook", "instagram", "linkedin", "youtube"]


def available() -> list[str]:
    return sorted(p.stem for p in Path(__file__).parent.glob("*.py") if not p.stem.startswith("_"))


def load(platform: str):
    if platform not in available():
        raise SystemExit(f"Unknown platform '{platform}'. Available: {', '.join(available())}")
    return importlib.import_module(f"platforms.{platform}")


def sort_key(platform: str) -> int:
    return ORDER.index(platform) if platform in ORDER else len(ORDER)
