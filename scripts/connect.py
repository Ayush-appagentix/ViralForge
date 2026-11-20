"""Connect your social accounts. Run this YOURSELF in the terminal (it asks for logins):

  ./sa connect meta [--alias NAME]       Facebook Pages + the Instagram accounts linked to them
  ./sa connect youtube [--alias NAME]    a YouTube channel (sign in with the Google account that owns it)
  ./sa connect linkedin [--alias NAME]   your LinkedIn profile

Connect as many accounts as you like (yours, clients'); each gets a short alias such as
"personal" or "acme". Logins are stored in secrets/ - never share that folder.
See SETUP.md for the one-time developer-app steps each platform needs first.
"""
from __future__ import annotations

import argparse
import getpass
import http.server
import json
import os
import secrets as pysecrets
import sys
import time
from urllib.parse import parse_qs, quote, urlencode, urlparse

import requests

from common import SECRETS, PublishError, env, is_wsl, open_url, save_account, slug

from platforms import _meta as meta
from platforms.youtube import SCOPES as YT_SCOPES


def ask_alias(default: str, given: str | None) -> str:
    if given:
        return slug(given)
    return slug(input(f"Short name for this account [{default}]: ").strip() or default)


# ---------- Meta (Facebook Pages + Instagram) ----------

def connect_meta(alias_arg: str | None) -> None:
    app_id, app_secret = env("META_APP_ID"), env("META_APP_SECRET")
    if not (app_id and app_secret):
        sys.exit("Add META_APP_ID and META_APP_SECRET to .env first (SETUP.md, step 3).")
    print("""
1. Graph API Explorer is opening in your browser.
2. Top right: choose your app. Under "User or Page" choose "Get User Access Token".
3. Add these permissions:
     pages_show_list, pages_read_engagement, pages_manage_posts,
     instagram_basic, instagram_content_publish
   (also business_management if your Page lives in a Meta Business portfolio)
4. Click "Generate Access Token", allow access to the Pages / Instagram accounts you want,
   then copy the token and paste it below.""")
    open_url("https://developers.facebook.com/tools/explorer/")
    short = getpass.getpass("Paste the token (hidden): ").strip()
    r = requests.get(meta.url("oauth/access_token"), timeout=60, params={
        "grant_type": "fb_exchange_token", "client_id": app_id, "client_secret": app_secret,
        "fb_exchange_token": short})
    long_lived = meta.check(r)
    user_token = long_lived["access_token"]
    user_expires = time.time() + int(long_lived.get("expires_in", 60 * 86400))
    pages = meta.get("me/accounts", user_token, limit=100,
                     fields="id,name,access_token,instagram_business_account{id,username}").get("data", [])
    if not pages:
        sys.exit("No Facebook Pages found for this login. Check you selected your Pages when generating the token.")
    print("\nPages found:")
    for i, p in enumerate(pages, 1):
        ig = p.get("instagram_business_account")
        print(f"  {i}. {p['name']}   Instagram: {'@' + ig['username'] if ig else 'none linked'}")
    pick = input("Which to connect? e.g. 1,3 or 'all' [all]: ").strip().lower() or "all"
    chosen = pages if pick == "all" else [pages[int(x) - 1] for x in pick.split(",") if x.strip().isdigit()]
    for p in chosen:
        alias = ask_alias(slug(p["name"]), alias_arg if len(chosen) == 1 else None)
        save_account("facebook", alias, {"page_id": p["id"], "page_name": p["name"],
                                         "page_token": p["access_token"], "connected_at": time.time()})
        print(f"  saved facebook:{alias}")
        ig = p.get("instagram_business_account")
        if not ig:
            continue
        token, kind, expires = p["access_token"], "page", None
        try:
            meta.get(ig["id"], token, fields="username")
        except PublishError:
            token, kind, expires = user_token, "user", user_expires
        save_account("instagram", alias, {"ig_user_id": ig["id"], "username": ig.get("username"),
                                          "page_id": p["id"], "page_token": p["access_token"],
                                          "token": token, "token_kind": kind, "expires_at": expires,
                                          "connected_at": time.time()})
        print(f"  saved instagram:{alias} (@{ig.get('username')})")
    print("\nDone. Check with: ./sa accounts")


# ---------- YouTube ----------

def connect_youtube(alias_arg: str | None) -> None:
    client_file = SECRETS / "google_client_secret.json"
    if not client_file.exists():
        sys.exit("Save your Google OAuth client file as secrets/google_client_secret.json first (SETUP.md, step 4).")
    if is_wsl():
        os.environ["BROWSER"] = "explorer.exe"
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    print("A Google sign-in page will open. Pick the Google account - and, if asked, the channel "
          "(brand account) - you want to post as.")
    flow = InstalledAppFlow.from_client_secrets_file(str(client_file), YT_SCOPES)
    creds = flow.run_local_server(host="localhost", port=8766, open_browser=True, prompt="consent",
                                  authorization_prompt_message="If no browser opened, visit:\n{url}\n",
                                  success_message="Connected - you can close this tab and return to the terminal.")
    if not creds.refresh_token:
        sys.exit("Google did not return a refresh token. Remove the app's access at "
                 "https://myaccount.google.com/permissions and run this again.")
    items = build("youtube", "v3", credentials=creds, cache_discovery=False).channels() \
        .list(part="snippet", mine=True).execute().get("items", [])
    if not items:
        sys.exit("This Google account has no YouTube channel.")
    ch = items[0]
    handle = ch["snippet"].get("customUrl")
    alias = ask_alias(slug(handle or ch["snippet"]["title"]), alias_arg)
    save_account("youtube", alias, {"channel_id": ch["id"], "title": ch["snippet"]["title"], "handle": handle,
                                    "token": json.loads(creds.to_json()), "connected_at": time.time()})
    print(f"Saved youtube:{alias} -> {ch['snippet']['title']} ({handle})")


# ---------- LinkedIn ----------

def wait_for_code(port: int, state: str, timeout: int = 300) -> str:
    result: dict = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = parse_qs(urlparse(self.path).query)
            if q.get("state", [""])[0] == state and "code" in q:
                result["code"] = q["code"][0]
                msg = "Connected - you can close this tab and return to the terminal."
            else:
                result["error"] = q.get("error_description", q.get("error", ["unknown error"]))[0]
                msg = f"LinkedIn sign-in failed: {result['error']}"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"<h2>{msg}</h2>".encode())

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    server.timeout = 5
    deadline = time.time() + timeout
    while not result and time.time() < deadline:
        server.handle_request()
    server.server_close()
    if "code" not in result:
        sys.exit(f"LinkedIn sign-in did not complete: {result.get('error', 'timed out')}")
    return result["code"]


def connect_linkedin(alias_arg: str | None) -> None:
    cid, csecret = env("LINKEDIN_CLIENT_ID"), env("LINKEDIN_CLIENT_SECRET")
    if not (cid and csecret):
        sys.exit("Add LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET to .env first (SETUP.md, step 5).")
    port = 8765
    redirect = f"http://localhost:{port}/callback"
    state = pysecrets.token_urlsafe(16)
    open_url("https://www.linkedin.com/oauth/v2/authorization?" + urlencode({
        "response_type": "code", "client_id": cid, "redirect_uri": redirect, "state": state,
        "scope": "openid profile w_member_social"}, quote_via=quote))
    code = wait_for_code(port, state)
    tok = requests.post("https://www.linkedin.com/oauth/v2/accessToken", timeout=60, data={
        "grant_type": "authorization_code", "code": code, "client_id": cid, "client_secret": csecret,
        "redirect_uri": redirect})
    if not tok.ok:
        sys.exit(f"LinkedIn token exchange failed: {tok.text[:300]}")
    tok = tok.json()
    me = requests.get("https://api.linkedin.com/v2/userinfo", timeout=60,
                      headers={"Authorization": f"Bearer {tok['access_token']}"}).json()
    alias = ask_alias(slug(me.get("name", "me")), alias_arg)
    save_account("linkedin", alias, {"person_urn": f"urn:li:person:{me['sub']}", "name": me.get("name"),
                                     "access_token": tok["access_token"],
                                     "expires_at": time.time() + int(tok.get("expires_in", 60 * 86400)),
                                     "connected_at": time.time()})
    print(f"Saved linkedin:{alias} -> {me.get('name')} (login lasts 60 days; run this again to renew)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("platform", choices=["meta", "youtube", "linkedin"])
    ap.add_argument("--alias")
    a = ap.parse_args()
    {"meta": connect_meta, "youtube": connect_youtube, "linkedin": connect_linkedin}[a.platform](a.alias)
