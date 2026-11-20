"""Show a Windows notification (from WSL or Windows).

Usage: ./sa notify "<title>" "<message>"
"""
import subprocess
import sys

from common import is_wsl


def notify(title: str, message: str) -> None:
    q = lambda s: s.replace("'", "''")
    script = ("Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; "
              "$n = New-Object System.Windows.Forms.NotifyIcon; $n.Icon = [System.Drawing.SystemIcons]::Information; "
              f"$n.BalloonTipTitle = '{q(title)}'; $n.BalloonTipText = '{q(message)}'; $n.Visible = $true; "
              "$n.ShowBalloonTip(10000); Start-Sleep -Seconds 8; $n.Dispose()")
    exe = "powershell.exe" if is_wsl() or sys.platform == "win32" else None
    if exe:
        subprocess.run([exe, "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, timeout=30)
    else:
        print(f"[{title}] {message}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    notify(sys.argv[1], sys.argv[2])
