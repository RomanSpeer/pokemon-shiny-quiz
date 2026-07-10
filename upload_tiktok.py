"""Upload a video to TikTok via the Content Posting API (Direct Post).

Requires env vars: TT_CLIENT_KEY, TT_CLIENT_SECRET, TT_REFRESH_TOKEN.
See get_tiktok_refresh_token.py for how to obtain the refresh token once.

Set TT_PRIVACY_LEVEL to override the default. While the app is unaudited,
only SELF_ONLY (private draft in your own inbox) is allowed - that's what
you'd use for the sandbox demo recording. PUBLIC_TO_EVERYONE only works
once the video.publish scope has been approved in the audit.

Uses a single-chunk upload (source_info.total_chunk_count=1), which TikTok
allows for videos up to 64MB - comfortably covers these ~20-40s Shorts. If
videos ever grow past that, this would need real chunked upload instead.
"""
from __future__ import annotations

import argparse
import os
import random
from pathlib import Path

import requests

TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"

# Same "viral" copy style as the YouTube variants, trimmed to TikTok's
# caption conventions. Doesn't reveal the Pokémon to keep the guessing hook.
VARIANTS = [
    "Who's That Pokémon? Guess before time runs out! ⏱️ #Pokemon #PokemonQuiz #WhosThatPokemon",
    "Only a TRUE Pokémon Master can guess this! ⚡️ #Pokemon #PokemonQuiz #Gaming",
    "Guess the Pokémon in 7 Seconds! 🔥 #Pokemon #Quiz #Nintendo",
    "Can YOU name this Pokémon? 🧠 #Pokemon #PokemonQuiz #Trivia",
]
MUSIC_CREDIT = " 🎵 Music by @CinderyLofi"


def _get_access_token() -> str:
    resp = requests.post(
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": os.environ["TT_CLIENT_KEY"],
            "client_secret": os.environ["TT_CLIENT_SECRET"],
            "grant_type": "refresh_token",
            "refresh_token": os.environ["TT_REFRESH_TOKEN"],
        },
        timeout=15,
    )
    data = resp.json()
    if "access_token" not in data:
        raise RuntimeError(f"Token refresh failed: {data}")
    return data["access_token"]


def upload(video_path: str) -> None:
    access_token = _get_access_token()
    video_bytes = Path(video_path).read_bytes()
    caption = random.choice(VARIANTS) + MUSIC_CREDIT
    privacy_level = os.environ.get("TT_PRIVACY_LEVEL", "SELF_ONLY")

    init_resp = requests.post(
        INIT_URL,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json={
            "post_info": {
                "title": caption,
                "privacy_level": privacy_level,
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": len(video_bytes),
                "chunk_size": len(video_bytes),
                "total_chunk_count": 1,
            },
        },
        timeout=15,
    )
    init_resp.raise_for_status()
    init_data = init_resp.json()["data"]
    publish_id = init_data["publish_id"]
    upload_url = init_data["upload_url"]

    put_resp = requests.put(
        upload_url,
        headers={
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{len(video_bytes) - 1}/{len(video_bytes)}",
        },
        data=video_bytes,
        timeout=120,
    )
    put_resp.raise_for_status()

    print(f"TikTok upload initiated: publish_id={publish_id}, privacy_level={privacy_level}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload video to TikTok via Content Posting API")
    parser.add_argument("--video", required=True, help="Path to video file")
    args = parser.parse_args()
    upload(args.video)
