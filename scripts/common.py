"""Shared helpers: paths, settings, connected accounts, ffmpeg, media probing, drafts."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "drafts"
POSTED = ROOT / "posted"
SECRETS = ROOT / "secrets"
BRANDS = ROOT / "brands"
HISTORY = POSTED / "log.jsonl"

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif"}
VIDEO_EXT = {".mp4", ".mov", ".m4v"}


class PublishError(Exception):
    """A platform rejected a request; the message is safe to show the user."""


class OutcomeUnknown(PublishError):
    """The request that creates the post was sent, but no clear answer came back, so the post
    may be live. Never retried automatically: retrying could post twice."""


# ---------- HTTP with retries ----------

RETRY_STATUS = {429, 500, 502, 503, 504}


def _rewind(kw: dict) -> list:
    """Remember where file bodies start so a retry re-sends them from the same place."""
    spots = []
    bodies = [kw.get("data")] + [v[1] if isinstance(v, tuple) else v for v in (kw.get("files") or {}).values()]
    for b in bodies:
        if hasattr(b, "seek") and hasattr(b, "tell"):
            spots.append((b, b.tell()))
    return spots


def http(method: str, url: str, *, final: bool = False, attempts: int = 4, what: str = "request",
         **kw) -> "requests.Response":
    """requests.request with retries for flaky networks, rate limits (429) and server errors (5xx).

    final=True marks the call that makes the post public. It is never retried after the server may
    have received it: a lost answer raises OutcomeUnknown instead, so nothing gets posted twice.
    """
    import time

    import requests

    kw.setdefault("timeout", 60)
    spots = _rewind(kw)
    for attempt in range(1, attempts + 1):
        r, err = None, None
        try:
            r = requests.request(method, url, **kw)
        except requests.exceptions.ConnectTimeout as e:  # never reached the server: safe to retry
            err = e
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
            if final:
                raise OutcomeUnknown(f"No answer from the platform during {what} ({type(e).__name__}). "
                                     "The post may or may not be live - check before retrying.")
            err = e
        else:
            if r.status_code not in RETRY_STATUS:
                return r
            if final and r.status_code != 429:  # 429 = refused before doing anything
                raise OutcomeUnknown(f"The platform answered {r.status_code} during {what}. "
                                     "The post may or may not be live - check before retrying.")
        if attempt == attempts:
            if r is not None:
                return r
            raise PublishError(f"Network problem during {what} after {attempts} tries: {err}")
        wait = min(2 ** attempt * 2, 60)
        if r is not None and (r.headers.get("Retry-After") or "").isdigit():
            wait = min(int(r.headers["Retry-After"]), 300)
        print(f"  {what}: {'HTTP ' + str(r.status_code) if r is not None else type(err).__name__}, "
              f"retrying in {wait}s ({attempt}/{attempts - 1})", flush=True)
        time.sleep(wait)
        for body, pos in spots:
            body.seek(pos)
    raise AssertionError("unreachable")


# ---------- settings (.env) ----------

def env(name: str, default: str | None = None) -> str | None:
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    value = os.environ.get(name, "").strip()
    return value or default


# ---------- connected accounts (secrets/<platform>.json) ----------

def _secret_file(platform: str) -> Path:
    return SECRETS / f"{platform}.json"


def load_accounts(platform: str) -> dict:
    f = _secret_file(platform)
    if not f.exists():
        return {"default": None, "accounts": {}}
    return json.loads(f.read_text(encoding="utf-8"))


def save_accounts(platform: str, data: dict) -> None:
    SECRETS.mkdir(exist_ok=True)
    f = _secret_file(platform)
    f.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        f.chmod(0o600)
    except OSError:
        pass


def save_account(platform: str, alias: str, info: dict, make_default: bool = False) -> None:
    data = load_accounts(platform)
    data["accounts"][alias] = info
    if make_default or not data.get("default"):
        data["default"] = alias
    save_accounts(platform, data)


def get_account(platform: str, alias: str | None = None) -> tuple[str, dict]:
    data = load_accounts(platform)
    alias = alias or data.get("default")
    if not alias or alias not in data["accounts"]:
        known = ", ".join(data["accounts"]) or "none"
        which = f"named '{alias}'" if alias else "set up"
        raise PublishError(f"No {platform} account {which} (connected: {known}). "
                           f"Connect one in your terminal: ./sa connect {platform_group(platform)}")
    return alias, data["accounts"][alias]


def platform_group(platform: str) -> str:
    return {"facebook": "meta", "instagram": "meta", "youtube_community": "youtube"}.get(platform, platform)


def slug(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len].strip("-") or "post"


# ---------- Windows / WSL bridges ----------

def is_wsl() -> bool:
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        return False


def win_path(p: Path | str) -> str:
    """Path as Windows sees it (for Windows programs started from WSL)."""
    if not is_wsl():
        return str(p)
    return subprocess.run(["wslpath", "-w", str(p)], capture_output=True, text=True, check=True).stdout.strip()


def open_url(url: str) -> None:
    """Open a link in the user's normal browser (the Windows one when running in WSL)."""
    print(f"\nIf the browser doesn't open, copy this link into it:\n{url}\n")
    try:
        if is_wsl():
            subprocess.run(["explorer.exe", url], check=False, capture_output=True)
        else:
            import webbrowser
            webbrowser.open(url)
    except FileNotFoundError:
        pass


def open_folder(path: Path) -> None:
    try:
        if is_wsl():
            subprocess.run(["explorer.exe", win_path(path)], check=False, capture_output=True)
    except FileNotFoundError:
        pass


def copy_to_clipboard(text_file: Path) -> bool:
    """Copy a UTF-8 text file to the Windows clipboard (keeps emoji intact)."""
    if not is_wsl():
        return False
    p = win_path(text_file).replace("'", "''")
    r = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                        f"Get-Content -Raw -Encoding UTF8 -LiteralPath '{p}' | Set-Clipboard"],
                       capture_output=True)
    return r.returncode == 0


def system_fonts_dir() -> Path | None:
    for c in (Path("/mnt/c/Windows/Fonts"), Path("/usr/share/fonts")):
        if c.exists():
            return c
    return None


# ---------- external tools ----------

def find_tool(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    local_bin = Path.home() / ".local" / "bin" / name
    if local_bin.exists():
        return str(local_bin)
    sys.exit(f"{name} not found. See SETUP.md, step 1.")


def run(cmd: list[str], cwd: Path | str | None = None) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-6000:] + "\n")
        raise RuntimeError(f"{Path(cmd[0]).name} failed with exit code {r.returncode}")
    return r


def probe(path: Path | str) -> dict:
    """Display width/height (rotation applied), duration, fps and audio presence."""
    r = run([find_tool("ffprobe"), "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", str(path)])
    data = json.loads(r.stdout)
    v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    info = {
        "file": str(path),
        "duration": round(float(data.get("format", {}).get("duration") or 0), 2),
        "size_mb": round(int(data.get("format", {}).get("size") or 0) / 1_048_576, 2),
        "has_audio": a is not None,
    }
    if v:
        w, h = int(v.get("width", 0)), int(v.get("height", 0))
        rotation = 0
        for sd in v.get("side_data_list", []) or []:
            if "rotation" in sd:
                rotation = int(float(sd["rotation"]))
        rotation = rotation or int(v.get("tags", {}).get("rotate", 0) or 0)
        if abs(rotation) % 180 == 90:
            w, h = h, w
        num, _, den = (v.get("avg_frame_rate") or "0/1").partition("/")
        fps = float(num) / float(den) if float(den or 0) else 0.0
        info.update({"width": w, "height": h, "rotation": rotation, "fps": round(fps, 2),
                     "video_codec": v.get("codec_name"),
                     "orientation": "vertical" if h > w else "horizontal" if w > h else "square"})
    return info


# ---------- drafts ----------

def resolve_draft(arg: str) -> Path:
    p = Path(arg)
    for c in ([p] if p.is_absolute() else [ROOT / p, DRAFTS / arg, POSTED / arg]):
        if (c / "draft.json").exists():
            return c.resolve()
    recent = sorted((f.parent.name for f in DRAFTS.glob("*/draft.json") if not f.parent.name.startswith("_")),
                    reverse=True)[:5]
    hint = ("\nRecent drafts: " + ", ".join(recent)) if recent else ""
    sys.exit(f"No draft.json found for '{arg}' (looked in drafts/ and posted/).{hint}")


def load_draft(d: Path) -> dict:
    return json.loads((d / "draft.json").read_text(encoding="utf-8"))


def save_draft(d: Path, data: dict) -> None:
    tmp = d / "draft.json.tmp"
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(d / "draft.json")


def draft_media(d: Path, draft: dict) -> Path | None:
    m = draft.get("media")
    if not m:
        return None
    p = Path(m)
    return p if p.is_absolute() else d / p


def media_kind(path: Path | None) -> str:
    if path is None:
        return "text"
    ext = path.suffix.lower()
    if ext in IMAGE_EXT:
        return "image"
    if ext in VIDEO_EXT:
        return "video"
    raise ValueError(f"Unsupported media type: {path.name}")


def fingerprint(d: Path, draft: dict) -> str:
    """Hash of everything the audience will see: media bytes, alt text and every target's text.
    Stored at approval; a scheduled run refuses to post if it no longer matches."""
    import hashlib

    h = hashlib.sha256()
    media = draft_media(d, draft)
    if media and media.exists():
        with media.open("rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
    seen = {k: draft.get(k) for k in ("media", "alt_text")}
    seen["targets"] = [{k: v for k, v in t.items()} for t in draft.get("targets") or []]
    h.update(json.dumps(seen, sort_keys=True, ensure_ascii=False).encode())
    return h.hexdigest()[:16]


def target_key(t: dict) -> str:
    return f"{t['platform']}:{t.get('account') or 'default'}"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def append_history(entry: dict) -> None:
    POSTED.mkdir(exist_ok=True)
    with HISTORY.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


class DraftLock:
    """Stops two publishes of the same draft running at once (e.g. a scheduled run and a manual one).
    Lives outside the draft folder because the folder is moved to posted/ while locked."""

    def __init__(self, draft_dir: Path):
        self.path = ROOT / ".cache" / "locks" / f"{draft_dir.name}.lock"

    def _holder_alive(self) -> bool:
        try:
            pid = int(self.path.read_text().split()[0])
            os.kill(pid, 0)
            return True
        except (OSError, ValueError, IndexError):
            return False

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if self._holder_alive():
                    raise SystemExit("This draft is already being published by another run "
                                     f"(lock: {self.path.relative_to(ROOT)}). Wait for it to finish.")
                self.path.unlink(missing_ok=True)  # left behind by a crashed run
                continue
            with os.fdopen(fd, "w") as f:
                f.write(f"{os.getpid()} {now_iso()}\n")
            return self
        raise SystemExit(f"Could not lock {self.path}")

    def __exit__(self, *exc):
        self.path.unlink(missing_ok=True)
        return False


def print_json(data) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))
