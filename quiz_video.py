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
)
from PIL import Image, ImageFilter, ImageDraw, ImageFont
import numpy as np

# ---------------------------------------------------------------------------
# ImageMagick / Pillow-Kompatibilität
# ---------------------------------------------------------------------------
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
WIDTH, HEIGHT = 1080, 1920  # TikTok vertical resolution

QUESTION_DURATION = 10       # Sekunden für die Frage
REVEAL_DURATION = 2.5         # Sekunden für das Reveal
N_ROUNDS = 5
# Anzahl der Runden

# Fonts (müssen von ImageMagick verstanden werden)
# Wenn du eine echte Pokémon-Font installiert hast, trag sie hier ein.
BASE_DIR = Path(__file__).resolve().parent

# Passe den Dateinamen exakt an das an, was bei dir liegt:
# z.B. Pokemon Solid.ttf, PokemonSolid.ttf, PokemonSolid.otf, etc.
FONT_PATH = BASE_DIR / "fonts" / "pokemon" / "PokemonSolid.ttf"

print("Font path:", FONT_PATH)
print("Font exists:", FONT_PATH.is_file())

FONT_NAME = str(FONT_PATH)
COUNTDOWN_FONT_NAME = FONT_NAME

FONT_SIZE = 90
TEXT_COLOR = "white"
COUNTDOWN_FONT_SIZE = 70

# Hintergrundmusik & Soundeffekte
BACKGROUND_MUSIC_DIR = Path("music/video_background_music")
POKEBALL_SFX_PATH = Path("music/sound_effects/pokeball.mp3")

# Hintergrundbilder unter background_images/backgrounds
BACKGROUND_IMAGES_DIR = Path("background_images/backgrounds")

# Pokéball-Animation
POKEBALL_ANIMATION_PATH = Path("background_images/animations/pokeball_animation.gif")
POKEBALL_PHASE_DURATION = 0.7  # feste Dauer der Pokéball-Phase

# Sprite-Größe: größer
SPRITE_QUAD_RATIO = 2.8       # max. 280 % der Quadrantbreite/-höhe
MAX_SCALE_UP = 3.5            # maximal 3.5x größer als Original

# feste Skalierung für Pokéball-GIFs
POKEBALL_SCALE = 1.5


# ---------------------------------------------------------------------------
# Helper: random geblurrtes Hintergrundbild laden
# ---------------------------------------------------------------------------
def _load_random_background_frame():
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

        scale = max(WIDTH / orig_w, HEIGHT / orig_h)
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)

        img = img.resize((new_w, new_h), Image.ANTIALIAS)

        left = (new_w - WIDTH) // 2
        top = (new_h - HEIGHT) // 2
        right = left + WIDTH
        bottom = top + HEIGHT
        img = img.crop((left, top, right, bottom))

        img = img.filter(ImageFilter.GaussianBlur(radius=12))

        frame = np.array(img)
        return frame
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Helper: prüfen, ob ein GIF animiert ist (Pillow)
# ---------------------------------------------------------------------------
def _is_animated_gif(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        with Image.open(path) as im:
            return getattr(im, "is_animated", False) and getattr(im, "n_frames", 1) > 1
    except Exception:
        return False


def _is_valid_pokemon_dir(p: Path) -> bool:
    """
    Gültig, wenn normal.gif & shiny.gif existieren und animiert sind.
    GIF-Decoding machen wir via VideoFileClip(has_mask=True).
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
# Helper: GIF einmal via FFmpeg dekodieren, dann endlos loopen
# ---------------------------------------------------------------------------
def _load_gif_clip_ffmpeg_loop(path: Path, desired_duration: float) -> VideoClip:
    """
    Lädt ein GIF mit VideoFileClip(has_mask=True), sammelt alle Frames
    (und ggf. Maskenframes) ein und baut daraus einen eigenen VideoClip,
    der die Frames endlos loopen kann (t -> t % orig_dur), ohne FFmpeg
    für lange Loops zu benutzen.
    """
    base = VideoFileClip(str(path), has_mask=True)
    fps = base.fps or 25

    frames_rgb = []
    for frame in base.iter_frames(fps=fps):
        frames_rgb.append(frame)

    if not frames_rgb:
        base.close()
        raise RuntimeError(f"Keine Frames im GIF {path}")

    total_frames = len(frames_rgb)

    frames_mask = None
    if base.mask is not None:
        frames_mask = [m for m in base.mask.iter_frames(fps=fps)]

    base.close()

    def make_frame(t):
        idx = int((t * fps) % total_frames)
        return frames_rgb[idx]

    clip = VideoClip(make_frame, duration=desired_duration)

    if frames_mask is not None and len(frames_mask) == total_frames:
        def make_mask_frame(t):
            idx = int((t * fps) % total_frames)
            return frames_mask[idx]
        mask_clip = VideoClip(make_mask_frame, ismask=True, duration=desired_duration)
        clip = clip.set_mask(mask_clip)

    return clip.set_duration(desired_duration)


# ---------------------------------------------------------------------------
# Helper: Quadranten aus GIFs bauen (FFmpeg -> eigener Loop-Clip)
# ---------------------------------------------------------------------------
def _build_quadrants(duration: float, gif_paths: list[str], pop_scale: bool = False, fixed_scale: float = None):
    """
    Erzeugt vier Quadranten aus GIF-Dateien:

    - GIFs werden einmal via VideoFileClip(has_mask=True) dekodiert.
    - Eigener VideoClip mit endlosem Loop wird gebaut.
    - Seitenverhältnis bleibt erhalten.
    - Sprites werden moderat hochskaliert (bis MAX_SCALE_UP).
    - pop_scale=True: kleiner Start, dann „Aufpoppen“ in den ersten ~0.6s.
    - fixed_scale: wenn gesetzt, wird genau dieser Scale-Faktor verwendet.
    """
    quad_w, quad_h = WIDTH // 2, HEIGHT // 2
    clips = []
    positions = [(0, 0), (quad_w, 0), (0, quad_h), (quad_w, quad_h)]

    sprite_max_w = quad_w * SPRITE_QUAD_RATIO
    sprite_max_h = quad_h * SPRITE_QUAD_RATIO

    for path_str, pos in zip(gif_paths, positions):
        clip = _load_gif_clip_ffmpeg_loop(Path(path_str), duration)

        desired_scale_w = sprite_max_w / clip.w
        desired_scale_h = sprite_max_h / clip.h
        desired_scale = min(desired_scale_w, desired_scale_h)

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

        quad_x, quad_y = pos
        x = quad_x + (quad_w - clip.w) / 2
        y = quad_y + (quad_h - clip.h) / 2
        clip = clip.set_position((x, y))

        clip = clip.set_duration(duration)
        clips.append(clip)

    return clips


# ---------------------------------------------------------------------------
# Helper: Pokéball als VideoFileClip (optional über FFmpeg)
# ---------------------------------------------------------------------------
def _load_pokeball_clip():
    if not POKEBALL_ANIMATION_PATH.is_file():
        return None
    try:
        clip = VideoFileClip(str(POKEBALL_ANIMATION_PATH), has_mask=True)
        return clip
    except Exception as e:
        print(f"Warnung: Pokéball-GIF kann von FFmpeg nicht gelesen werden: {e}")
        return None


def _build_healthbar(duration: float) -> VideoClip:
    """
    Zentrierte Healthbar im Pokémon-Stil:

    - Schwarze, abgerundete Border (Pill-Shape)
    - Innen weißer Hintergrund
    - Füllung von links:
        - >50% Restzeit: grün
        - 50% bis 15%: orange
        - <15%: rot
    - "Verlust" kommt von rechts: rechter Teil bleibt weiß.
    """
    bar_w = int(WIDTH * 0.5)      # etwas schmaler als zuvor
    bar_h = 30                    # etwas flacher
    border_thickness = 8          # dickere Border
    radius = bar_h // 2           # abgerundete Ecken (Pill-Form)

    total_w = bar_w + 2 * border_thickness
    total_h = bar_h + 2 * border_thickness

    def make_frame(t):
        ratio = max(0.0, min(1.0, (duration - t) / duration))

        # Farbwahl abhängig von Restzeit
        if ratio > 0.5:
            color = (80, 200, 80)      # Grün
        elif ratio > 0.15:
            color = (255, 165, 0)     # Orange
        else:
            color = (220, 60, 60)     # Rot

        # Pillow-Canvas für hübsche abgerundete Ecken
        img = Image.new("RGB", (total_w, total_h), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        x0 = border_thickness
        y0 = border_thickness
        x1 = x0 + bar_w
        y1 = y0 + bar_h

        # Innenbereich: weißer Hintergrund (damit "Verlust" von rechts weiß ist)
        draw.rounded_rectangle(
            [(x0, y0), (x1, y1)],
            radius=radius,
            fill=(255, 255, 255),
            outline=None
        )

        # Füllung von links: abgerundeter Balken mit der aktuellen Farbe
        fill_w = max(1, int(bar_w * ratio))
        if fill_w > 0:
            draw.rounded_rectangle(
                [(x0, y0), (x0 + fill_w, y1)],
                radius=radius,
                fill=color,
                outline=None
            )

        # zurück als NumPy-Array
        arr = np.array(img)
        return arr

    health_clip = VideoClip(make_frame, duration=duration)
    # knapp unter der vertikalen Mitte (z.B. 52 % der Höhe)
    health_clip = health_clip.set_position(("center", int(HEIGHT * 0.52)))
    return health_clip.set_duration(duration)

def _build_guess_text_clip(text: str, duration: float) -> VideoClip:
    """
    Rendert den Titel-Text (z.B. "Guess the Shiny") mit der Pokémon-Font
    über Pillow und gibt ihn als ImageClip zurück, zentriert über der Healthbar.
    """
    # Transparenter Fullscreen-Canvas
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Font laden – im Fehlerfall Default-Font verwenden
    try:
        font = ImageFont.truetype(FONT_NAME, FONT_SIZE)
    except OSError as e:
        print(f"Warnung: Pokémon-Font konnte nicht geladen werden ({e}). Verwende Default-Font.")
        font = ImageFont.load_default()

    # Textgröße bestimmen – Pillow 10+: textbbox, ältere Versionen: textsize
    if hasattr(draw, "textbbox"):
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
    else:
        text_w, text_h = draw.textsize(text, font=font)

    # Zentrierte Position (knapp über der Healthbar)
    x = (WIDTH - text_w) // 2
    # leicht über der Mitte, z.B. 0.45
    y = int(HEIGHT * 0.45)

    # Weißen Text zeichnen
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))

    # In ImageClip verwandeln
    frame = np.array(img)
    clip = ImageClip(frame).set_duration(duration)
    return clip.set_position((0, 0))


# ---------------------------------------------------------------------------
# Helper: Countdown-Clip (falls du später doch wieder Zahl-Countdown willst)
# ---------------------------------------------------------------------------
def _build_countdown(duration: float) -> VideoClip:
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
            method="label",  # transparenter Text, keine Box
        ).set_duration(per_step)
        clips.append(txt)

    countdown = concatenate_videoclips(clips)
    return countdown


# ---------------------------------------------------------------------------
# Helper: eine Quiz-Runde
# ---------------------------------------------------------------------------
def _create_round(pokemon_dirs, background_frame):
    selected_dirs = random.sample(pokemon_dirs, k=4)

    shiny_dir = random.choice(selected_dirs)
    shiny_path = shiny_dir / "shiny.gif"
    if not shiny_path.is_file():
        raise FileNotFoundError(f"Shiny GIF not found: {shiny_path}")

    cry_path = shiny_dir / "cry.ogg"
    cry_str = str(cry_path) if cry_path.is_file() else None

    normal_dirs = [d for d in selected_dirs if d != shiny_dir]
    normal_paths = []
    for d in normal_dirs:
        normal_path = d / "normal.gif"
        if not normal_path.is_file():
            raise FileNotFoundError(f"Normal GIF not found: {normal_path}")
        normal_paths.append(normal_path)

    gif_order = [str(shiny_path)] + [str(p) for p in normal_paths]
    random.shuffle(gif_order)

    # -------------------- Teil 1: Frage --------------------
    elements_q = []
    pokeball_sfx_offset = None  # Zeitpunkt innerhalb der Runde, wann der SFX laufen soll
    if background_frame is not None:
        bg_clip_q = ImageClip(background_frame).set_duration(QUESTION_DURATION)
        elements_q.append(bg_clip_q)

    pokeball_duration = 0.0
    pokeball_base_clip = _load_pokeball_clip()

    if pokeball_base_clip and QUESTION_DURATION > 1.0:
        pokeball_duration = min(POKEBALL_PHASE_DURATION, QUESTION_DURATION - 0.5)

        # SFX soll zur Hälfte der Pokéball-Duration gespielt werden
        pokeball_sfx_offset = 0.0
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
        print("Hinweis: Pokéball-Animation wird nicht verwendet (Datei fehlt oder FFmpeg mag sie nicht).")

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

    # Text "Guess the Shiny" mittig über der Healthbar (Pillow + Pokémon-Font)
    guess_text = _build_guess_text_clip("Guess the Shiny", QUESTION_DURATION)

    # Healthbar mittig
    healthbar_clip = _build_healthbar(QUESTION_DURATION)

    question_clip = CompositeVideoClip(
        [background_q, guess_text, healthbar_clip],
        size=(WIDTH, HEIGHT)
    ).set_duration(QUESTION_DURATION)

    # -------------------- Teil 2: Reveal --------------------
    shiny_clip = _load_gif_clip_ffmpeg_loop(shiny_path, REVEAL_DURATION)

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

    # Rückgabe: Video-Clip, Cry-Audio-Pfad, Pokéball-SFX-Offset (innerhalb der Runde)
    return round_clip, cry_str, pokeball_sfx_offset


# ---------------------------------------------------------------------------
# Finales Video (mehrere Runden + Musik + Cry)
# ---------------------------------------------------------------------------
def create_quiz_video(output_path: str = "quiz.mp4"):
    assets_dir = Path("assets")
    all_dirs = [p for p in assets_dir.iterdir() if p.is_dir()]
    pokemon_dirs = [p for p in all_dirs if _is_valid_pokemon_dir(p)]

    if len(pokemon_dirs) < 4:
        raise ValueError(
            "Es wurden weniger als vier gültige Pokémon gefunden.\n"
            "Stelle sicher, dass genügend Pokémon mit animierten normal.gif und shiny.gif vorhanden sind."
        )

    print(f"{len(pokemon_dirs)} gültige Pokémon-Ordner gefunden.")

    background_frame = _load_random_background_frame()

    rounds = []
    cry_paths = []
    pokeball_offsets = []

    for round_idx in range(N_ROUNDS):
        round_clip, cry_path, pokeball_offset = _create_round(pokemon_dirs, background_frame)
        rounds.append(round_clip)
        cry_paths.append(cry_path)
        pokeball_offsets.append(pokeball_offset)
        print(f"Runde {round_idx + 1} erzeugt.")

    final = concatenate_videoclips(rounds)
    total_duration = final.duration

    audio_clips = []

    if BACKGROUND_MUSIC_DIR.is_dir():
        # Nur "echte" MP3s ohne macOS-Resource-Files (._Dateien)
        music_files = sorted(
            mf for mf in BACKGROUND_MUSIC_DIR.glob("*.mp3")
            if not mf.name.startswith("._")
        )

        if music_files:
            music_file = random.choice(music_files)
            print(f"Hintergrundmusik: {music_file}")
            bg = AudioFileClip(str(music_file))
            bg = bg.subclip(0, min(bg.duration, total_duration))
            audio_clips.append(bg)
        else:
            print("Hinweis: Keine gültigen Hintergrundmusik-Dateien gefunden.")

    current_start = 0.0
    for round_clip, cry_path, pokeball_offset in zip(rounds, cry_paths, pokeball_offsets):
        # Cry-Sound im Reveal
        if cry_path:
            cry = AudioFileClip(cry_path)
            cry = cry.subclip(0, min(cry.duration, REVEAL_DURATION))
            reveal_start_in_round = QUESTION_DURATION
            cry = cry.set_start(current_start + reveal_start_in_round)
            audio_clips.append(cry)

        # Pokéball-SFX in der Fragephase, zur Hälfte der Pokéball-Duration
        if pokeball_offset is not None and POKEBALL_SFX_PATH.is_file():
            sfx = AudioFileClip(str(POKEBALL_SFX_PATH))
            # nicht kürzen – kompletten Sound (5–6 s) laufen lassen
            sfx = sfx.set_start(current_start + pokeball_offset)
            audio_clips.append(sfx)

        current_start += round_clip.duration

    if audio_clips:
        final_audio = CompositeAudioClip(audio_clips).set_duration(total_duration)
        final = final.set_audio(final_audio)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    final.write_videofile(output_path, fps=30, codec="libx264", audio=bool(audio_clips))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Create shiny Pokémon quiz video (multi-round)")
    parser.add_argument(
        "--output",
        type=str,
        default="quiz.mp4",
        help="Output video file path",
    )
    args = parser.parse_args()

    create_quiz_video(output_path=args.output)