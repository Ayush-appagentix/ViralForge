"""Render an HTML design to an exact-size PNG + JPEG using the Edge/Chrome already on this PC.

Usage: ./sa render-image <post.html> [--size 1080x1350]

Writes post.png and post.jpg next to the HTML file (Instagram's API accepts JPEG only).
The HTML should be a fixed-size page: html,body { width:1080px; height:1350px; margin:0; overflow:hidden }.
Sizes: 1080x1350 (4:5 feed post), 1080x1080 (square), 1080x1920 (story / slide for a Short).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

from PIL import Image

from common import ROOT, is_wsl, win_path

WINDOWS_BROWSERS = [
    "/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    "/mnt/c/Program Files/Microsoft/Edge/Application/msedge.exe",
    "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
]


def find_browser() -> tuple[str, bool]:
    """Return (browser path, needs_windows_paths)."""
    for name in ("chromium", "chromium-browser", "google-chrome", "microsoft-edge"):
        if shutil.which(name):
            return shutil.which(name), False
    for b in WINDOWS_BROWSERS:
        if Path(b).exists():
            return b, is_wsl()
    sys.exit("Microsoft Edge or Google Chrome is required to render images.")


def render(html: Path, width: int, height: int) -> tuple[Path, Path]:
    html = html.resolve()
    png, jpg = html.with_suffix(".png"), html.with_suffix(".jpg")
    png.unlink(missing_ok=True)
    browser, windows = find_browser()
    if windows:  # Windows Edge driven from WSL: every path must be a Windows path
        profile = ROOT / ".cache" / "browser-profile"
        profile.mkdir(parents=True, exist_ok=True)
        to = win_path
        url = "file:///" + quote(win_path(html).replace("\\", "/"), safe=":/")
        tmp = None
    else:
        tmp = tempfile.TemporaryDirectory()
        profile, to, url = Path(tmp.name), str, html.as_uri()
    cmd = [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
           "--no-default-browser-check", "--force-device-scale-factor=1",
           f"--user-data-dir={to(profile)}", f"--window-size={width},{height}",
           "--virtual-time-budget=6000", f"--screenshot={to(png)}", url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        sys.exit("The browser took over 2 minutes and was stopped. Usually the HTML waits on something that "
                 "never loads (a web font or image URL) or an endless animation - remove it and try again.")
    finally:
        if tmp:
            tmp.cleanup()
    if not png.exists():
        sys.exit(f"Browser did not produce a screenshot.\n{r.stderr[-2000:]}")
    img = Image.open(png).convert("RGB")
    if img.size != (width, height):  # headless viewport can be off by a few px; force exact size
        canvas = Image.new("RGB", (width, height), "white")
        canvas.paste(img.crop((0, 0, min(width, img.width), min(height, img.height))), (0, 0))
        img = canvas
        img.save(png)
    img.save(jpg, "JPEG", quality=93, optimize=True)
    return png, jpg


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("html")
    ap.add_argument("--size", default="1080x1350", help="WIDTHxHEIGHT, e.g. 1080x1350 or 1080x1920")
    a = ap.parse_args()
    try:
        w, h = (int(x) for x in a.size.lower().split("x"))
    except ValueError:
        sys.exit(f"--size must look like 1080x1350, not '{a.size}'.")
    if not Path(a.html).exists():
        sys.exit(f"HTML file not found: {a.html}")
    png, jpg = render(Path(a.html), w, h)
    print(f"Wrote {png} and {jpg} ({w}x{h}, {jpg.stat().st_size // 1024} KB)")
