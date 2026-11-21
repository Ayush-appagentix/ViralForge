"""Publish an approved draft to every target in its draft.json - or schedule it.

Usage:
  ./sa publish <draft_dir>                              post now
  ./sa publish <draft_dir> --only instagram:main,youtube:personal
  ./sa publish <draft_dir> --at "2026-11-20 18:00"      schedule (your PC's local time; PC must be on)
  ./sa publish <draft_dir> --cancel                     cancel a scheduled post

Claude Code always asks you before this command runs. Already-posted targets are skipped,
so running it again after a failure only retries what failed. A target in "needs_check" (the
platform may have posted but gave no clear answer) is never retried until you check it.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import requests

import platforms
from common import (DRAFTS, POSTED, ROOT, DraftLock, OutcomeUnknown, PublishError, append_history, draft_media, fingerprint, get_account,
                    is_wsl, load_draft, platform_group, media_kind, now_iso, probe, resolve_draft, save_draft, target_key)

TASK_PATH = "\\SocialAgent\\"


# ---------- validation ----------

def media_info(media: Path | None) -> dict:
    kind = media_kind(media)
    info = {"kind": kind}
    if media is None:
        return info
    if not media.exists():
        raise SystemExit(f"Media file not found: {media}")
    info["size_mb"] = round(media.stat().st_size / 1_048_576, 2)
    if kind == "video":
        info.update(probe(media))
    else:
        from PIL import Image
        with Image.open(media) as im:
            info["width"], info["height"] = im.size
    return info


WARN_DAYS = 7


def login_days_left(account: dict) -> int | None:
    exp = account.get("expires_at")
    return None if not exp else int((exp - time.time()) // 86400)


def selected(t: dict, only: set[str] | None) -> bool:
    return not only or target_key(t) in only or t["platform"] in only


def check_draft(d: Path, draft: dict, only: set[str] | None = None) -> list[str]:
    problems = []
    targets = [t for t in draft.get("targets") or [] if selected(t, only)]
    if not targets:
        return ["draft.json has no targets (where should this be posted?)."]
    media = draft_media(d, draft)
    info = media_info(media)
    for t in targets:
        key = target_key(t)
        mod = platforms.load(t["platform"])
        if info["kind"] not in mod.MEDIA:
            problems.append(f"{key}: {mod.LABEL} can't post {info['kind']} posts.")
            continue
        problems += [f"{key}: {p}" for p in mod.check(t, media, info)]
        if mod.MODE == "api":
            try:
                _, account = get_account(getattr(mod, "ACCOUNTS_FROM", t["platform"]), t.get("account"))
            except PublishError as e:
                problems.append(f"{key}: {e}")
                continue
            days = login_days_left(account)
            if days is not None and days < 0:
                problems.append(f"{key}: login expired - in your terminal run ./sa connect {platform_group(t['platform'])}")
            elif days is not None and days <= WARN_DAYS:
                print(f"Warning - {key}: login expires in {days} day(s). Reconnect soon so posts don't fail: "
                      f"./sa connect {platform_group(t['platform'])}")
    return problems


# ---------- lifecycle ----------

def finalize(d: Path, draft: dict) -> Path:
    states = [draft.get("results", {}).get(target_key(t), {}).get("status") for t in draft["targets"]]
    if "needs_check" in states:
        draft["status"] = "needs_check"
    elif all(s == "posted" for s in states):
        draft["status"] = "posted"
    elif all(s in ("posted", "awaiting_manual") for s in states):
        draft["status"] = "awaiting_manual"
    elif any(s in ("posted", "awaiting_manual") for s in states):
        draft["status"] = "partial"
    else:
        draft["status"] = "failed"
    save_draft(d, draft)
    if draft["status"] != "posted":
        return d
    append_history({"date": now_iso(), "id": draft.get("id", d.name), "title": draft.get("title"),
                    "topic": draft.get("topic"), "brand": draft.get("brand"), "kind": draft.get("kind"),
                    "posts": {k: v.get("url") for k, v in draft.get("results", {}).items()}})
    POSTED.mkdir(exist_ok=True)
    dest = POSTED / d.name
    shutil.move(str(d), str(dest))
    return dest


def run_targets(d: Path, draft: dict, only: set[str] | None) -> Path:
    media = draft_media(d, draft)
    info = media_info(media)
    ctx = {"kind": info["kind"], "draft_dir": d, "alt_text": draft.get("alt_text"), "title": draft.get("title"),
           "thumbnail_at": draft.get("thumbnail_at"), "duration": info.get("duration"),
           "orientation": info.get("orientation")}
    draft.setdefault("results", {})
    for t in sorted(draft["targets"], key=lambda t: platforms.sort_key(t["platform"])):
        key = target_key(t)
        if not selected(t, only):
            continue
        state = draft["results"].get(key, {}).get("status")
        if state in ("posted", "awaiting_manual"):
            print(f"- {key}: already done, skipping")
            continue
        if state == "needs_check":
            print(f"- {key}: SKIPPED - the last try may have posted. Check the platform, then run\n"
                  f"    ./sa drafts mark-posted {d.name} {key} [url]   if it is live, or\n"
                  f"    ./sa drafts reset {d.name} {key}               if it is not, then publish again.")
            continue
        mod = platforms.load(t["platform"])
        print(f"- {key}: posting to {mod.LABEL} ...", flush=True)
        try:
            try:
                alias, account = get_account(getattr(mod, "ACCOUNTS_FROM", t["platform"]), t.get("account"))
                account = {**account, "_alias": alias}
            except PublishError:
                if mod.MODE == "api":
                    raise
                account = {}
            res = mod.publish(t, media, account, ctx)
            if res.get("manual"):
                draft["results"][key] = {"status": "awaiting_manual", "at": now_iso(), **res}
                print(f"  ACTION NEEDED - {mod.LABEL}:")
                for step in res.get("steps", []):
                    print(f"    * {step}")
            else:
                draft["results"][key] = {"status": "posted", "id": res.get("id"), "url": res.get("url"), "at": now_iso(),
                                         "caption_live": t.get("caption")}
                print(f"  posted: {res.get('url')}")
        except OutcomeUnknown as e:
            draft["results"][key] = {"status": "needs_check", "error": str(e), "at": now_iso()}
            print(f"  NOT SURE IT POSTED: {e}\n  Not retrying, so it can't post twice.")
        except (PublishError, requests.RequestException, OSError) as e:
            draft["results"][key] = {"status": "failed", "error": str(e), "at": now_iso()}
            print(f"  FAILED: {e}")
        except Exception as e:  # noqa: BLE001 - one broken platform must not stop the others
            msg = f"unexpected {type(e).__name__}: {e}"
            draft["results"][key] = {"status": "failed", "error": msg, "at": now_iso()}
            print(f"  FAILED ({msg}). The other platforms still run.")
            traceback.print_exc(file=sys.stderr)
        save_draft(d, draft)
    return finalize(d, draft)


# ---------- scheduling (Windows Task Scheduler, runs the agent inside WSL) ----------

def powershell(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                          capture_output=True, text=True)


def psq(s: str) -> str:
    return s.replace("'", "''")


def schedule(d: Path, draft: dict, when: str) -> None:
    if not is_wsl():
        sys.exit("Scheduling uses Windows Task Scheduler and needs this agent to run inside WSL.")
    try:
        dt = datetime.strptime(when.strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        sys.exit('Use the format --at "YYYY-MM-DD HH:MM" (24-hour, your PC\'s local time).')
    distro = os.environ.get("WSL_DISTRO_NAME", "Ubuntu")
    rel = d.relative_to(ROOT).as_posix()
    args = f"-d {distro} --cd {ROOT} -- ./sa publish {rel} --scheduled-run"
    r = powershell(
        f"$when = [datetime]'{dt:%Y-%m-%dT%H:%M:00}'; "
        "if ($when -lt (Get-Date)) { Write-Output 'PAST'; exit 3 }; "
        f"$a = New-ScheduledTaskAction -Execute 'wsl.exe' -Argument '{psq(args)}'; "
        "$t = New-ScheduledTaskTrigger -Once -At $when; "
        "$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries; "
        f"Register-ScheduledTask -TaskPath '{TASK_PATH}' -TaskName 'post-{psq(d.name)}' "
        "-Action $a -Trigger $t -Settings $s -Force | Out-Null")
    if "PAST" in r.stdout:
        sys.exit(f"{when} is already in the past (PC local time).")
    if r.returncode != 0:
        sys.exit(f"Could not create the Windows scheduled task:\n{r.stderr[-1500:]}")
    draft.update({"status": "scheduled", "scheduled_for": when, "approval": approval(d, draft)})
    save_draft(d, draft)
    print(f"Scheduled for {when} (PC local time). Windows Task Scheduler > SocialAgent > post-{d.name}")
    print("Your PC must be on and signed in at that time; if it's off, it posts as soon as it's back on.")


def approval(d: Path, draft: dict) -> dict:
    return {"approved_at": now_iso(), "how": "confirmed in Claude Code", "fingerprint": fingerprint(d, draft)}


def changed_since_approval(d: Path, draft: dict) -> bool:
    saved = (draft.get("approval") or {}).get("fingerprint")
    return bool(saved) and saved != fingerprint(d, draft)


def unschedule(d: Path) -> None:
    if is_wsl():
        powershell(f"Unregister-ScheduledTask -TaskPath '{TASK_PATH}' -TaskName 'post-{psq(d.name)}' "
                   "-Confirm:$false -ErrorAction SilentlyContinue")


def notify(text: str) -> None:
    from notify import notify as windows_notification
    try:
        windows_notification("Social agent", text)
    except (OSError, subprocess.TimeoutExpired):
        pass


# ---------- main ----------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("draft")
    ap.add_argument("--only", help="comma-separated platform or platform:account list")
    ap.add_argument("--at", help='schedule instead of posting now: "YYYY-MM-DD HH:MM"')
    ap.add_argument("--cancel", action="store_true", help="cancel a scheduled post")
    ap.add_argument("--scheduled-run", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args()

    d = resolve_draft(a.draft)
    if a.scheduled_run:
        log = (DRAFTS / "_scheduled.log").open("a", encoding="utf-8")
        sys.stdout = sys.stderr = log
        print(f"\n=== {now_iso()} scheduled publish of {d.name}")
    try:
        with DraftLock(d):
            run(d, a)
    except Exception:  # noqa: BLE001 - nobody is watching a scheduled run: always tell the user
        if not a.scheduled_run:
            raise
        traceback.print_exc()
        notify(f"Scheduled post '{d.name}' crashed - see drafts/_scheduled.log, then run /review")
        sys.exit(1)


def run(d: Path, a: argparse.Namespace) -> None:
    draft = load_draft(d)  # read inside the lock: another run may just have changed it

    if draft.get("status") in ("posted", "rejected"):
        sys.exit(f"This draft is already {draft['status']}.")
    if a.cancel:
        unschedule(d)
        draft.update({"status": "pending", "scheduled_for": None})
        save_draft(d, draft)
        print("Scheduled post cancelled; the draft is back to pending.")
        return
    if a.scheduled_run and draft.get("status") != "scheduled":
        print(f"Skipped: status is '{draft.get('status')}', not 'scheduled'.")
        unschedule(d)
        return

    if a.scheduled_run and changed_since_approval(d, draft):
        unschedule(d)
        draft.update({"status": "pending", "scheduled_for": None})
        save_draft(d, draft)
        print("Not posting: the draft was changed after you approved the schedule. Back to pending.")
        notify(f"'{draft.get('title', d.name)}' changed after approval - not posted. Run /review to approve it again.")
        return

    only = {s.strip() for s in a.only.split(",") if s.strip()} if a.only else None
    if only:
        known = {target_key(t) for t in draft.get("targets") or []} | {t["platform"] for t in draft.get("targets") or []}
        unknown = sorted(only - known)
        if unknown:
            sys.exit(f"--only {', '.join(unknown)} is not in this draft. Its targets: "
                     f"{', '.join(sorted(target_key(t) for t in draft.get('targets') or []))}")
    problems = check_draft(d, draft, only)
    if problems:
        print("Not posting - fix these first:\n" + "\n".join(f"  - {p}" for p in problems))
        if a.scheduled_run:
            notify(f"Scheduled post '{draft.get('title', d.name)}' failed checks - open Claude Code and run /review")
        sys.exit(1)

    if a.at:
        schedule(d, draft, a.at)
        return

    if not a.scheduled_run:  # a manual publish is a fresh approval of what is there now
        draft["approval"] = approval(d, draft)
    final_dir = run_targets(d, draft, only)
    result = load_draft(final_dir)
    print(f"\nStatus: {result['status']}   ({final_dir})")
    if a.scheduled_run:
        unschedule(d)
        notify(f"'{result.get('title', d.name)}' - {result['status']}")


if __name__ == "__main__":
    main()
