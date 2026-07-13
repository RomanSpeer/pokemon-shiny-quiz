import os
import random
from pathlib import Path

from moviepy.config import change_settings
from moviepy.editor import (
    ColorClip,
    TextClip,
    CompositeVideoClip,
    concatenate_videoclips,
    VideoFileClip,
    AudioFileClip,
    CompositeAudioClip,
    vfx,
)
from PIL import Image

change_settings({
    "IMAGEMAGICK_BINARY": r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"
})

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
WIDTH, HEIGHT = 1080, 1920               # TikTok vertical resolution

QUESTION_DURATION = 15                   # Sekunden für die Frage
REVEAL_DURATION = 5                      # Sekunden für das Reveal
N_ROUNDS = 3                             # Anzahl Quiz-Runden

FONT_NAME = "Arial-Bold"                 # ggf. durch eigenen Font ersetzen
FONT_SIZE = 80
TEXT_COLOR = "white"

HIGHLIGHT_COLOR = (255, 255, 255)        # Farbe des Rahmens
BORDER_THICK = 10                        # Rahmenstärke

MUSIC_FILE = Path("music.mp3")           # optional: Hintergrundmusik

# Sprites bewusst kleiner + keine Hochskalierung
SPRITE_QUAD_RATIO = 0.5                  # max. 50 % der Quadrantbreite/-höhe
# ---------------------------------------------------------------------------


def _apply_fast_mode():
    """Setzt kurze Zeiten und wenige Runden für schnelle Tests."""
    global QUESTION_DURATION, REVEAL_DURATION, N_ROUNDS
    QUESTION_DURATION = 2      # 2 Sekunden Frage
    REVEAL_DURATION = 1        # 1 Sekunde Reveal
    N_ROUNDS = 1               # eine Runde → ~3 Sekunden Video


# ---------------------------------------------------------------------------
# Helper: prüfen, ob ein GIF wirklich animiert ist
# ---------------------------------------------------------------------------
def _is_animated_gif(path: Path) -> bool:
    """True, wenn path eine animierte GIF-Datei (>= 2 Frames) ist."""
    if not path.is_file():
        return False
    try:
        with Image.open(path) as im:
            return getattr(im, "is_animated", False) and getattr(im, "n_frames", 1) > 1
    except Exception:
        return False


def _is_valid_pokemon_dir(p: Path) -> bool:
    """
    Ein Pokémon-Ordner ist nur gültig, wenn:
    - normal.gif existiert und animiert ist
    - shiny.gif existiert und animiert ist
    """
    normal = p / "normal.gif"
    shiny = p / "shiny.gif"

    if not normal.is_file() or not shiny.is_file():
        return False

    if not _is_animated_gif(normal):
        return False

    if not _is_animated_gif(shiny):
        return False

    return True


# ---------------------------------------------------------------------------
# Helper: Quadranten aus GIFs bauen (Transparenz, keine Hochskalierung)
# ---------------------------------------------------------------------------
def _build_quadrants(duration: float, gif_paths: list[str]):
    """Erzeugt vier Quadranten aus GIF-Dateien.

    - GIFs werden über die gewünschte Dauer geloopt.
    - Seitenverhältnis bleibt erhalten.
    - Sprites werden nur verkleinert, nie vergrößert (keine Hochskalierung).
    - Transparenz aus dem GIF wird genutzt (has_mask=True).
    """
    quad_w, quad_h = WIDTH // 2, HEIGHT // 2
    clips = []
    positions = [(0, 0), (quad_w, 0), (0, quad_h), (quad_w, quad_h)]

    sprite_max_w = quad_w * SPRITE_QUAD_RATIO
    sprite_max_h = quad_h * SPRITE_QUAD_RATIO

    for path, pos in zip(gif_paths, positions):
        # has_mask=True: MoviePy erzeugt automatisch eine Maske aus GIF-Transparenz
        clip = VideoFileClip(path, has_mask=True)

        # GIF über die gewünschte Dauer loopen
        clip = clip.fx(vfx.loop, duration=duration)

        # Nur verkleinern, nie vergrößern:
        # - wenn Sprite größer als sprite_max_*, schrumpfen
        # - wenn kleiner, Originalgröße behalten (keine Pixel-Hochskalierung)
        scale_w = sprite_max_w / clip.w
        scale_h = sprite_max_h / clip.h
        scale = min(scale_w, scale_h)

        if scale < 1.0:
            clip = clip.resize(scale)
        # sonst: clip bleibt in Originalgröße

        # innerhalb des Quadranten zentrieren
        quad_x, quad_y = pos
        x = quad_x + (quad_w - clip.w) / 2
        y = quad_y + (quad_h - clip.h) / 2
        clip = clip.set_position((x, y))

        # Dauer setzen
        clip = clip.set_duration(duration)

        clips.append(clip)

    return clips


# ---------------------------------------------------------------------------
# Helper: Reveal-Rahmen für den richtigen Quadranten
# ---------------------------------------------------------------------------
def _build_answer_border(answer_quad: str, duration: float):
    """Erzeugt vier Rahmen-Segmente um den angegebenen Quadranten."""
    quad_w, quad_h = WIDTH // 2, HEIGHT // 2

    top = ColorClip(size=(quad_w, BORDER_THICK), color=HIGHLIGHT_COLOR).set_duration(duration)
    bottom = ColorClip(size=(quad_w, BORDER_THICK), color=HIGHLIGHT_COLOR).set_duration(duration)
    left = ColorClip(size=(BORDER_THICK, quad_h), color=HIGHLIGHT_COLOR).set_duration(duration)
    right = ColorClip(size=(BORDER_THICK, quad_h), color=HIGHLIGHT_COLOR).set_duration(duration)

    positions = {
        "top_left": {
            "top": (0, 0),
            "bottom": (0, quad_h - BORDER_THICK),
            "left": (0, 0),
            "right": (quad_w - BORDER_THICK, 0),
        },
        "top_right": {
            "top": (quad_w, 0),
            "bottom": (quad_w, quad_h - BORDER_THICK),
            "left": (quad_w, 0),
            "right": (quad_w + quad_w - BORDER_THICK, 0),
        },
        "bottom_left": {
            "top": (0, quad_h),
            "bottom": (0, quad_h + quad_h - BORDER_THICK),
            "left": (0, quad_h),
            "right": (quad_w - BORDER_THICK, quad_h),
        },
        "bottom_right": {
            "top": (quad_w, quad_h),
            "bottom": (quad_w, quad_h + quad_h - BORDER_THICK),
            "left": (quad_w, quad_h),
            "right": (quad_w + quad_w - BORDER_THICK, quad_h),
        },
    }

    pos = positions.get(answer_quad, positions["top_left"])

    border_clips = [
        top.set_position(pos["top"]),
        bottom.set_position(pos["bottom"]),
        left.set_position(pos["left"]),
        right.set_position(pos["right"]),
    ]
    return border_clips


# ---------------------------------------------------------------------------
# Helper: Eine komplette Quiz-Runde bauen (Frage + Reveal)
# ---------------------------------------------------------------------------
def _create_round(pokemon_dirs):
    """Erzeugt einen Clip für eine Quiz-Runde (Frage + Reveal) und gibt den Cry-Pfad zurück."""
    # 4 zufällige gültige Pokémon-Ordner auswählen
    selected_dirs = random.sample(pokemon_dirs, k=4)

    # zufälliges shiny unter diesen 4 wählen
    shiny_dir = random.choice(selected_dirs)
    shiny_path = shiny_dir / "shiny.gif"
    if not shiny_path.is_file():
        raise FileNotFoundError(f"Shiny GIF not found (should not happen): {shiny_path}")

    # Cry-Pfad (falls vorhanden) merken
    cry_path = shiny_dir / "cry.ogg"
    cry_str = str(cry_path) if cry_path.is_file() else None

    # die anderen drei liefern normal.gif
    normal_dirs = [d for d in selected_dirs if d != shiny_dir]
    normal_paths = []
    for d in normal_dirs:
        normal_path = d / "normal.gif"
        if not normal_path.is_file():
            raise FileNotFoundError(f"Normal GIF not found (should not happen): {normal_path}")
        normal_paths.append(normal_path)

    # Liste aller GIFs (ein shiny + drei normal) und zufällige Reihenfolge
    gif_order = [str(shiny_path)] + [str(p) for p in normal_paths]
    random.shuffle(gif_order)

    # bestimmen, in welchem Quadranten das shiny liegt
    shiny_idx = gif_order.index(str(shiny_path))
    index_to_quad = {
        0: "top_left",
        1: "top_right",
        2: "bottom_left",
        3: "bottom_right",
    }
    answer_quad = index_to_quad[shiny_idx]

    # -------------------- Part 1: Frage --------------------
    background_q = CompositeVideoClip(
        _build_quadrants(QUESTION_DURATION, gif_order), size=(WIDTH, HEIGHT)
    )
    txt = (
        TextClip(
            "Which Pokemon is shiny?",
            fontsize=FONT_SIZE,
            font=FONT_NAME,
            color=TEXT_COLOR,
            method="caption",
        )
        .set_duration(QUESTION_DURATION)
        .set_position("center")
    )
    # Text **immer oben**: als letztes Element im Composite
    question_clip = CompositeVideoClip(
        [background_q, txt],
        size=(WIDTH, HEIGHT)
    ).set_duration(QUESTION_DURATION)

    # -------------------- Part 2: Reveal --------------------
    background_r = CompositeVideoClip(
        _build_quadrants(REVEAL_DURATION, gif_order), size=(WIDTH, HEIGHT)
    )
    border_clips = _build_answer_border(answer_quad, REVEAL_DURATION)

    reveal_clip = CompositeVideoClip(
        [background_r, *border_clips],
        size=(WIDTH, HEIGHT)
    ).set_duration(REVEAL_DURATION)

    # Frage + Reveal zusammen
    round_clip = concatenate_videoclips([question_clip, reveal_clip])
    return round_clip, cry_str


# ---------------------------------------------------------------------------
# Build the full video (mehrere Runden + Audio)
# ---------------------------------------------------------------------------
def create_quiz_video(output_path: str = "quiz.mp4", fast_mode: bool = False):
    """Erzeugt ein TikTok‑Quiz‑Video mit mehreren Runden und Audio (Musik + Cries)."""
    if fast_mode:
        _apply_fast_mode()

    # alle Pokémon-Ordner unter assets sammeln
    all_dirs = [p for p in Path("assets").iterdir() if p.is_dir()]

    # nur gültige Ordner mit animierten normal+shiny GIFs verwenden
    pokemon_dirs = [p for p in all_dirs if _is_valid_pokemon_dir(p)]

    if len(pokemon_dirs) < 4:
        raise ValueError(
            "Es wurden weniger als vier gültige Pokémon gefunden.\n"
            "Stelle sicher, dass genügend Pokémon mit animierten normal.gif und shiny.gif vorhanden sind."
        )

    # Rundenclips und zugehörige Cry-Pfade erzeugen
    rounds = []
    cry_paths = []

    for _ in range(N_ROUNDS):
        round_clip, cry_path = _create_round(pokemon_dirs)
        rounds.append(round_clip)
        cry_paths.append(cry_path)

    # Video ohne Audio zusammensetzen
    final = concatenate_videoclips(rounds)
    total_duration = final.duration

    # -------------------- Audio-Spuren bauen --------------------
    audio_clips = []

    # Hintergrundmusik (optional)
    if MUSIC_FILE.is_file():
        bg = AudioFileClip(str(MUSIC_FILE))
        bg = bg.subclip(0, min(bg.duration, total_duration))
        audio_clips.append(bg)

    # Cries pro Runde:
    # jeder Cry startet genau beim Reveal der jeweiligen Runde
    current_start = 0.0
    for round_clip, cry_path in zip(rounds, cry_paths):
        if cry_path:
            cry = AudioFileClip(cry_path)
            cry = cry.subclip(0, min(cry.duration, REVEAL_DURATION))
            reveal_start_in_round = QUESTION_DURATION
            cry = cry.set_start(current_start + reveal_start_in_round)
            audio_clips.append(cry)

        current_start += round_clip.duration

    # Audio zusammensetzen und auf das finale Video legen
    if audio_clips:
        final_audio = CompositeAudioClip(audio_clips).set_duration(total_duration)
        final = final.set_audio(final_audio)

    # -------------------- Video schreiben --------------------
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    final.write_videofile(output_path, fps=30, codec="libx264", audio=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Create shiny Pokémon quiz video")
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Fast test mode (kurze Dauer, wenige Runden)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="quiz.mp4",
        help="Output video file path",
    )
    args = parser.parse_args()

    create_quiz_video(output_path=args.output, fast_mode=args.fast)