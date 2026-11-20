"""Have Claude prepare a draft post every day (it never posts - you approve with /review).

Usage (run yourself in the terminal):
  ./sa schedule-daily 09:00 [--brand main]   every day at 09:00 (PC local time)
  ./sa schedule-daily --status
  ./sa schedule-daily --run-now [--brand main]
  ./sa schedule-daily --off
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

from common import ROOT, is_wsl

TASK = ("\\SocialAgent\\", "daily-draft")


def ps(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                          capture_output=True, text=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("time", nargs="?", help="HH:MM, 24-hour")
    ap.add_argument("--brand", default="main")
    ap.add_argument("--off", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--run-now", action="store_true")
    a = ap.parse_args()
    if not is_wsl():
        sys.exit("This uses Windows Task Scheduler and expects the agent to run inside WSL.")
    path, name = TASK
    if a.run_now:
        os.execvp("bash", ["bash", str(ROOT / "scripts" / "daily.sh"), a.brand])
    if a.off:
        ps(f"Unregister-ScheduledTask -TaskPath '{path}' -TaskName '{name}' -Confirm:$false -ErrorAction SilentlyContinue")
        print("Daily drafts turned off.")
        return
    if a.status or not a.time:
        r = ps(f"Get-ScheduledTask -TaskPath '{path}' -TaskName '{name}' -ErrorAction SilentlyContinue | "
               "Get-ScheduledTaskInfo | Select-Object LastRunTime,NextRunTime,LastTaskResult | Format-List")
        print(r.stdout.strip() or "Daily drafts are off.")
        return
    if not re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", a.time):
        sys.exit("Time must be HH:MM, e.g. 09:00")
    distro = os.environ.get("WSL_DISTRO_NAME", "Ubuntu")
    args = f"-d {distro} --cd {ROOT} -- bash ./scripts/daily.sh {a.brand}"
    r = ps(f"$a = New-ScheduledTaskAction -Execute 'wsl.exe' -Argument \"{args}\"; "
           f"$t = New-ScheduledTaskTrigger -Daily -At '{a.time}'; "
           "$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
           "-ExecutionTimeLimit (New-TimeSpan -Minutes 30); "
           f"Register-ScheduledTask -TaskPath '{path}' -TaskName '{name}' -Action $a -Trigger $t -Settings $s -Force | Out-Null")
    if r.returncode != 0:
        sys.exit(f"Could not create the scheduled task:\n{r.stderr[-1500:]}")
    print(f"Every day at {a.time} Claude will prepare a draft for brand '{a.brand}' and notify you.")
    print("Nothing is posted until you run /review in Claude Code and approve it.")


if __name__ == "__main__":
    main()
