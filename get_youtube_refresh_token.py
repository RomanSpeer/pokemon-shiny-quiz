"""One-time local helper to obtain a YouTube refresh token.

1. In Google Cloud Console, enable the "YouTube Data API v3" and create an
   OAuth 2.0 Client ID of type "Desktop app". Download the JSON and save it
   as client_secret.json next to this script.
2. Run: python get_youtube_refresh_token.py
3. Sign in with the Google account that owns the target YouTube channel and
   grant access.
4. Copy the three printed values into the repo's GitHub Secrets as
   YT_CLIENT_ID, YT_CLIENT_SECRET and YT_REFRESH_TOKEN.
"""
from google_auth_oauthlib.flow import InstalledAppFlow

# youtube.force-ssl is needed in addition to youtube.upload so the token can
# also add uploaded videos to a playlist (YT_PLAYLIST_ID).
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

if __name__ == "__main__":
    flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
    credentials = flow.run_local_server(port=0)

    print("YT_CLIENT_ID:", credentials.client_id)
    print("YT_CLIENT_SECRET:", credentials.client_secret)
    print("YT_REFRESH_TOKEN:", credentials.refresh_token)
