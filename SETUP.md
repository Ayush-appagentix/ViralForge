# Social agent — setup and use

The agent is Claude Code itself, working in this folder. There's no app, server or website.
Everything below is one-time setup. Steps 3–5 cover the platforms; do only the ones you want.

## 1. Open it
VS Code connected to WSL → **File → Open Folder → `/mnt/c/Users/Admin/social-agent`** → open the Claude Code panel.
(Or in the WSL terminal: `cd /mnt/c/Users/Admin/social-agent && claude`.)

Already installed on this PC: FFmpeg (`~/.local/bin`) and the Python environment (`~/.venvs/social-agent`).
On a new PC, run this from the folder: `uv venv ~/.venvs/social-agent && VIRTUAL_ENV=~/.venvs/social-agent uv pip install -r requirements.txt`,
and install FFmpeg (`sudo apt install ffmpeg`).

## 2. Your brand
- Fill in every `TODO` in `brands/main/brand.md` (voice, colours, hashtags, default accounts, daily plan).
- Put your logo at `brands/main/logo.png` (transparent PNG). Optional: fonts in `brands/main/fonts/`, music in `brands/main/music/`.
- More brands or clients: copy the folder to `brands/<name>/`.
- Copy `.env.example` to `.env` (you'll paste app keys into it below).

## 3. Facebook Page + Instagram (free, Meta Graph API)
1. Instagram must be a **Business or Creator** account (Instagram app → Settings → Account type; switching is free)
   and **linked to your Facebook Page** (Page settings → Linked accounts → Instagram).
   Meta's API can't post to personal Facebook profiles. For those, the agent uses "assisted" mode:
   it prepares the post and you click Post.
2. Go to https://developers.facebook.com/apps/creation/ and create an app. Pick the use cases for managing a Page and
   Instagram content. If they aren't listed, pick "Other" → "Business". You can skip the business portfolio.
3. Leave the app in **Development mode**. Because you're the app admin, posting to Pages and Instagram accounts you
   manage needs **no App Review**.
4. Go to App settings → Basic and copy the **App ID** and **App secret** into `.env` (`META_APP_ID`, `META_APP_SECRET`).
5. In the WSL terminal, in this folder, run: `./sa connect meta`. It walks you through the rest and saves every Page you
   pick, plus its Instagram account, under a short name.
   - Client accounts: ask the client to give you a role on their Page (Page settings → Page access), then run
     `./sa connect meta` again.

## 4. YouTube (free, YouTube Data API)
1. Go to https://console.cloud.google.com and create a project. Then go to **APIs & Services → Library** and enable
   **YouTube Data API v3**.
2. Set up the **OAuth consent screen** (Google Auth Platform): user type External, add your Google account as a test user,
   then **Publish app** (set it to "In production"). Otherwise your login expires every 7 days. Google shows an
   "unverified app" warning when you sign in; click Advanced → continue. That's fine for your own use.
3. Go to **Credentials → Create credentials → OAuth client ID → Desktop app**, then download the JSON and save it as
   `secrets/google_client_secret.json`. In Windows that's `C:\Users\Admin\social-agent\secrets\`.
4. Run: `./sa connect youtube --alias personal`. Run it once per channel. For a brand or client channel, pick that
   channel when Google asks.
- Videos and Shorts upload automatically. Vertical or square videos up to 3 minutes become Shorts.
- **Community posts:** YouTube has no API for these, so they're assisted. The agent copies the text to your clipboard
  and opens your channel's Posts tab; you paste and click Post.

## 5. LinkedIn personal profile (free)
1. Go to https://www.linkedin.com/developers/apps and create an app. If it asks for a LinkedIn Page, any Page you
   administer works.
2. In the **Products** tab, add **Share on LinkedIn** and **Sign In with LinkedIn using OpenID Connect**.
3. In the **Auth** tab, copy the Client ID and Client secret into `.env`, and add the redirect URL
   `http://localhost:8765/callback`.
4. Run: `./sa connect linkedin --alias me`. The login lasts 60 days; run the command again to renew.

**Company page (e.g. AutomateFinance):** posting *as the Page* through the API needs LinkedIn's
**Community Management API**, a reviewed product only for registered legal organisations (business email
and Page super-admin verification, applied for on a *separate, new* developer app). Until that's approved,
use the `linkedin_page` target: Claude prepares the post, copies it to your clipboard and opens the Page's
admin view — you click Post. Target: `{"platform": "linkedin_page", "account": "<Page ID>", "caption": "..."}`.

Check what's connected at any time with `./sa accounts`.

## 6. Daily drafts (optional)
After `brands/main/brand.md` is filled in, run `./sa schedule-daily 09:00`.
Every day at 09:00, Claude prepares a post and shows a Windows notification. **It never posts on its own.**
Open Claude Code and type `/review` to approve, change, schedule or discard it.
Use `./sa schedule-daily --status` to check it, `--run-now` to test it, and `--off` to stop it.

## Using the agent (just talk to it in Claude Code)
- "Edit `inbox/raw-talk.mp4` into a 40-second Reel and post it to Instagram and YouTube"
- "Make an image post about our weekend offer for Facebook, Instagram and LinkedIn"
- "Make a 5-slide Short with 3 tips about X"
- "Post this photo `C:\Users\Admin\Pictures\team.jpg` to the acme Instagram tomorrow at 6 pm"
- "Make a YouTube community post asking my audience which topic they want next"
- Shortcuts: `/social <anything>`, `/edit-video <file> <notes>`, `/review`, `/daily-post`

Every post goes like this:
1. Claude makes and checks the draft.
2. It shows you the media and captions.
3. You choose **Post now / Schedule / Change / Discard**.
4. Claude Code asks you once more before publishing. That's the safety lock.

Drop raw files in `inbox/`. Drafts live in `drafts/`, and posted ones move to `posted/`.

## Good to know
- Scheduled posts use Windows Task Scheduler. Your PC must be on at that time; if it's off, the post goes out as soon
  as the PC is back on.
- If Instagram image posts ever fail with an image-URL error, add `IG_IMAGE_HOST=litterbox` to `.env`. That uses a free
  temporary public host instead.
- New platform: add one file to `scripts/platforms/` and ask Claude to write it. The format is described in
  `scripts/platforms/__init__.py`.
