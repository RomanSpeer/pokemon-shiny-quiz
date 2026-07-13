import shutil
from pathlib import Path

from moviepy.editor import VideoFileClip
from PIL import Image

ASSETS_DIR = Path("assets")


def is_animated_gif(path: Path) -> bool:
    """True, wenn path eine animierte GIF-Datei (>= 2 Frames) ist und Pillow sie öffnen kann."""
    if not path.is_file():
        return False
    try:
        with Image.open(path) as im:
            return getattr(im, "is_animated", False) and getattr(im, "n_frames", 1) > 1
    except Exception:
        return False


def ffmpeg_gif_ok(path: Path) -> bool:
    """
    Dekodiert ein GIF mit VideoFileClip (FFmpeg) über alle Frames.
    Wenn irgendwo ein Fehler auftritt, ist das genau der Typ von GIF,
    der dir später bei write_videofile um die Ohren fliegt.
    """
    if not path.is_file():
        return False

    clip = None
    try:
        clip = VideoFileClip(str(path), has_mask=True)
        # komplette GIF-Dauer durchlaufen
        for _ in clip.iter_frames():
            pass
        return True
    except Exception as e:
        print(f"[WARN] FFmpeg-Fehler bei {path}: {e}")
        return False
    finally:
        if clip is not None:
            clip.close()


def is_valid_pokemon_dir(p: Path) -> bool:
    """
    Ein Pokémon-Ordner ist gültig, wenn:
    - normal.gif & shiny.gif existieren
    - beide animiert sind
    - beide sich von FFmpeg vollständig dekodieren lassen
    """
    normal = p / "normal.gif"
    shiny = p / "shiny.gif"

    if not normal.is_file() or not shiny.is_file():
        return False

    if not is_animated_gif(normal) or not is_animated_gif(shiny):
        return False

    if not ffmpeg_gif_ok(normal) or not ffmpeg_gif_ok(shiny):
        return False

    return True


def find_invalid_pokemon_dirs() -> list[Path]:
    """Findet alle Pokémon-Ordner in ASSETS_DIR, die für FFmpeg problematisch sind."""
    if not ASSETS_DIR.is_dir():
        raise FileNotFoundError(f"Assets-Verzeichnis nicht gefunden: {ASSETS_DIR}")

    all_dirs = [p for p in ASSETS_DIR.iterdir() if p.is_dir()]
    invalid = []

    print(f"Scanne {len(all_dirs)} Ordner unter {ASSETS_DIR} (vollständiger FFmpeg-Check)...")

    for idx, p in enumerate(all_dirs, start=1):
        if not is_valid_pokemon_dir(p):
            invalid.append(p)

        if idx % 100 == 0:
            print(f"  geprüft: {idx}/{len(all_dirs)} Ordner, aktuell invalid: {len(invalid)}")

    print(f"Fertig. Invalid Pokémon-Ordner: {len(invalid)}")
    return invalid


def delete_dirs(dirs: list[Path]):
    """Löscht die angegebenen Ordner (rekursiv) nach Bestätigung."""
    if not dirs:
        print("Keine Ordner zu löschen.")
        return

    print("\nFolgende Ordner werden gelöscht:")
    for p in dirs:
        print(f"  - {p}")

    answer = input("\nWirklich löschen? [yes/NO]: ").strip().lower()
    if answer != "yes":
        print("Abgebrochen, nichts gelöscht.")
        return

    for p in dirs:
        try:
            shutil.rmtree(p)
            print(f"  [OK] gelöscht: {p}")
        except Exception as e:
            print(f"  [ERR] konnte {p} nicht löschen: {e}")

    print("Löschvorgang abgeschlossen.")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Finde und lösche Pokémon-Ordner mit GIFs, die FFmpeg nicht komplett dekodieren kann."
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Invalid Pokémon-Ordner nach Scan tatsächlich löschen",
    )
    args = parser.parse_args()

    invalid_dirs = find_invalid_pokemon_dirs()

    if not invalid_dirs:
        print("Alle Pokémon-GIFs sehen für FFmpeg gut aus. ✅")
        return

    print("\nInvalid Ordner:")
    for p in invalid_dirs:
        print(f"  - {p}")

    if args.delete:
        delete_dirs(invalid_dirs)
    else:
        print(
            "\nHinweis: Nichts gelöscht. "
            "Wenn du die oben gelisteten Ordner entfernen möchtest, "
            "führe das Skript mit --delete aus:\n"
            "  python cleanup_invalid_pokemon_full.py --delete"
        )


if __name__ == "__main__":
    main()