---
name: social
description: Social media agent. Use when the user wants to create, edit, schedule or publish a social media post - e.g. "make a post about X", "edit this raw video and post it", "post this image to Instagram and Facebook", "turn this into a Reel/Short", "make a YouTube community post". Handles images, videos (raw footage editing), slideshow videos, text and community posts, and always gets the user's approval before publishing.
argument-hint: "[what to post, e.g. 'edit inbox/talk.mp4 for IG + YouTube' or 'a tip post about X']"
---
# Create → (edit) → approve → publish

Request: $ARGUMENTS

Follow CLAUDE.md (golden rules, draft format, commands). Work from the project root.

## 1. Understand the request
Work out, asking only for what you can't infer:
- **What**: a file the user gave (raw video / finished video / image), an idea to create from scratch, or text only.
  Windows paths `C:\...` → `/mnt/c/...`. Files dropped in `inbox/` count as "given".
- **Where**: run `./sa accounts`. Use the platforms/accounts the user named, else the brand's
  *Default targets* in `brands/<brand>/brand.md`. Explain if a wanted platform isn't connected
  (give the `./sa connect ...` command) and continue with the rest.
- **Edit?** Raw/long footage, or the user asked for edits → step 3a. A finished clip to post as-is → skip editing.

## 2. Start a draft
`./sa drafts new <video|image|text|slideshow> <short title> [--brand <brand>]` prints `drafts/<id>`.
Everything for this post goes in that folder.

## 3. Make the media
a) **Raw video** → use the **video-editor** subagent. Give it: source path, draft folder, brand, target
   platforms, the user's brief. It returns `final.mp4`, `preview.jpg` and notes on what it cut.
b) **Image from an idea** (tip, quote, announcement, offer) → **designer** subagent, 1080x1350 for feeds.
c) **Video without footage** → designer makes `slides/01.html…` at 1080x1920, then
   `./sa slideshow <draft> [--music brands/<brand>/music/<file>]`.
d) **User's own image** → post as-is if it already fits (Instagram needs JPEG, 4:5–1.91:1); otherwise the
   designer crops/brands it. **User's finished video** → `./sa probe`; only re-render if specs don't fit.
e) **Text only** → no media (Instagram and YouTube video can't take text-only posts).

Look at the result yourself (Read `preview.jpg` / `post.jpg`). Fix anything off before showing the user.

## 4. Write the post
Fill `draft.json`: `media`, `alt_text`, `topic`, `source: "user"`, and one target per platform+account,
written for that platform in the brand's voice:
- **instagram**: strong first line (hook), short paragraphs, call to action, 3–8 relevant hashtags at the end.
- **facebook**: conversational, 0–3 hashtags.
- **linkedin**: professional, insight-first, short lines, 3–5 hashtags, no clickbait.
- **youtube**: `title` ≤100 chars (no `<` `>`), `description` with 2–3 hashtags (#Shorts if vertical ≤3 min), `tags`.
- **youtube_community**: short and conversational; a question works well.
Set `status` to `"pending"`, then `./sa drafts check <draft>` and fix every problem it lists.

## 5. Approval (never skip)
Show the user: links to the media and preview (e.g. `[final.mp4](drafts/<id>/final.mp4)`), each target's
caption/title, and any warnings. Then ask with AskUserQuestion — options: **Post now**, **Schedule**,
**Change something**, **Discard**.
- Change → apply it, re-render if needed, re-check, show again, ask again.
- Discard → `./sa drafts reject <draft>`.
- Schedule → get the date/time (their PC's local time) → `./sa publish <draft> --at "YYYY-MM-DD HH:MM"`.
- Post now → `./sa publish <draft>`.
Mention that Claude Code will show one more permission prompt — that's the final safety lock.

## 6. After publishing
Report each target with its link or the error in plain words. Failed → explain the fix; ask before running
publish again (it only retries what failed). Assisted targets (youtube_community, facebook_profile) →
walk the user through the printed steps; when they say it's posted, run
`./sa drafts mark-posted <draft> <platform:account> [post-url]`.
