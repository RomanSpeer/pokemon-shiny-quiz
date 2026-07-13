# Pokémon Quiz Video Generator

Erzeugt automatisch ein "Wer ist dieses Pokémon?"-Quizvideo (1080x1920, für
Shorts/Reels/TikTok) mit Daten von der [PokeAPI](https://pokeapi.co).

## Ablauf des Videos

1. **Intro** – Silhouette des Pokémon + Pokédex-Nummer
2. **Typ-Chart** – Schwächen / Resistenzen / Immunitäten (berechnet aus den
   Typ-Multiplikatoren der PokeAPI)
3. **Schrei** – Original-Cry des Pokémon
4. **Fähigkeit** – Name + kurze Beschreibung
5. **Pokédex-Eintrag** – Flavor-Text, Größe & Gewicht
6. **Reveal** – Farbiges Artwork, Name und Typen

## Setup

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

Wird `ffmpeg` nicht bereits über `moviepy`/`imageio-ffmpeg` gefunden, muss es
zusätzlich installiert sein (macOS: `brew install ffmpeg`).

## Benutzung

```bash
./.venv/bin/python main.py            # zufälliges Pokémon
./.venv/bin/python main.py pikachu    # bestimmtes Pokémon per Name
./.venv/bin/python main.py 6          # bestimmtes Pokémon per Pokédex-Nummer
```

Das fertige Video landet in `output/quiz_<nummer>_<name>.mp4`.

## Struktur

- `pokeapi.py` – Ruft Basisdaten, Typ-Effektivität, Fähigkeit, Pokédex-Eintrag
  und Cry-URL von der PokeAPI ab.
- `slides.py` – Rendert jede Slide als Bild (Pillow).
- `video.py` – Setzt die Slides inkl. Cry-Audio zu einem MP4 zusammen (moviepy).
- `main.py` – Einstiegspunkt / CLI.

## YouTube-Upload & Playlist

Der Workflow (`.github/workflows/generate-and-upload.yml`) lädt jedes Video automatisch
als YouTube Short hoch (`upload_youtube.py`) und hängt es optional an eine Playlist an.

Benötigte Repo-Secrets:

- `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` – per
  `python get_youtube_refresh_token.py` einmalig lokal erzeugen (siehe Docstring dort).
- `YT_PLAYLIST_ID` *(optional)* – ohne dieses Secret wird der Playlist-Schritt
  einfach übersprungen. Playlist einmalig manuell in YouTube Studio anlegen:
  - **Titel:** `Guess the Pokémon`
  - **Beschreibung:** New mystery Pokémon every round. ⚡ Type chart, cry,
    ability and a pixelated silhouette — piece together the clues before the
    reveal. How fast can you name it? 🔴 Drop your guess in the comments and
    see if you're a true Pokémon Master!
    `#Shorts #Pokemon #PokemonQuiz #WhosThatPokemon`
  - Die ID danach aus der Playlist-URL kopieren:
    `youtube.com/playlist?list=PLxxxxxxxx` → der Teil nach `list=`.

**Wichtig:** Das Hinzufügen zu einer Playlist braucht den Scope
`youtube.force-ssl`, reines `youtube.upload` reicht dafür nicht. Falls dein
`YT_REFRESH_TOKEN` schon vor der Playlist-Funktion erzeugt wurde, fehlt ihm
dieser Scope – `get_youtube_refresh_token.py` einmal erneut laufen lassen und
das Secret mit dem neuen Token überschreiben, sonst schlägt der
Playlist-Insert mit einem 403 fehl (der Video-Upload selbst funktioniert
trotzdem weiter).

## Anpassungen

- Slide-Dauer, Farben und Schriftgrößen lassen sich in `slides.py` bzw.
  `video.py` (Konstanten `SLIDE_DURATION`, `INTRO_DURATION`, `REVEAL_DURATION`)
  anpassen.
- Um Hintergrundmusik zu ergänzen, kann in `video.py` beim finalen Clip
  zusätzlich ein `AudioFileClip` per `CompositeAudioClip` mit reduzierter
  Lautstärke gemischt werden.
