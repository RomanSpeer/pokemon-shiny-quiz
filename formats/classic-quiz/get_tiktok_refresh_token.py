"""One-time local helper to obtain a TikTok refresh token (for sandbox testing
and, later, the automated posting workflow).

1. In the TikTok Developer Portal, make sure your app has:
   - Login Kit enabled, with this exact redirect URI registered:
     https://romanspeer.github.io/pokemon-quiz-video/oauth-callback
   - Content Posting API enabled, with "Direct Post" turned on.
   - Your own TikTok account added as a Sandbox target user (App details ->
     Sandbox tab) - required since the app isn't audited yet, otherwise the
     authorization step will be rejected.
2. Run: python get_tiktok_refresh_token.py
   (it will ask for your Client Key/Secret, or set TT_CLIENT_KEY /
   TT_CLIENT_SECRET as env vars to skip the prompts)
3. Open the printed URL, log in with the TikTok account you added as a
   sandbox tester, and approve access.
4. TikTok redirects to the oauth-callback.html page, which displays a
   `code` value on screen. Paste that code back into this script's prompt.
5. The script exchanges it for tokens and prints TT_CLIENT_KEY,
   TT_CLIENT_SECRET and TT_REFRESH_TOKEN - copy those into GitHub Secrets
   once you're ready to automate (see upload_tiktok.py).
"""
from __future__ import annotations

import os
import secrets
import urllib.parse

import requests

REDIRECT_URI = "https://romanspeer.github.io/pokemon-quiz-video/oauth-callback"
SCOPES = "user.info.basic,video.upload,video.publish"

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"


def main() -> None:
    client_key = os.environ.get("TT_CLIENT_KEY") or input("TikTok Client Key: ").strip()
    client_secret = os.environ.get("TT_CLIENT_SECRET") or input("TikTok Client Secret: ").strip()

    state = secrets.token_urlsafe(16)
    params = {
        "client_key": client_key,
        "scope": SCOPES,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "state": state,
    }
    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    print("\n1. Open this URL, log in with your sandbox-tester TikTok account, and approve access:\n")
    print(auth_url)
    print(f"\n2. You'll land on {REDIRECT_URI} showing a 'code' value - copy it.\n")

    code = input("Paste the code here: ").strip()

    resp = requests.post(
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        },
        timeout=15,
    )
    data = resp.json()
    if "access_token" not in data:
        raise RuntimeError(f"Token exchange failed: {data}")

    print("\nSuccess! Store these as GitHub Secrets:\n")
    print("TT_CLIENT_KEY:", client_key)
    print("TT_CLIENT_SECRET:", client_secret)
    print("TT_REFRESH_TOKEN:", data["refresh_token"])
    print(
        f"\n(access_token expires in {data['expires_in']}s, refresh_token in "
        f"{data['refresh_expires_in']}s - upload_tiktok.py uses the refresh "
        "token to mint a fresh access token on every run.)"
    )


if __name__ == "__main__":
    main()
