---
name: daily-post
description: Prepare today's social media draft for a brand from its daily plan. Never publishes - the user approves later with /review. Run by the daily scheduler or by hand.
argument-hint: "[brand, default main]"
disable-model-invocation: true
---
Brand: $ARGUMENTS (empty means `main`)

You may be running unattended. **Do not ask questions. Never run `./sa publish`.**

1. Read `brands/<brand>/brand.md`. If it still contains `TODO`, stop and say:
   "Fill in brands/<brand>/brand.md first." Read `CLAUDE.md` for the draft format.
2. Run `./sa drafts list` — if a daily draft for this brand from today is already waiting, stop.
   Run `./sa drafts history --days 45` and avoid repeating recent topics.
3. Pick today's post from the brand's **Daily plan** (rotate content pillars and formats; use the weekday rule
   if one is given).
4. `./sa drafts new <image|slideshow> "<title>" --brand <brand>`.
5. Create the media yourself following `.claude/agents/designer.md`:
   - image post: one 1080x1350 HTML → `./sa render-image <file> --size 1080x1350`, media = the .jpg
   - slideshow (Reel/Short): 4–7 slides at 1080x1920 in `slides/`, then `./sa slideshow <draft>`
     (add `--music` if the brand has a track in `brands/<brand>/music/`), media = `final.mp4`
   Read the rendered image/preview and fix overflow, cut-off or hard-to-read text before moving on.
6. Write `draft.json`: targets from the brand's **Daily targets**, captions per platform in the brand voice,
   `alt_text`, `topic`, `source: "daily"`, `status: "pending"`.
7. `./sa drafts check <draft>` and fix problems (if a target's account isn't connected, drop that target
   and note it). Finish with one line: the draft folder and title.
