"""Upload a video to YouTube as a Short.

Requires env vars: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN.
See get_youtube_refresh_token.py for how to obtain the refresh token once.
"""
import argparse
import os
import random

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Jeder Upload wählt zufällig eine Variante, für etwas Abwechslung.
VARIANTS = [
    {
        "title": "Guess the Shiny Pokémon! ✨🔥 #Shorts",
        "description": (
            "Kannst du das shiny Pokémon erraten, bevor die Zeit abläuft? "
            "#Shorts #Pokemon #Shiny #Quiz"
        ),
        "tags": ["Pokemon", "Shiny", "Shorts", "Quiz"],
    },
    {
        "title": "Only a TRUE Pokémon fan can guess this! ⚡️ #Shorts",
        "description": (
            "Errätst du das shiny Pokémon schneller als der Timer? "
            "#Shorts #Pokemon #PokemonQuiz #Shiny #Gaming"
        ),
        "tags": ["Pokemon", "PokemonQuiz", "Shorts", "Shiny", "Gaming"],
    },
    {
        "title": "Shiny Pokémon Quiz - How fast can YOU guess? 🎮",
        "description": (
            "Neue Runde, neues shiny Pokémon! Schreib deinen Tipp in die "
            "Kommentare. #Shorts #Pokemon #Shiny #Quiz #Nintendo"
        ),
        "tags": ["Pokemon", "Shiny", "Quiz", "Shorts", "Nintendo"],
    },
    {
        "title": "Can you name this Shiny Pokémon in 3 seconds? ⏱️",
        "description": (
            "Shiny Pokémon Ratespiel – testet dein Wissen! "
            "#Shorts #Pokemon #Shiny #PokemonQuiz"
        ),
        "tags": ["Pokemon", "Shiny", "PokemonQuiz", "Shorts"],
    },
]
CATEGORY_ID = "24"  # Entertainment


def upload(video_path: str) -> None:
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
    )
    youtube = build("youtube", "v3", credentials=creds)

    variant = random.choice(VARIANTS)
    body = {
        "snippet": {
            "title": variant["title"],
            "description": variant["description"],
            "tags": variant["tags"],
            "categoryId": CATEGORY_ID,
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload-Fortschritt: {int(status.progress() * 100)}%")

    print(f"YouTube-Video hochgeladen: https://youtube.com/watch?v={response['id']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload video to YouTube Shorts")
    parser.add_argument("--video", required=True, help="Path to video file")
    args = parser.parse_args()
    upload(args.video)
