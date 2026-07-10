"""Upload a video to YouTube as a Short.

Requires env vars: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN.
See get_youtube_refresh_token.py for how to obtain the refresh token once.

Optionally set YT_PLAYLIST_ID to also add every upload to a playlist (e.g. a
"Guess the Pokémon" playlist). Find a playlist's ID in its YouTube URL
(youtube.com/playlist?list=PL...) or create one via the API/YouTube Studio.
If unset, the playlist step is simply skipped.
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
        "title": "Who's That Pokémon? Guess before time runs out! ⏱️",
        "description": (
            "Type chart, cry, ability and a pixelated silhouette - can you guess the "
            "Pokémon before the reveal? Drop your guess in the comments! "
            "#Shorts #Pokemon #PokemonQuiz #WhosThatPokemon"
        ),
        "tags": ["Pokemon", "PokemonQuiz", "WhosThatPokemon", "Shorts", "Quiz"],
    },
    {
        "title": "Only a TRUE Pokémon Master can guess this! ⚡️ #Shorts",
        "description": (
            "Use the type chart, the cry and the ability to figure out who's that "
            "Pokémon! #Shorts #Pokemon #PokemonQuiz #Nintendo #Gaming"
        ),
        "tags": ["Pokemon", "PokemonQuiz", "Nintendo", "Shorts", "Gaming"],
    },
    {
        "title": "Guess the Pokémon in 7 Seconds! 🔥 #Shorts",
        "description": (
            "New round, new mystery Pokémon! How fast can you name it? "
            "#Shorts #Pokemon #PokemonQuiz #Quiz #Nintendo"
        ),
        "tags": ["Pokemon", "Quiz", "PokemonQuiz", "Shorts", "Nintendo"],
    },
    {
        "title": "Can YOU name this Pokémon? 🧠 #Shorts",
        "description": (
            "Type chart, cry and ability clues - put your Pokédex knowledge to the "
            "test before the reveal! #Shorts #Pokemon #PokemonQuiz #Trivia"
        ),
        "tags": ["Pokemon", "PokemonQuiz", "Trivia", "Shorts"],
    },
]
CATEGORY_ID = "24"  # Entertainment


def add_to_playlist(youtube, video_id: str, playlist_id: str) -> None:
    youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {"kind": "youtube#video", "videoId": video_id},
            }
        },
    ).execute()


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
            print(f"Upload progress: {int(status.progress() * 100)}%")

    print(f"YouTube video uploaded: https://youtube.com/watch?v={response['id']}")

    playlist_id = os.environ.get("YT_PLAYLIST_ID")
    if playlist_id:
        add_to_playlist(youtube, response["id"], playlist_id)
        print(f"Added to playlist: https://youtube.com/playlist?list={playlist_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload video to YouTube Shorts")
    parser.add_argument("--video", required=True, help="Path to video file")
    args = parser.parse_args()
    upload(args.video)
