---
name: review
description: Review social media drafts waiting for the user (daily drafts, scheduled posts, failed or assisted posts) and publish the ones they approve.
---
1. `./sa drafts list`. If nothing is waiting, say so and stop.
2. Take drafts one at a time, oldest first. For each: `./sa drafts show <draft>`, Read its preview / image,
   then show the user the media links, every target's caption/title and any problems from
   `./sa drafts check <draft>`.
3. Ask with AskUserQuestion, depending on status:
   - **pending** → Post now / Schedule / Change something / Skip for now / Discard
   - **scheduled** → Keep schedule / Post now instead / Cancel schedule (`./sa publish <draft> --cancel`)
   - **needs_check** → a platform may have posted without confirming. Ask the user to look at that
     account: live → `./sa drafts mark-posted <draft> <platform:account> [url]`; not live →
     `./sa drafts reset <draft> <platform:account>`, then retry (needs approval). Never retry blindly.
   - **partial / failed** → show the errors; Retry failed ones / Change something / Discard
   - **awaiting_manual** → "Did you post it?" → `./sa drafts mark-posted <draft> <platform:account> [url]`,
     or redo the assisted step with `./sa publish <draft> --only <platform:account>`
4. Then act exactly as in `.claude/skills/social/SKILL.md` steps 5–6 (approval is required for every
   publish; the permission prompt is the final lock). Finish with a short summary of what was posted.
