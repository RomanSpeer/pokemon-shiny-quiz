"""Upload a video to YouTube as a Short.

Requires env vars: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN.
Optional env var: YT_PLAYLIST_ID (or YT_STAT_PLAYLIST_ID for --format stat) -
if set, the uploaded video is added to that playlist (requires the refresh
token to include the youtube.force-ssl scope, not just youtube.upload).
See get_youtube_refresh_token.py for how to obtain the refresh token once.
"""
import argparse
import os
import random

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Each upload randomly picks a variant, for some variety.
VARIANTS = [
    {
        "title": "Guess the Shiny Pokémon! ✨🔥 #Shorts",
        "description": (
            "Can you guess which Pokémon is the Shiny one before time runs out? "
            "Comment your guess before the reveal! "
            "#Shorts #Pokemon #Shiny #Quiz"
        ),
        "tags": ["Pokemon", "Shiny", "Shorts", "Quiz"],
    },
    {
        "title": "Only a TRUE Pokémon fan can guess this! ⚡️ #Shorts",
        "description": (
            "Can you guess the shiny Pokémon faster than the timer? "
            "Drop your answer in the comments! "
            "#Shorts #Pokemon #PokemonQuiz #Shiny #Gaming"
        ),
        "tags": ["Pokemon", "PokemonQuiz", "Shorts", "Shiny", "Gaming"],
    },
    {
        "title": "Shiny Pokémon Quiz - How fast can YOU guess? 🎮",
        "description": (
            "New round, new shiny Pokémon! Drop your guess in the comments "
            "before time runs out. "
            "#Shorts #Pokemon #Shiny #Quiz #Nintendo"
        ),
        "tags": ["Pokemon", "Shiny", "Quiz", "Shorts", "Nintendo"],
    },
    {
        "title": "Can you name this Shiny Pokémon in 3 seconds? ⏱️",
        "description": (
            "Shiny Pokémon guessing game - put your knowledge to the test! "
            "Comment your guess below. "
            "#Shorts #Pokemon #Shiny #PokemonQuiz"
        ),
        "tags": ["Pokemon", "Shiny", "PokemonQuiz", "Shorts"],
    },
]

STAT_VARIANTS = [
    {
        "title": "Who has more Speed? Pokémon Stat Battle! ⚔️ #Shorts",
        "description": (
            "Can you guess which Pokémon wins the stat battle? "
            "Comment your pick before the reveal! "
            "#Shorts #Pokemon #PokemonQuiz #Stats"
        ),
        "tags": ["Pokemon", "PokemonQuiz", "Shorts", "Stats", "Gaming"],
    },
    {
        "title": "Pokémon Stat Showdown - Who Wins? 📊 #Shorts",
        "description": (
            "Guess which Pokémon has the higher stat before the reveal! "
            "Drop your answer in the comments. "
            "#Shorts #Pokemon #PokemonQuiz #Stats"
        ),
        "tags": ["Pokemon", "PokemonQuiz", "Stats", "Shorts", "Nintendo"],
    },
    {
        "title": "Test Your Pokédex Knowledge! Stat Battle 🎮 #Shorts",
        "description": (
            "Two Pokémon, one hidden stat - can you call the winner? "
            "Comment your guess below! "
            "#Shorts #Pokemon #PokemonQuiz #Stats"
        ),
        "tags": ["Pokemon", "PokemonQuiz", "Stats", "Shorts", "Gaming"],
    },
]
CATEGORY_ID = "24"  # Entertainment

# Required by the music license (CinderyLofi allows free use, credit required).
MUSIC_CREDIT = "Music: @CinderyLofi (https://www.youtube.com/@CinderyLofi)"


def upload(video_path: str, format_: str = "shiny") -> None:
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
    )
    youtube = build("youtube", "v3", credentials=creds)

    variant = random.choice(STAT_VARIANTS if format_ == "stat" else VARIANTS)
    description = f"{variant['description']}\n\n{MUSIC_CREDIT}"
    body = {
        "snippet": {
            "title": variant["title"],
            "description": description,
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
            print(f"Upload progress: {int(status.progress() * 100)}%")

    video_id = response["id"]
    print(f"YouTube video uploaded: https://youtube.com/watch?v={video_id}")

    playlist_env = "YT_STAT_PLAYLIST_ID" if format_ == "stat" else "YT_PLAYLIST_ID"
    playlist_id = os.environ.get(playlist_env)
    if playlist_id:
        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id},
                }
            },
        ).execute()
        print(f"Added to playlist {playlist_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload video to YouTube Shorts")
    parser.add_argument("--video", required=True, help="Path to video file")
    parser.add_argument("--format", dest="format_", default="shiny", choices=["shiny", "stat"])
    args = parser.parse_args()
    upload(args.video, format_=args.format_)
