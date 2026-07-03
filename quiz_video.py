import os
import platform
import random
from pathlib import Path

from moviepy.config import change_settings
from moviepy.editor import (
    CompositeVideoClip,
    concatenate_videoclips,
    VideoFileClip,
    AudioFileClip,
    CompositeAudioClip,
    VideoClip,
    vfx,
    TextClip,
)
from PIL import Image

# Nur unter Windows explizit das ImageMagick-Binary setzen.
if platform.system() == "Windows":
    change_settings({
        "IMAGEMAGICK_BINARY": r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"
    })
else:
    # Unter Linux (GitHub Actions) verlässt sich MoviePy auf das installierte 'convert'/'magick'.
    # Optional kannst du es explizit setzen, wenn du willst:
    # change_settings({"IMAGEMAGICK_BINARY": "convert"})
    pass
# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
WIDTH, HEIGHT = 1080, 1920               # TikTok vertical resolution

QUESTION_DURATION = 15                   # Sekunden für die Frage
REVEAL_DURATION = 5                      # Sekunden für das Reveal
N_ROUNDS = 3                             # Anzahl Quiz-Runden

# Poppige TikTok-Style Fonts:
# - Poppins: häufig in modernen UI/Shortform-Content
# - Montserrat: ähnlich, etwas kantiger
# ACHTUNG: Du musst die Fonts auf deinem System installiert haben!
# Wenn es Fehler gibt, ändere FONT_NAME und COUNTDOWN_FONT_NAME z.B. zurück auf "Arial-Bold".
FONT_NAME = "Poppins-Bold"
COUNTDOWN_FONT_NAME = "Montserrat-ExtraBold"

FONT_SIZE = 80
TEXT_COLOR = "white"
COUNTDOWN_FONT_SIZE = 70

MUSIC_FILE = Path("music.mp3")           # optionale Hintergrundmusik

# Sprite-Größe: größer, aber begrenzt
SPRITE_QUAD_RATIO = 0.7                  # max. 70 % der Quadrantbreite/-höhe
MAX_SCALE_UP = 1.3                       # maximal 1.3x größer als Original


def _apply_fast_mode():
    """Kurze Zeiten und eine Runde für schnelle Tests."""
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
# Helper: Quadranten aus GIFs bauen (Transparenz, begrenztes Upscaling)
# ---------------------------------------------------------------------------
def _build_quadrants(duration: float, gif_paths: list[str]):
    """
    Erzeugt vier Quadranten aus GIF-Dateien.

    - GIFs werden über die gegebene Dauer geloopt.
    - Seitenverhältnis bleibt erhalten.
    - Sprites werden nur moderat hochskaliert (bis MAX_SCALE_UP), sonst eher kleiner.
    - GIF-Transparenz wird genutzt (has_mask=True).
    """
    quad_w, quad_h = WIDTH // 2, HEIGHT // 2
    clips = []
    positions = [(0, 0), (quad_w, 0), (0, quad_h), (quad_w, quad_h)]

    sprite_max_w = quad_w * SPRITE_QUAD_RATIO
    sprite_max_h = quad_h * SPRITE_QUAD_RATIO

    for path, pos in zip(gif_paths, positions):
        clip = VideoFileClip(path, has_mask=True)
        clip = clip.fx(vfx.loop, duration=duration)

        # gewünschte Zielgröße in Quadrant
        desired_scale_w = sprite_max_w / clip.w
        desired_scale_h = sprite_max_h / clip.h
        desired_scale = min(desired_scale_w, desired_scale_h)

        # begrenzt hochskalieren
        if desired_scale < 1.0:
            scale = desired_scale
        else:
            scale = min(desired_scale, MAX_SCALE_UP)

        if scale != 1.0:
            clip = clip.resize(scale)

        # zentrieren im Quadranten
        quad_x, quad_y = pos
        x = quad_x + (quad_w - clip.w) / 2
        y = quad_y + (quad_h - clip.h) / 2
        clip = clip.set_position((x, y))

        clip = clip.set_duration(duration)
        clips.append(clip)

    return clips


# ---------------------------------------------------------------------------
# Helper: Countdown-Clip
# ---------------------------------------------------------------------------
def _build_countdown(duration: float) -> VideoClip:
    """
    Baut einen numerischen Countdown-Clip von duration bis 1 herunter.
    """

    def make_frame(t):
        remaining = int(duration - t) + 1
        if remaining < 0:
            remaining = 0

        txt = TextClip(
            str(remaining),
            fontsize=COUNTDOWN_FONT_SIZE,
            font=COUNTDOWN_FONT_NAME,
            color=TEXT_COLOR,
            method="label",
        )
        frame = txt.get_frame(0)
        txt.close()
        return frame

    countdown = VideoClip(make_frame, duration=duration)
    return countdown


# ---------------------------------------------------------------------------
# Helper: eine Quiz-Runde (Frage + Reveal + Cry)
# ---------------------------------------------------------------------------
def _create_round(pokemon_dirs):
    """
    Erzeugt eine Quiz-Runde:
    - Frage: 4 GIFs, Text, Countdown
    - Reveal: shiny Pokémon in der Mitte, mit Cry-Audio (falls vorhanden)
    """
    # 4 zufällige gültige Pokémon-Ordner
    selected_dirs = random.sample(pokemon_dirs, k=4)

    # shiny unter den 4
    shiny_dir = random.choice(selected_dirs)
    shiny_path = shiny_dir / "shiny.gif"
    if not shiny_path.is_file():
        raise FileNotFoundError(f"Shiny GIF not found (should not happen): {shiny_path}")

    # Cry-Pfad (falls vorhanden)
    cry_path = shiny_dir / "cry.ogg"
    cry_str = str(cry_path) if cry_path.is_file() else None

    # restliche drei: normal.gif
    normal_dirs = [d for d in selected_dirs if d != shiny_dir]
    normal_paths = []
    for d in normal_dirs:
        normal_path = d / "normal.gif"
        if not normal_path.is_file():
            raise FileNotFoundError(f"Normal GIF not found (should not happen): {normal_path}")
        normal_paths.append(normal_path)

    # Liste der GIFs (ein shiny + drei normal) in zufälliger Reihenfolge
    gif_order = [str(shiny_path)] + [str(p) for p in normal_paths]
    random.shuffle(gif_order)

    # -------------------- Teil 1: Frage --------------------
    background_q = CompositeVideoClip(
        _build_quadrants(QUESTION_DURATION, gif_order), size=(WIDTH, HEIGHT)
    )

    question_text = (
        TextClip(
            "Which Pokemon is shiny?",
            fontsize=FONT_SIZE,
            font=FONT_NAME,
            color=TEXT_COLOR,
            method="caption",
        )
        .set_duration(QUESTION_DURATION)
        .set_position(("center", HEIGHT * 0.3))
    )

    countdown = _build_countdown(QUESTION_DURATION).set_position(
        ("center", HEIGHT * 0.5)
    )

    # Text und Countdown zuletzt einfügen → liegen über allem
    question_clip = CompositeVideoClip(
        [background_q, countdown, question_text],
        size=(WIDTH, HEIGHT)
    ).set_duration(QUESTION_DURATION)

    # -------------------- Teil 2: Reveal (nur shiny) --------------------
    shiny_clip = VideoFileClip(str(shiny_path), has_mask=True)
    shiny_clip = shiny_clip.fx(vfx.loop, duration=REVEAL_DURATION)

    # shiny etwas größer in der Mitte anzeigen
    target_w = WIDTH * 0.7
    target_h = HEIGHT * 0.7
    desired_scale = min(target_w / shiny_clip.w, target_h / shiny_clip.h)

    if desired_scale < 1.0:
        scale = desired_scale
    else:
        scale = min(desired_scale, MAX_SCALE_UP)

    if scale != 1.0:
        shiny_clip = shiny_clip.resize(scale)

    shiny_clip = shiny_clip.set_position(("center", "center")).set_duration(REVEAL_DURATION)

    reveal_clip = CompositeVideoClip(
        [shiny_clip],
        size=(WIDTH, HEIGHT)
    ).set_duration(REVEAL_DURATION)

    round_clip = concatenate_videoclips([question_clip, reveal_clip])

    # Runde + Cry-Pfad zurückgeben
    return round_clip, cry_str


# ---------------------------------------------------------------------------
# Finales Video (mehrere Runden + Musik + Cries)
# ---------------------------------------------------------------------------
def create_quiz_video(output_path: str = "quiz.mp4", fast_mode: bool = False):
    """Erzeugt das vollständige Quiz-Video mit mehreren Runden, Musik und Cry-Audio."""
    if fast_mode:
        _apply_fast_mode()

    # alle Pokémon-Ordner unter assets
    all_dirs = [p for p in Path("assets").iterdir() if p.is_dir()]

    # nur Ordner mit animiertem normal+shiny GIF
    pokemon_dirs = [p for p in all_dirs if _is_valid_pokemon_dir(p)]

    if len(pokemon_dirs) < 4:
        raise ValueError(
            "Es wurden weniger als vier gültige Pokémon gefunden.\n"
            "Stelle sicher, dass genügend Pokémon mit animierten normal.gif und shiny.gif vorhanden sind."
        )

    # Rundenclips und Cry-Pfade erzeugen
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

    # Hintergrundmusik
    if MUSIC_FILE.is_file():
        bg = AudioFileClip(str(MUSIC_FILE))
        bg = bg.subclip(0, min(bg.duration, total_duration))
        audio_clips.append(bg)

    # Cries pro Runde: jeder Cry startet beim Reveal der jeweiligen Runde
    current_start = 0.0
    for round_clip, cry_path in zip(rounds, cry_paths):
        if cry_path:
            cry = AudioFileClip(cry_path)
            cry = cry.subclip(0, min(cry.duration, REVEAL_DURATION))
            reveal_start_in_round = QUESTION_DURATION
            cry = cry.set_start(current_start + reveal_start_in_round)
            audio_clips.append(cry)

        current_start += round_clip.duration

    # Audio zusammensetzen und auf das Video legen
    if audio_clips:
        final_audio = CompositeAudioClip(audio_clips).set_duration(total_duration)
        final = final.set_audio(final_audio)

    # -------------------- Video schreiben --------------------
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    final.write_videofile(output_path, fps=30, codec="libx264", audio=bool(audio_clips))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Create shiny Pokémon quiz video")
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Fast test mode (kurze Dauer, eine Runde)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="quiz.mp4",
        help="Output video file path",
    )
    args = parser.parse_args()

    create_quiz_video(output_path=args.output, fast_mode=args.fast)