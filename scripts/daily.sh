#!/usr/bin/env bash
# Run by Windows Task Scheduler (see ./sa schedule-daily). Claude drafts today's post; it cannot publish:
# publishing is not in the allowed tools, and in headless mode anything not allowed is refused.
set -uo pipefail
cd "$(dirname "$0")/.."
BRAND="${1:-main}"
LOG=drafts/_daily.log
mkdir -p drafts
export PATH="$HOME/.local/bin:$PATH"
CLAUDE="$(command -v claude || echo "$HOME/.local/bin/claude")"
echo "=== $(date '+%F %T') daily draft for brand '$BRAND'" >> "$LOG"
"$CLAUDE" -p "/daily-post $BRAND" --permission-mode acceptEdits \
  --allowedTools "Read" "Glob" "Grep" "Bash(./sa render-image *)" "Bash(./sa slideshow *)" \
                 "Bash(./sa drafts *)" "Bash(./sa accounts)" "Bash(./sa probe *)" "Bash(./sa frames *)" \
  >> "$LOG" 2>&1
status=$?
if [ $status -eq 0 ]; then
  ./sa notify "Social agent" "Today's post draft is ready. Open Claude Code and run /review to approve it."
else
  ./sa notify "Social agent" "Daily draft failed - see drafts/_daily.log"
fi
exit $status
