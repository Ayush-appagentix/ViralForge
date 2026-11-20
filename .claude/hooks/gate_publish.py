#!/usr/bin/env python3
"""Safety lock: any shell command that could publish to social media must be approved by the human,
whatever permission mode Claude Code is in."""
import json
import re
import sys

PUBLISH = re.compile(
    r"\bsa\s+publish\b|scripts/publish\.py|graph\.facebook\.com|rupload\.facebook\.com"
    r"|api\.linkedin\.com|googleapis\.com/upload|youtube/v3/videos",
    re.IGNORECASE,
)

try:
    command = json.load(sys.stdin).get("tool_input", {}).get("command", "")
except (ValueError, AttributeError):
    sys.exit(0)

if PUBLISH.search(command or ""):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": "This publishes to social media. Allow only if you approved this exact draft.",
    }}))
sys.exit(0)
