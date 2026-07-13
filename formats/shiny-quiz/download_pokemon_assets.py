import argparse
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from tqdm import tqdm


# --------------------------------------------------------------------------- #
# Konfiguration
# --------------------------------------------------------------------------- #
BASE_URL = "https://pokeapi.co/api/v2"
ASSETS_ROOT = Path("assets/pokemon")

# Wartezeit zwischen API‑Requests (in Sekunden) – reduziert das Risiko von
# Rate‑Limit‑Fehlern (die API erlaubt ca. 100 Requests pro 60 Sekunden).
REQUEST_DELAY = 0.6


# --------------------------------------------------------------------------- #
# Hilfsfunktionen
# --------------------------------------------------------------------------- #
def _request(url: str) -> dict:
    """Einfacher GET‑Request mit Fehlerbehandlung."""
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _download_file(url: str, dest: Path) -> None:
    """Download einer Datei (Bild, Audio, …) und speichere sie unter ``dest``."""
    resp = requests.get(url, stream=True, timeout=30)
    resp.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)


def _save_as_gif(src_path: Path, dst_path: Path) -> None:
    """
    Konvertiere ein PNG (oder ein bereits vorhandenes GIF) zu einem GIF.

    Für die meisten Sprites ist die Quelle ein statisches PNG (1 Frame).
    Falls mehrere Frames vorhanden sind, übernehmen wir sie und speichern
    ein animiertes GIF. Problematische Transparenz-Infos werden entfernt,
    um Pillow-Bugs zu vermeiden.
    """
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(src_path) as im:
            frames: list[Image.Image] = []

            # Alle Frames einlesen (bei PNG meist nur 1)
            try:
                while True:
                    frames.append(im.copy())
                    im.seek(im.tell() + 1)
            except EOFError:
                pass  # Ende der Frames

            if not frames:
                return

            if len(frames) == 1:
                # Einfaches Bild → als GIF speichern, Transparenz bereinigen
                frame = frames[0].convert("RGBA")
                frame.info.pop("transparency", None)
                frame.save(dst_path, format="GIF")
            else:
                # Mehrere Frames → animiertes GIF bauen
                clean_frames: list[Image.Image] = []
                for f in frames:
                    f = f.convert("RGBA")
                    f.info.pop("transparency", None)
                    clean_frames.append(f)

                clean_frames[0].save(
                    dst_path,
                    format="GIF",
                    save_all=True,
                    append_images=clean_frames[1:],
                    loop=0,
                    duration=im.info.get("duration", 100),
                    disposal=2,
                )

    except UnidentifiedImageError:
        print(f"⚠️  {src_path} ist kein gültiges Bild – Sprite wird übersprungen.")


def _fallback_static_sprite(sprites: dict, shiny: bool = False) -> str | None:
    """
    Falls kein besseres Sprite verfügbar ist, greife auf das statische
    Front‑Sprite zurück (PNG).
    """
    try:
        return sprites["front_shiny"] if shiny else sprites["front_default"]
    except KeyError:
        return None


def _get_best_sprite_url(sprites: dict, shiny: bool = False) -> str | None:
    """
    Wähle die bestmögliche Sprite-URL:

    1. 'other' -> 'showdown' (animierte GIFs für alle Pokémon)
    2. Gen‑V 'animated' (Black/White)
    3. Klassisches statisches Front‑Sprite (PNG)
    """
    key = "front_shiny" if shiny else "front_default"

    # 1) Showdown-Sprites (animierte GIFs)
    try:
        showdown = sprites["other"]["showdown"]
        url = showdown.get(key)
        if url:
            return url
    except (KeyError, TypeError):
        pass

    # 2) Gen‑V animierte Sprites (Black/White)
    try:
        gen5 = sprites["versions"]["generation-v"]["black-white"]["animated"]
        url = gen5.get(key)
        if url:
            return url
    except (KeyError, TypeError):
        pass

    # 3) Fallback: statisches Front-Sprite (PNG)
    return _fallback_static_sprite(sprites, shiny=shiny)


def _is_gif_url(url: str) -> bool:
    """Prüfe anhand der URL-Endung, ob es sich um ein GIF handelt."""
    path = urlparse(url).path.lower()
    return path.endswith(".gif")


def _download_pokemon(pokemon_entry: dict) -> None:
    """Lädt die Assets für ein einzelnes Pokémon herunter."""
    name = pokemon_entry["name"]
    pokemon_url = pokemon_entry["url"]
    data = _request(pokemon_url)

    target_dir = ASSETS_ROOT / name
    target_dir.mkdir(parents=True, exist_ok=True)

    sprites = data["sprites"]

    # ------------------------------------------------- #
    # 1️⃣ Normal‑Sprite (bevorzugt animiertes Showdown‑GIF)
    # ------------------------------------------------- #
    normal_url = _get_best_sprite_url(sprites, shiny=False)

    if normal_url:
        if _is_gif_url(normal_url):
            # animiertes GIF direkt speichern
            _download_file(normal_url, target_dir / "normal.gif")
        else:
            # z.B. PNG → temporär speichern und nach GIF konvertieren
            tmp_path = target_dir / "normal_tmp"
            _download_file(normal_url, tmp_path)
            _save_as_gif(tmp_path, target_dir / "normal.gif")
            tmp_path.unlink(missing_ok=True)

    # ------------------------------------------------- #
    # 2️⃣ Shiny‑Sprite (bevorzugt animiertes Showdown‑GIF)
    # ------------------------------------------------- #
    shiny_url = _get_best_sprite_url(sprites, shiny=True)

    if shiny_url:
        if _is_gif_url(shiny_url):
            _download_file(shiny_url, target_dir / "shiny.gif")
        else:
            tmp_path = target_dir / "shiny_tmp"
            _download_file(shiny_url, tmp_path)
            _save_as_gif(tmp_path, target_dir / "shiny.gif")
            tmp_path.unlink(missing_ok=True)

    # ------------------------------------------------- #
    # 3️⃣ Cry (Audio‑Datei, .ogg)
    #     liegt direkt im Pokémon-Objekt unter data["cries"]["latest"]
    # ------------------------------------------------- #
    try:
        cries = data.get("cries") or {}
        cry_url = cries.get("latest")
        if cry_url:
            _download_file(cry_url, target_dir / "cry.ogg")
    except Exception:
        # Manche Pokémon besitzen keinen Cry‑Eintrag oder der Download schlägt fehl.
        pass


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments; currently only ``--start`` is supported."""
    parser = argparse.ArgumentParser(
        description="Download Pokémon assets (Showdown-GIFs bevorzugt) mit optionaler Resume-Funktion"
    )
    parser.add_argument(
        "--start",
        type=str,
        default="",
        help="Name des Pokémon, ab dem der Download beginnen soll (Standard: chespin)",
    )
    return parser.parse_args()


def main() -> None:
    """Hauptfunktion – iteriert über alle Pokémon und ruft ``_download_pokemon`` auf."""
    args = parse_args()

    print("🔎 Lade die Liste aller Pokémon …")
    index = _request(f"{BASE_URL}/pokemon?limit=2000")  # 2000 > aktuelle Anzahl
    results = index["results"]

    # Bestimme den Start‑Index (falls der Name nicht gefunden wird, beginnen wir bei 0)
    start_idx = next((i for i, e in enumerate(results) if e["name"] == args.start), 0)
    if start_idx > 0:
        print(f"🚦 Starte bei Pokémon #{start_idx + 1} ({args.start})")
    else:
        print(f"🚦 Starte bei Anfang (Standard‑Pokémon: {args.start})")

    subset = results[start_idx:]

    print(f"📦 {len(subset)} Einträge werden verarbeitet …")
    for entry in tqdm(subset, desc="Pokémon", unit="poke"):
        try:
            _download_pokemon(entry)
        except Exception as exc:  # noqa: BLE001
            tqdm.write(f"⚠️  Fehler bei {entry['name']}: {exc}")
        time.sleep(REQUEST_DELAY)  # Rate‑Limit‑Schutz

    print("\n✅ Alle Assets wurden unter dem Ordner 'assets/pokemon/' abgelegt.")
    print(
        "💡 Du kannst das Verzeichnis jetzt in dein Projekt kopieren oder direkt\n"
        "   mit deinem `quiz_video.py` verwenden."
    )


if __name__ == "__main__":
    main()