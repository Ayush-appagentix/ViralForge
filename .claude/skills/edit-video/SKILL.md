---
name: edit-video
description: Edit a raw video like a professional short-form editor (cut filler and silences, strong hook, 9:16 reframe, captions, logo, music), then get approval and post it. Use when the user hands over raw footage.
argument-hint: "<video path> [platforms] [notes, e.g. 'under 45s, punchy, no music']"
---
Raw video and brief: $ARGUMENTS

Read `.claude/skills/social/SKILL.md` and follow it, taking the **raw video** path in step 3a: hand the
footage to the **video-editor** subagent with the brief above. If no platforms were named, use the brand's
default targets. Approval in step 5 is mandatory before anything is published.
