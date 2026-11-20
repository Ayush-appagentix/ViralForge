"""Show connected accounts (never prints tokens).

Usage:
  ./sa accounts                               list everything connected
  ./sa accounts default <platform> <alias>    make an account the default for a platform
  ./sa accounts remove <platform> <alias>     forget an account
"""
from __future__ import annotations

import sys
import time

from common import load_accounts, save_accounts

PLATFORMS = ["facebook", "instagram", "youtube", "linkedin"]


def describe(platform: str, acc: dict) -> str:
    name = {"facebook": acc.get("page_name"), "instagram": "@" + str(acc.get("username")),
            "youtube": f"{acc.get('title')} ({acc.get('handle') or acc.get('channel_id')})",
            "linkedin": acc.get("name")}.get(platform, "")
    exp = acc.get("expires_at")
    if exp:
        days = int((exp - time.time()) / 86400)
        name += f"   login {'EXPIRED' if days < 0 else f'expires in {days} days'}"
    return name


def main(argv: list[str]) -> None:
    if argv[:1] == ["default"] and len(argv) == 3:
        data = load_accounts(argv[1])
        if argv[2] not in data["accounts"]:
            sys.exit(f"No {argv[1]} account '{argv[2]}'.")
        data["default"] = argv[2]
        save_accounts(argv[1], data)
        print(f"Default {argv[1]} account is now '{argv[2]}'.")
        return
    if argv[:1] == ["remove"] and len(argv) == 3:
        data = load_accounts(argv[1])
        data["accounts"].pop(argv[2], None)
        if data.get("default") == argv[2]:
            data["default"] = next(iter(data["accounts"]), None)
        save_accounts(argv[1], data)
        print(f"Removed {argv[1]} account '{argv[2]}'.")
        return
    if argv:
        sys.exit(__doc__)
    any_found = False
    for p in PLATFORMS:
        data = load_accounts(p)
        for alias, acc in data["accounts"].items():
            any_found = True
            star = "*" if alias == data.get("default") else " "
            print(f"{star} {p + ':' + alias:28} {describe(p, acc)}")
    if not any_found:
        print("No accounts connected yet. In your terminal run: ./sa connect meta | youtube | linkedin")
    else:
        print("\n* = default account for that platform. Assisted targets (youtube_community, "
              "facebook_profile, linkedin_page) need no connection.")


if __name__ == "__main__":
    main(sys.argv[1:])
