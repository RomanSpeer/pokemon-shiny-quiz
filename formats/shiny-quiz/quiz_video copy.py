import os
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
    ImageClip,
    ImageSequenceClip,
)
from PIL import Image, ImageFilter
import numpy as np

# ---------------------------------------------------------------------------
# ImageMagick / Pillow-Kompatibilität
# ---------------------------------------------------------------------------
# MoviePy 1.0.3 erwartet Image.ANTIALIAS, das in neueren Pillow-Versionen entfernt wurde.
if not hasattr(Image, "ANTIALIAS"):
    try:
        Image.ANTIALIAS = Image.Resampling.LANCZOS
    except AttributeError:
        Image.ANTIALIAS = getattr(Image, "LANCZOS", Image.BICUBIC)

# ImageMagick-Binary für MoviePy (Windows vs. macOS/Linux)
if os.name == "nt" and not os.getenv("GITHUB_ACTIONS"):
    change_settings({
        "IMAGEMAGICK_BINARY": r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"
    })
elif os.name == "posix":
    change_settings({"IMAGEMAGICK_BINARY": "magick"})  # macOS / Linux

print(os.name)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
WIDTH, HEIGHT = 1080, 1920               # TikTok vertical resolution

QUESTION_DURATION = 15                   # Sekunden für die Frage
REVEAL_DURATION = 5                      # Sekunden für das Reveal
N_ROUNDS = 3                             # Anzahl Quiz-Runden

# Fonts (müssen vom ImageMagick auf deinem System verstanden werden)
FONT_NAME = "AvantGarde-Book"
COUNTDOWN_FONT_NAME = "AvantGarde-Book"

FONT_SIZE = 80
TEXT_COLOR = "white"
COUNTDOWN_FONT_SIZE = 70

# Hintergrundmusik: Ordner mit mehreren mp3-Dateien
MUSIC_DIR = Path("music")

# Hintergrundbilder (blurred): PNG/JPG unter background_images/backgrounds
BACKGROUND_IMAGES_DIR = Path("background_images/backgrounds")

# Pokéball-Animation
POKEBALL_ANIMATION_PATH = Path("background_images/animations/pokeball_animation.gif")
POKEBALL_PHASE_DURATION = 0.7  # feste Dauer der Pokéball-Phase (~Fast-Mode)

# Sprite-Größe: größer, aber begrenzt
SPRITE_QUAD_RATIO = 2.0                  # max. 200 % der Quadrantbreite/-höhe
MAX_SCALE_UP = 2.6                       # maximal 2.6x größer als Original

# feste Skalierung für Pokéball-GIFs (unabhängig von SPRITE_QUAD_RATIO/MAX_SCALE_UP)
POKEBALL_SCALE = 1.5


def _apply_fast_mode():
    """Kurze Zeiten und eine Runde für schnelle Tests."""
    global QUESTION_DURATION, REVEAL_DURATION, N_ROUNDS
    QUESTION_DURATION = 2      # 2 Sekunden Frage
    REVEAL_DURATION = 1        # 1 Sekunde Reveal
    N_ROUNDS = 1               # eine Runde → ~3 Sekunden Video


# ---------------------------------------------------------------------------
# Helper: random geblurrtes Hintergrundbild laden (ohne Stretch, Center-Crop)
# ---------------------------------------------------------------------------
def _load_random_background_frame():
    """
    Lädt ein zufälliges PNG/JPG aus BACKGROUND_IMAGES_DIR,
    skaliert es mit beibehaltener Aspect Ratio so, dass WIDTH x HEIGHT bedeckt ist,
    schneidet dann die Mitte auf (WIDTH, HEIGHT) zu und blurred das Ergebnis.
    Gibt None zurück, wenn keine passenden Bilder vorhanden sind.
    """
    if not BACKGROUND_IMAGES_DIR.is_dir():
        return None

    files = []
    for ext in ("*.png", "*.jpg", "*.jpeg"):
        files.extend(BACKGROUND_IMAGES_DIR.glob(ext))

    if not files:
        return None

    bg_path = random.choice(files)
    try:
        img = Image.open(bg_path).convert("RGB")
        orig_w, orig_h = img.size

        # Skalierungsfaktor, so dass das Bild die Zielfläche komplett bedeckt (cover)
        scale = max(WIDTH / orig_w, HEIGHT / orig_h)
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)

        # Resize mit beibehaltener Aspect Ratio
        img = img.resize((new_w, new_h), Image.ANTIALIAS)

        # Center-Crop auf 1080x1920
        left = (new_w - WIDTH) // 2
        top = (new_h - HEIGHT) // 2
        right = left + WIDTH
        bottom = top + HEIGHT
        img = img.crop((left, top, right, bottom))

        # Blur, damit der Hintergrund nicht zu dominant ist
        img = img.filter(ImageFilter.GaussianBlur(radius=12))

        frame = np.array(img)
        return frame
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Helper: prüfen, ob ein GIF wirklich animiert ist (Pillow)
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
    Ein Pokémon-Ordner ist gültig, wenn:
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
# Helper: Pokéball als ImageSequenceClip laden (ohne VideoFileClip)
# ---------------------------------------------------------------------------
def _load_pokeball_clip():
    """
    Lädt die Pokéball-Animation mit Pillow und baut daraus ein ImageSequenceClip.
    Damit umgehen wir FFMPEG/VideoFileClip für dieses GIF komplett.
    Gibt einen Clip oder None zurück.
    """
    if not POKEBALL_ANIMATION_PATH.is_file():
        return None

    try:
        im = Image.open(POKEBALL_ANIMATION_PATH)
        frames = []
        durations_ms = []

        while True:
            frame = im.convert("RGBA")
            frames.append(np.array(frame))
            durations_ms.append(im.info.get("duration", 40))  # default 40ms
            im.seek(im.tell() + 1)
    except EOFError:
        pass
    except Exception as e:
        print(f"Warnung: Pokéball-GIF konnte nicht komplett gelesen werden: {e}")
        return None

    if not frames:
        return None

    avg_duration_ms = sum(durations_ms) / len(durations_ms)
    fps = 1000.0 / avg_duration_ms if avg_duration_ms > 0 else 25.0

    clip = ImageSequenceClip(frames, fps=fps)
    return clip


# ---------------------------------------------------------------------------
# Helper: Quadranten aus GIFs bauen (Pokémon via VideoFileClip)
# ---------------------------------------------------------------------------
def _build_quadrants(duration: float, gif_paths: list[str], pop_scale: bool = False, fixed_scale: float = None):
    """
    Erzeugt vier Quadranten aus GIF-Dateien (Pokémon) mit VideoFileClip:

    - GIFs werden über die gegebene Dauer geloopt.
    - Seitenverhältnis bleibt erhalten.
    - Sprites werden moderat hochskaliert (bis MAX_SCALE_UP), sonst eher kleiner.
    - GIF-Transparenz wird genutzt (has_mask=True).
    - pop_scale=True: kleiner Start, dann leichtes „Aufpoppen“ in den ersten ~0.6s.
    - fixed_scale: wenn gesetzt, wird genau dieser Scale-Faktor verwendet.
    """
    quad_w, quad_h = WIDTH // 2, HEIGHT // 2
    clips = []
    positions = [(0, 0), (quad_w, 0), (0, quad_h), (quad_w, quad_h)]

    sprite_max_w = quad_w * SPRITE_QUAD_RATIO
    sprite_max_h = quad_h * SPRITE_QUAD_RATIO

    for path_str, pos in zip(gif_paths, positions):
        clip = VideoFileClip(path_str, has_mask=True)
        clip = clip.fx(vfx.loop, duration=duration)

        # Zielgröße basierend auf Quadrant
        desired_scale_w = sprite_max_w / clip.w
        desired_scale_h = sprite_max_h / clip.h
        desired_scale = min(desired_scale_w, desired_scale_h)

        # Basis-Scale bestimmen
        if fixed_scale is not None:
            base_scale = fixed_scale
        else:
            if desired_scale < 1.0:
                base_scale = desired_scale
            else:
                base_scale = min(desired_scale, MAX_SCALE_UP)

        if pop_scale:
            pop_duration = min(0.6, duration)
            clip = clip.resize(
                lambda t, base_scale=base_scale, pop_duration=pop_duration: base_scale * (
                    0.8 + 0.2 * min(t / pop_duration, 1.0)
                )
            )
        else:
            if base_scale != 1.0:
                clip = clip.resize(base_scale)

        # zentrieren im Quadranten
        quad_x, quad_y = pos
        x = quad_x + (quad_w - clip.w) / 2
        y = quad_y + (quad_h - clip.h) / 2
        clip = clip.set_position((x, y))

        clip = clip.set_duration(duration)
        clips.append(clip)

    return clips


# ---------------------------------------------------------------------------
# Helper: Countdown-Clip (Text transparent, weiter oben)
# ---------------------------------------------------------------------------
def _build_countdown(duration: float) -> VideoClip:
    """
    Baut einen numerischen Countdown-Clip von duration bis 1 herunter.
    Der Text hat einen transparenten Hintergrund (keine Box).
    Implementiert als Sequenz von TextClips.
    """
    total = int(duration)
    if total <= 0:
        total = 1

    per_step = duration / total
    clips = []

    for i in range(total, 0, -1):
        txt = TextClip(
            str(i),
            fontsize=COUNTDOWN_FONT_SIZE,
            font=COUNTDOWN_FONT_NAME,
            color=TEXT_COLOR,
            method="label",          # transparenter Text, keine Box
        ).set_duration(per_step)
        clips.append(txt)

    countdown = concatenate_videoclips(clips)
    return countdown


# ---------------------------------------------------------------------------
# Helper: eine Quiz-Runde (Frage + Reveal + Cry)
# ---------------------------------------------------------------------------
def _create_round(pokemon_dirs, background_frame):
    """
    Erzeugt eine Quiz-Runde:
    - Frage: kurze Pokéball-Animation pro Quadrant, danach 4 Pokémon-GIFs mit Pop-Scale,
      geblurrter Hintergrund (falls vorhanden), Text, Countdown
    - Reveal: shiny Pokémon in der Mitte, mit Cry-Audio (falls vorhanden), auf gleichem Hintergrund
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
    # Hintergrund für Frage-Phase
    elements_q = []
    if background_frame is not None:
        bg_clip_q = ImageClip(background_frame).set_duration(QUESTION_DURATION)
        elements_q.append(bg_clip_q)

    # Pokéball-Phase: feste Dauer, kurz (z.B. 0.7s), damit wie im Fast-Mode
    pokeball_duration = 0.0
    pokeball_base_clip = _load_pokeball_clip()

    if pokeball_base_clip and QUESTION_DURATION > 1.0:
        # max. POKEBALL_PHASE_DURATION, aber nie länger als QUESTION_DURATION - 0.5
        pokeball_duration = min(POKEBALL_PHASE_DURATION, QUESTION_DURATION - 0.5)

        quad_w, quad_h = WIDTH // 2, HEIGHT // 2
        positions = [(0, 0), (quad_w, 0), (0, quad_h), (quad_w, quad_h)]

        pokeball_quads = []
        for pos in positions:
            c = pokeball_base_clip.fx(vfx.loop, duration=pokeball_duration)
            c = c.resize(POKEBALL_SCALE)

            quad_x, quad_y = pos
            x = quad_x + (quad_w - c.w) / 2
            y = quad_y + (quad_h - c.h) / 2
            c = c.set_position((x, y)).set_duration(pokeball_duration)
            c = c.set_start(0).fx(vfx.fadeout, 0.2)
            pokeball_quads.append(c)

        elements_q.extend(pokeball_quads)
    else:
        print("Hinweis: Pokéball-Animation wird nicht verwendet (Datei fehlt oder GIF konnte nicht gelesen werden).")

    # Pokémon-Phase: Pokémon erscheinen nach Pokéball, mit Pop-Scale-Animation
    pokemon_duration = QUESTION_DURATION - pokeball_duration
    pokemon_quads = _build_quadrants(
        pokemon_duration,
        gif_order,
        pop_scale=True,
        fixed_scale=None,
    )
    pokemon_quads = [c.set_start(pokeball_duration).fx(vfx.fadein, 0.2) for c in pokemon_quads]
    elements_q.extend(pokemon_quads)

    background_q = CompositeVideoClip(
        elements_q,
        size=(WIDTH, HEIGHT)
    ).set_duration(QUESTION_DURATION)

    # Frage-Text (transparent, etwas mittiger)
    question_text = (
        TextClip(
            "Find the Shiny",
            fontsize=FONT_SIZE,
            font=FONT_NAME,
            color=TEXT_COLOR,
            method="label",          # kurzer Text, keine Caption-Box
        )
        .set_duration(QUESTION_DURATION)
        .set_position(("center", HEIGHT * 0.4))
    )

    countdown = _build_countdown(QUESTION_DURATION).set_position(
        ("center", HEIGHT * 0.6)  # etwas höher
    )

    # Text und Countdown zuletzt einfügen → liegen über allem
    question_clip = CompositeVideoClip(
        [background_q, countdown, question_text],
        size=(WIDTH, HEIGHT)
    ).set_duration(QUESTION_DURATION)

    # -------------------- Teil 2: Reveal (nur shiny, gleicher Hintergrund) --------------------
    shiny_clip = VideoFileClip(str(shiny_path), has_mask=True)
    shiny_clip = shiny_clip.fx(vfx.loop, duration=REVEAL_DURATION)

    # shiny deutlich größer in der Mitte anzeigen (Scale 3.0)
    scale = 3.0
    shiny_clip = shiny_clip.resize(scale)
    shiny_clip = shiny_clip.set_position(("center", "center")).set_duration(REVEAL_DURATION)

    if background_frame is not None:
        bg_clip_r = ImageClip(background_frame).set_duration(REVEAL_DURATION)
        reveal_clip = CompositeVideoClip(
            [bg_clip_r, shiny_clip],
            size=(WIDTH, HEIGHT)
        ).set_duration(REVEAL_DURATION)
    else:
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

    # alle Pokémon-Ordner unter assets (leichter Check)
    assets_dir = Path("assets")
    all_dirs = [p for p in assets_dir.iterdir() if p.is_dir()]
    pokemon_dirs = [p for p in all_dirs if _is_valid_pokemon_dir(p)]

    if len(pokemon_dirs) < 4:
        raise ValueError(
            "Es wurden weniger als vier gültige Pokémon gefunden.\n"
            "Stelle sicher, dass genügend Pokémon mit animierten normal.gif und shiny.gif vorhanden sind."
        )

    print(f"{len(pokemon_dirs)} gültige Pokémon-Ordner gefunden.")

    # einmalig random Hintergrundbild für das ganze Video laden
    background_frame = _load_random_background_frame()

    # Rundenclips und Cry-Pfade erzeugen
    rounds = []
    cry_paths = []

    for round_idx in range(N_ROUNDS):
        round_clip, cry_path = _create_round(pokemon_dirs, background_frame)
        rounds.append(round_clip)
        cry_paths.append(cry_path)
        print(f"Runde {round_idx + 1} erzeugt.")

    # Video ohne Audio zusammensetzen
    final = concatenate_videoclips(rounds)
    total_duration = final.duration

    # -------------------- Audio-Spuren bauen --------------------
    audio_clips = []

    # Hintergrundmusik: zufällige mp3 aus MUSIC_DIR (falls vorhanden)
    if MUSIC_DIR.is_dir():
        music_files = sorted(MUSIC_DIR.glob("*.mp3"))
        if music_files:
            music_file = random.choice(music_files)
            print(f"Verwende Hintergrundmusik: {music_file}")
            bg = AudioFileClip(str(music_file))
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