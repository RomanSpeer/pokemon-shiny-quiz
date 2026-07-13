import json
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

QUESTION_DURATION = 7       # Sekunden für die Frage
STAT_QUESTION_DURATION = 5  # Sekunden Bedenkzeit für die Stat-Vergleich-Runde
REVEAL_DURATION = 2        # Sekunden für das Reveal
STAT_REVEAL_DURATION = REVEAL_DURATION + 1  # etwas länger, da 4 Werte gleichzeitig zu lesen sind
N_ROUNDS = 5
# Anzahl der Runden

# Mix der Rundentypen für das normale Shiny-Quiz-Video (Gewichte müssen
# nicht auf 1 summieren, werden normalisiert). stat_compare ist bewusst
# nicht Teil dieses Mixes - das läuft als eigenständiges Video
# (--round-type stat_compare, siehe stat_video.py).
ROUND_TYPE_WEIGHTS = {
    "species": 0.4,      # 4 verschiedene Pokémon, eines shiny -> welches ist shiny?
    "color_shift": 0.4,  # 1 Pokémon 4x, 3x Hue-verschoben -> welches ist die echte Farbe?
    "cry": 0.2,          # 4 Silhouetten, Cry-Sound einer davon -> welches Pokémon ruft?
}
STATS_PATH = Path("data/pokemon_stats.json")
STAT_LABELS = {
    "hp": "HP",
    "attack": "Attack",
    "defense": "Defense",
    "special-attack": "Sp. Attack",
    "special-defense": "Sp. Defense",
    "speed": "Speed",
    "height": "Height",
    "weight": "Weight",
}
MIN_STAT_GAP = 5   # Verlierer müssen mindestens so viel schlechter sein als der Gewinner
MAX_STAT_GAP = 12  # ...aber höchstens so viel, sonst wird's zu offensichtlich

# "height" ist in Dezimetern gespeichert und hat eine riesige Bandbreite
# (0.1m bis 20m+) - ein fixer Punkte-Gap wäre bei kleinen Pokémon relativ
# riesig (1m vs 0.1m wirkt trivial unterschiedlich) und bei großen kaum
# merkbar. Daher hier prozentual vom Anker-Wert statt absolut.
HEIGHT_MIN_GAP_RATIO = 0.15  # Verlierer mind. 15% kleiner als der Gewinner
HEIGHT_MAX_GAP_RATIO = 0.35  # ...aber höchstens 35% kleiner
HUE_SHIFT_MIN_DEGREES = 25
HUE_SHIFT_MAX_DEGREES = 150

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


print("BACKGROUND_IMAGES_DIR:", BACKGROUND_IMAGES_DIR, "exists:", BACKGROUND_IMAGES_DIR.is_dir())
print("BACKGROUND_MUSIC_DIR:", BACKGROUND_MUSIC_DIR, "exists:", BACKGROUND_MUSIC_DIR.is_dir())
print("POKEBALL_SFX_PATH:", POKEBALL_SFX_PATH, "exists:", POKEBALL_SFX_PATH.is_file())

# ---------------------------------------------------------------------------
# Helper: random geblurrtes Hintergrundbild laden
# ---------------------------------------------------------------------------
def _load_random_background_frame():
    if not BACKGROUND_IMAGES_DIR.is_dir():
        print("Hinweis: BACKGROUND_IMAGES_DIR existiert nicht:", BACKGROUND_IMAGES_DIR)
        return None

    files = []
    patterns = [
        "*.png", "*.PNG",
        "*.jpg", "*.JPG",
        "*.jpeg", "*.JPEG",
    ]
    for ext in patterns:
        files.extend(BACKGROUND_IMAGES_DIR.glob(ext))

    # macOS-Resource-Files (._*) und versteckte Dateien rausfiltern
    files = [
        f for f in files
        if not f.name.startswith("._") and not f.name.startswith(".")
    ]

    print(f"Gefundene Background-Images in {BACKGROUND_IMAGES_DIR}: {len(files)}")

    if not files:
        print("Hinweis: Keine gültigen Background-Images gefunden.")
        return None

    bg_path = random.choice(files)
    print("Verwendetes Background-Image:", bg_path)

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
    except Exception as e:
        print(f"Hinweis: Fehler beim Laden des Background-Images {bg_path} ({e}).")
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
def _load_gif_clip_ffmpeg_loop(path: Path, desired_duration: float, color_transform=None) -> VideoClip:
    """
    Lädt ein GIF mit VideoFileClip(has_mask=True), sammelt alle Frames
    (und ggf. Maskenframes) ein und baut daraus einen eigenen VideoClip,
    der die Frames endlos loopen kann (t -> t % orig_dur), ohne FFmpeg
    für lange Loops zu benutzen.

    color_transform: optionale Funktion (RGB-Frame -> RGB-Frame), z.B. für
    Hue-Shift oder Silhouette-Effekte. Die Transparenzmaske bleibt davon
    unberührt.
    """
    base = VideoFileClip(str(path), has_mask=True)
    fps = base.fps or 25

    frames_rgb = []
    for frame in base.iter_frames(fps=fps):
        frames_rgb.append(color_transform(frame) if color_transform else frame)

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


def _hue_shift_frame(frame_rgb: np.ndarray, degrees: float) -> np.ndarray:
    """Rotiert den Farbton (Hue) eines RGB-Frames um `degrees`."""
    img = Image.fromarray(frame_rgb, "RGB").convert("HSV")
    h, s, v = img.split()
    shift = int(round(degrees / 360 * 255))
    h_arr = (np.array(h).astype(np.int16) + shift) % 256
    h_new = Image.fromarray(h_arr.astype(np.uint8), "L")
    shifted = Image.merge("HSV", (h_new, s, v)).convert("RGB")
    return np.array(shifted)


def _silhouette_frame(frame_rgb: np.ndarray) -> np.ndarray:
    """Ersetzt alle Pixel durch ein einheitliches Dunkelgrau (Silhouette).
    Die Transparenzmaske bleibt unverändert, sodass nur die sichtbare Form
    übrig bleibt."""
    return np.full_like(frame_rgb, 30)


def _desaturate_frame(frame_rgb: np.ndarray, amount: float = 0.5) -> np.ndarray:
    """Blendet Farbe Richtung Grau - für 'Verlierer'-Sprites beim
    Stat-Vergleich-Reveal (amount=0 -> unverändert, 1 -> komplett grau)."""
    gray = frame_rgb.mean(axis=-1, keepdims=True)
    blended = frame_rgb.astype(np.float64) * (1 - amount) + gray * amount
    return blended.astype(np.uint8)


def _apply_fade_mask(clip, start_opacity: float = 1.0, end_opacity: float = 0.45):
    """Lässt die Deckkraft eines Clips über seine gesamte Dauer linear von
    start_opacity zu end_opacity übergehen (nie ganz unsichtbar)."""
    if clip.mask is None:
        return clip
    duration = clip.duration

    def fade(get_frame, t):
        factor = start_opacity + (end_opacity - start_opacity) * min(t / duration, 1.0)
        return get_frame(t) * factor

    return clip.set_mask(clip.mask.fl(fade))


# ---------------------------------------------------------------------------
# Helper: Quadranten aus GIFs bauen (FFmpeg -> eigener Loop-Clip)
# ---------------------------------------------------------------------------
def _build_quadrants(
    duration: float,
    gif_paths: list[str],
    pop_scale: bool = False,
    fixed_scale: float = None,
    color_transforms: list = None,
):
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

    if color_transforms is None:
        color_transforms = [None] * len(gif_paths)

    for path_str, pos, color_transform in zip(gif_paths, positions, color_transforms):
        clip = _load_gif_clip_ffmpeg_loop(Path(path_str), duration, color_transform=color_transform)

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


def _build_healthbar(duration: float, y_ratio: float = 0.52) -> VideoClip:
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
        fill_w = max(2, int(bar_w * ratio))
        # Pillow <10 wirft einen ValueError in rounded_rectangle, wenn die
        # Breite ungerade ist und radius == fill_w // 2 - daher auf gerade
        # Breite runden.
        if fill_w % 2:
            fill_w -= 1
        if fill_w > 0:
            fill_radius = min(radius, fill_w // 2)
            draw.rounded_rectangle(
                [(x0, y0), (x0 + fill_w, y1)],
                radius=fill_radius,
                fill=color,
                outline=None
            )

        # zurück als NumPy-Array
        arr = np.array(img)
        return arr

    health_clip = VideoClip(make_frame, duration=duration)
    health_clip = health_clip.set_position(("center", int(HEIGHT * y_ratio)))
    return health_clip.set_duration(duration)

def _build_text_clip(
    text: str,
    duration: float,
    y_ratio: float = 0.45,
    x_center: float = None,
    font_size: int = None,
    color=(255, 255, 255, 255),
) -> VideoClip:
    """
    Rendert Text mit der Pokémon-Font über Pillow und gibt ihn als
    ImageClip zurück. x_center erlaubt Positionierung abseits der Mitte
    (z.B. für Werte in einem 2-Panel-Layout).
    """
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    def _measure(f):
        if hasattr(draw, "textbbox"):
            bbox = draw.textbbox((0, 0), text, font=f)
            return bbox[2] - bbox[0]
        return draw.textsize(text, font=f)[0]

    try:
        size = font_size or FONT_SIZE
        font = ImageFont.truetype(FONT_NAME, size)
        # Zu breiten Text automatisch verkleinern, statt über den Rand
        # hinauslaufen zu lassen (z.B. sehr lange Pokémon-Namen).
        max_width = WIDTH * 0.92
        text_w = _measure(font)
        if text_w > max_width:
            size = max(18, int(size * max_width / text_w))
            font = ImageFont.truetype(FONT_NAME, size)
    except OSError as e:
        print(f"Warnung: Pokémon-Font konnte nicht geladen werden ({e}). Verwende Default-Font.")
        font = ImageFont.load_default()

    text_w = _measure(font)
    cx = x_center if x_center is not None else WIDTH / 2
    x = int(cx - text_w / 2)
    y = int(HEIGHT * y_ratio)

    draw.text((x, y), text, font=font, fill=color)

    frame = np.array(img)
    clip = ImageClip(frame).set_duration(duration)
    return clip.set_position((0, 0))


def _build_guess_text_clip(text: str, duration: float) -> VideoClip:
    """Titel-Text (z.B. "Guess the Shiny"), zentriert über der Healthbar."""
    return _build_text_clip(text, duration, y_ratio=0.45, font_size=FONT_SIZE)


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
def _average_color(gif_path: Path) -> np.ndarray:
    """Durchschnittsfarbe des ersten Frames, transparente Pixel ausgeschlossen."""
    with Image.open(gif_path) as im:
        arr = np.array(im.convert("RGBA"))
    rgb = arr[..., :3].astype(np.float64)
    mask = arr[..., 3] > 10
    if not mask.any():
        mask = np.ones(arr.shape[:2], dtype=bool)
    return rgb[mask].mean(axis=0)


def _shiny_color_distance(pokemon_dir: Path) -> float:
    """Je kleiner der Wert, desto ähnlicher sehen normal.gif und shiny.gif
    sich - also desto schwerer ist die Runde für dieses Pokémon."""
    normal_color = _average_color(pokemon_dir / "normal.gif")
    shiny_color = _average_color(pokemon_dir / "shiny.gif")
    return float(np.linalg.norm(normal_color - shiny_color))


MIN_SHINY_COLOR_DISTANCE = 8.0  # unterhalb dessen gilt normal/shiny als (fast) ununterscheidbar

MIN_SHINY_SATURATION = 60.0  # unterhalb dessen ist ein Hue-Shift kaum sichtbar (z.B. sehr dunkle Shinys)
COLOR_SHIFT_PICK_ATTEMPTS = 6


def _average_saturation(gif_path: Path) -> float:
    """Durchschnittliche HSV-Sättigung des ersten Frames, transparente Pixel
    ausgeschlossen. Bei niedriger Sättigung (Grau-/Schwarztöne) ist ein
    Hue-Shift kaum sichtbar."""
    with Image.open(gif_path) as im:
        arr = np.array(im.convert("RGBA"))
    mask = arr[..., 3] > 10
    if not mask.any():
        mask = np.ones(arr.shape[:2], dtype=bool)
    hsv = np.array(Image.fromarray(arr[..., :3], "RGB").convert("HSV"))
    return float(hsv[..., 1][mask].mean())


def _pick_round_type(exclude: frozenset = frozenset()) -> str:
    types = [t for t in ROUND_TYPE_WEIGHTS if t not in exclude]
    weights = [ROUND_TYPE_WEIGHTS[t] for t in types]
    return random.choices(types, weights=weights, k=1)[0]


def _load_stats_data() -> dict:
    """Lädt die lokal gecachten Statwerte (siehe fetch_pokemon_stats.py).
    Ohne diese Datei wird der stat_compare-Rundentyp einfach übersprungen."""
    if not STATS_PATH.is_file():
        return {}
    try:
        return json.loads(STATS_PATH.read_text())
    except Exception as e:
        print(f"Warnung: {STATS_PATH} konnte nicht gelesen werden ({e}).")
        return {}


def _format_stat_value(stat_key: str, value) -> str:
    if stat_key == "height":
        return f"{value / 10:.1f} m"
    if stat_key == "weight":
        return f"{value / 10:.1f} kg"
    return str(value)


def _find_stat_group(pokemon_dirs, stats_data, group_size: int = 4):
    """Wählt eine Statkategorie + einen Anker-Pokémon (= der Gewinner), dann
    `group_size - 1` weitere Pokémon, deren Wert um MIN_STAT_GAP bis
    MAX_STAT_GAP darunter liegt (bei "height" stattdessen prozentual, siehe
    HEIGHT_MIN/MAX_GAP_RATIO) - rein aus den lokal gecachten Werten, kein
    Live-API-Call während der Videoerstellung. Der Mindestabstand verhindert
    ein zu knappes (fast unlösbares) Rätsel, der Höchstabstand verhindert
    ein zu offensichtliches. Gibt None zurück, wenn keine passende Gruppe
    gefunden wurde."""
    names = [d.name for d in pokemon_dirs if d.name in stats_data]
    if len(names) < group_size:
        return None

    anchor_name = random.choice(names)
    stat_key = random.choice(list(STAT_LABELS.keys()))
    anchor_value = stats_data[anchor_name].get(stat_key)
    if anchor_value is None:
        return None

    if stat_key == "height":
        min_gap = max(1, round(anchor_value * HEIGHT_MIN_GAP_RATIO))
        max_gap = max(min_gap + 1, round(anchor_value * HEIGHT_MAX_GAP_RATIO))
    else:
        min_gap, max_gap = MIN_STAT_GAP, MAX_STAT_GAP

    candidates = [
        (name, stats_data[name][stat_key])
        for name in names
        if name != anchor_name
        and stat_key in stats_data[name]
        and min_gap <= anchor_value - stats_data[name][stat_key] <= max_gap
    ]
    if len(candidates) < group_size - 1:
        return None

    chosen = random.sample(candidates, group_size - 1)

    # Anker ist per Konstruktion garantiert der höchste Wert (alle anderen
    # liegen mindestens MIN_STAT_GAP darunter) - kein Tie möglich.
    entries = [(anchor_name, anchor_value)] + chosen
    random.shuffle(entries)

    return {
        "entries": entries,
        "stat_key": stat_key,
        "winner_name": anchor_name,
        "winner_value": anchor_value,
    }


def _prepare_species_round(pokemon_dirs, color_distances):
    """4 verschiedene Pokémon, eines shiny - welches ist shiny?"""
    selected_dirs = random.sample(pokemon_dirs, k=4)

    # Gewichtete Zufallsauswahl: Pokémon mit geringem Farbunterschied
    # zwischen normal/shiny werden bevorzugt (schwerer zu erraten), aber
    # nicht ausschließlich, damit auch leichtere Runden vorkommen. Kandidaten
    # mit (fast) identischen Farben (defekte Assets) werden als Shiny-Antwort
    # ausgeschlossen, da das Rätsel sonst unlösbar wäre - sie bleiben aber
    # als normale Decoys zulässig.
    shiny_candidates = [
        d for d in selected_dirs
        if color_distances.get(d, 100.0) >= MIN_SHINY_COLOR_DISTANCE
    ] or selected_dirs
    epsilon = 5.0
    weights = [1.0 / (color_distances.get(d, 100.0) + epsilon) for d in shiny_candidates]
    shiny_dir = random.choices(shiny_candidates, weights=weights, k=1)[0]
    shiny_path = shiny_dir / "shiny.gif"
    if not shiny_path.is_file():
        raise FileNotFoundError(f"Shiny GIF not found: {shiny_path}")

    normal_dirs = [d for d in selected_dirs if d != shiny_dir]
    normal_paths = []
    for d in normal_dirs:
        normal_path = d / "normal.gif"
        if not normal_path.is_file():
            raise FileNotFoundError(f"Normal GIF not found: {normal_path}")
        normal_paths.append(normal_path)

    entries = [(str(shiny_path), None)] + [(str(p), None) for p in normal_paths]
    random.shuffle(entries)

    cry_path = shiny_dir / "cry.ogg"
    return {
        "gif_paths": [e[0] for e in entries],
        "color_transforms": [e[1] for e in entries],
        "guess_label": "Guess the Shiny",
        "shiny_path": shiny_path,
        "cry_str": str(cry_path) if cry_path.is_file() else None,
        "question_cry_offset": None,
        "mute_pokeball_sfx": False,
    }


def _prepare_color_shift_round(pokemon_dirs):
    """1 Pokémon 4x gezeigt, 3x mit verschobenem Hue - welches ist die echte Farbe?"""
    pokemon_dir = random.choice(pokemon_dirs)
    shiny_path = pokemon_dir / "shiny.gif"
    if not shiny_path.is_file():
        raise FileNotFoundError(f"Shiny GIF not found: {shiny_path}")

    entries = [(str(shiny_path), None)]
    for _ in range(3):
        degrees = random.uniform(HUE_SHIFT_MIN_DEGREES, HUE_SHIFT_MAX_DEGREES)
        degrees *= random.choice([-1, 1])
        entries.append(
            (str(shiny_path), lambda frame, d=degrees: _hue_shift_frame(frame, d))
        )
    random.shuffle(entries)

    cry_path = pokemon_dir / "cry.ogg"
    return {
        "gif_paths": [e[0] for e in entries],
        "color_transforms": [e[1] for e in entries],
        "guess_label": "Spot the REAL Shiny!",
        "shiny_path": shiny_path,
        "cry_str": str(cry_path) if cry_path.is_file() else None,
        "question_cry_offset": None,
        "mute_pokeball_sfx": False,
    }


def _prepare_cry_round(pokemon_dirs):
    """4 Silhouetten, Cry-Sound einer davon - welches Pokémon ruft?"""
    selected_dirs = random.sample(pokemon_dirs, k=4)
    answer_dir = random.choice(selected_dirs)

    entries = []
    for d in selected_dirs:
        normal_path = d / "normal.gif"
        if not normal_path.is_file():
            raise FileNotFoundError(f"Normal GIF not found: {normal_path}")
        entries.append((str(normal_path), _silhouette_frame))
    random.shuffle(entries)

    shiny_path = answer_dir / "shiny.gif"
    cry_path = answer_dir / "cry.ogg"
    return {
        "gif_paths": [e[0] for e in entries],
        "color_transforms": [e[1] for e in entries],
        "guess_label": "Guess by the Cry!",
        "shiny_path": shiny_path,
        "cry_str": str(cry_path) if cry_path.is_file() else None,
        # Marker: wird unten zu zwei tatsächlichen Zeitpunkten aufgelöst,
        # sobald pokeball_duration bekannt ist.
        "question_cry_offset": True,
        # Pokéball-SFX würde den Cry übertönen -> für diesen Rundentyp stumm.
        "mute_pokeball_sfx": True,
    }


def _create_round(pokemon_dirs, background_frame, color_distances, round_type=None):
    round_type = round_type or _pick_round_type()

    if round_type == "color_shift":
        setup = _prepare_color_shift_round(pokemon_dirs)
    elif round_type == "cry":
        setup = _prepare_cry_round(pokemon_dirs)
    else:
        setup = _prepare_species_round(pokemon_dirs, color_distances)

    gif_order = setup["gif_paths"]
    color_transforms = setup["color_transforms"]
    shiny_path = setup["shiny_path"]
    cry_str = setup["cry_str"]

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

    if setup["mute_pokeball_sfx"]:
        pokeball_sfx_offset = None

    # Cry beim Cry-Rundentyp 2x während der Fragephase abspielen (direkt
    # beim Erscheinen der Silhouetten, dann nochmal auf halber Strecke),
    # damit er trotz stummgeschaltetem Pokéball-SFX gut hörbar ist.
    question_cry_offsets = None
    if setup["question_cry_offset"] is not None:
        remaining = QUESTION_DURATION - pokeball_duration
        question_cry_offsets = [pokeball_duration, pokeball_duration + remaining / 2]

    pokemon_duration = QUESTION_DURATION - pokeball_duration
    pokemon_quads = _build_quadrants(
        pokemon_duration,
        gif_order,
        pop_scale=True,
        fixed_scale=None,
        color_transforms=color_transforms,
    )
    pokemon_quads = [c.set_start(pokeball_duration).fx(vfx.fadein, 0.2) for c in pokemon_quads]
    elements_q.extend(pokemon_quads)

    background_q = CompositeVideoClip(
        elements_q,
        size=(WIDTH, HEIGHT)
    ).set_duration(QUESTION_DURATION)

    # Guess-Text (rundentyp-abhängig) mittig über der Healthbar (Pillow + Pokémon-Font)
    guess_text = _build_guess_text_clip(setup["guess_label"], QUESTION_DURATION)

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

    # Rückgabe: Video-Clip, Cry-Audio-Pfad, Pokéball-SFX-Offset, Liste von
    # Cry-Offsets während der Fragephase (nur beim Cry-Rundentyp gesetzt),
    # Zeitpunkt (innerhalb der Runde) an dem das Reveal beginnt.
    return round_clip, cry_str, pokeball_sfx_offset, question_cry_offsets, QUESTION_DURATION


def _create_stat_round(pokemon_dirs, background_frame, group):
    """4 verschiedene Pokémon mit ähnlichem Wert in einer Statkategorie -
    welches hat den höchsten Wert? Werte bleiben während der Frage verdeckt,
    Gewinner wird im Reveal groß gezeigt."""
    entries = group["entries"]
    stat_key = group["stat_key"]
    stat_label = STAT_LABELS[stat_key]
    winner_name = group["winner_name"]

    dirs_by_name = {d.name: d for d in pokemon_dirs}
    gif_paths = [str(dirs_by_name[name] / "normal.gif") for name, _ in entries]

    winner_dir = dirs_by_name[winner_name]
    cry_path = winner_dir / "cry.ogg"
    cry_str = str(cry_path) if cry_path.is_file() else None

    # -------------------- Teil 1: Frage --------------------
    elements_q = []
    if background_frame is not None:
        elements_q.append(ImageClip(background_frame).set_duration(STAT_QUESTION_DURATION))
    elements_q.extend(
        _build_quadrants(STAT_QUESTION_DURATION, gif_paths, pop_scale=True)
    )

    title_text = _build_text_clip(
        f"Which Pokémon has the highest {stat_label}?",
        STAT_QUESTION_DURATION, y_ratio=0.45, font_size=int(FONT_SIZE * 0.6),
    )
    healthbar_clip = _build_healthbar(STAT_QUESTION_DURATION)

    question_clip = CompositeVideoClip(
        [*elements_q, title_text, healthbar_clip],
        size=(WIDTH, HEIGHT),
    ).set_duration(STAT_QUESTION_DURATION)

    # -------------------- Teil 2: Reveal --------------------
    # Alle 4 bleiben an ihrer Quadranten-Position sichtbar: Verlierer
    # verblassen langsam Richtung grau/transparent (nie ganz unsichtbar),
    # Gewinner pulsiert kurz größer/kleiner und liegt im Vordergrund.
    winner_idx = next(i for i, (name, _) in enumerate(entries) if name == winner_name)

    quad_w, quad_h = WIDTH // 2, HEIGHT // 2
    positions = [(0, 0), (quad_w, 0), (0, quad_h), (quad_w, quad_h)]
    sprite_max_w = quad_w * SPRITE_QUAD_RATIO
    sprite_max_h = quad_h * SPRITE_QUAD_RATIO

    reveal_quadrants = []
    for i, (path_str, pos) in enumerate(zip(gif_paths, positions)):
        is_winner = i == winner_idx
        transform = None if is_winner else (lambda f: _desaturate_frame(f, 0.6))
        clip = _load_gif_clip_ffmpeg_loop(Path(path_str), STAT_REVEAL_DURATION, color_transform=transform)

        desired_scale = min(sprite_max_w / clip.w, sprite_max_h / clip.h)
        base_scale = desired_scale if desired_scale < 1.0 else min(desired_scale, MAX_SCALE_UP)

        if is_winner:
            base_scale *= 1.15
            clip = clip.resize(
                lambda t, bs=base_scale: bs * (1 + 0.12 * np.sin(2 * np.pi * 1.2 * t))
            )
        else:
            clip = clip.resize(base_scale)
            clip = _apply_fade_mask(clip, start_opacity=1.0, end_opacity=0.45)

        quad_x, quad_y = pos
        x = quad_x + (quad_w - clip.w) / 2
        y = quad_y + (quad_h - clip.h) / 2
        clip = clip.set_position((x, y)).set_duration(STAT_REVEAL_DURATION)
        reveal_quadrants.append(clip)

    # Gewinner als letztes Element = oberste Ebene, damit er im Vordergrund steht.
    reveal_quadrants = (
        [c for i, c in enumerate(reveal_quadrants) if i != winner_idx]
        + [reveal_quadrants[winner_idx]]
    )

    # (x_center, y_ratio) je Quadrant, nah am jeweiligen Sprite - Reihenfolge
    # muss zu `positions` oben passen: oben-links, oben-rechts, unten-links,
    # unten-rechts.
    value_positions = [
        (WIDTH * 0.25, 0.10), (WIDTH * 0.75, 0.10),
        (WIDTH * 0.25, 0.87), (WIDTH * 0.75, 0.87),
    ]
    white = (255, 255, 255, 255)
    green = (80, 200, 80, 255)
    value_texts = [
        _build_text_clip(
            _format_stat_value(stat_key, value), STAT_REVEAL_DURATION,
            y_ratio=y_ratio, x_center=x_center, font_size=int(FONT_SIZE * 0.6),
            color=green if i == winner_idx else white,
        )
        for i, ((_, value), (x_center, y_ratio)) in enumerate(zip(entries, value_positions))
    ]

    insight_text = _build_text_clip(
        f"{winner_name.replace('-', ' ').title()} wins!",
        STAT_REVEAL_DURATION, y_ratio=0.48, font_size=int(FONT_SIZE * 0.55),
    )

    elements_r = []
    if background_frame is not None:
        elements_r.append(ImageClip(background_frame).set_duration(STAT_REVEAL_DURATION))
    elements_r.extend(reveal_quadrants)

    reveal_clip = CompositeVideoClip(
        [*elements_r, insight_text, *value_texts],
        size=(WIDTH, HEIGHT),
    ).set_duration(STAT_REVEAL_DURATION)

    round_clip = concatenate_videoclips([question_clip, reveal_clip])

    # Kein Pokéball-SFX, kein Fragephase-Cry bei diesem Rundentyp.
    return round_clip, cry_str, None, None, STAT_QUESTION_DURATION


# ---------------------------------------------------------------------------
# Finales Video (mehrere Runden + Musik + Cry)
# ---------------------------------------------------------------------------
def create_quiz_video(output_path: str = "quiz.mp4", round_type: str = None):
    """round_type=None: normale Mischung aus ROUND_TYPE_WEIGHTS (Shiny-Quiz).
    round_type="stat_compare": eigenständiges Stat-Vergleich-Video, alle
    Runden dieses Typs (siehe stat_video.py)."""
    assets_dir = Path("assets")
    all_dirs = [p for p in assets_dir.iterdir() if p.is_dir()]
    pokemon_dirs = [p for p in all_dirs if _is_valid_pokemon_dir(p)]

    if len(pokemon_dirs) < 4:
        raise ValueError(
            "Es wurden weniger als vier gültige Pokémon gefunden.\n"
            "Stelle sicher, dass genügend Pokémon mit animierten normal.gif und shiny.gif vorhanden sind."
        )

    print(f"{len(pokemon_dirs)} gültige Pokémon-Ordner gefunden.")

    color_distances = {}
    if round_type != "stat_compare":
        print("Berechne Shiny/Normal-Farbunterschiede...")
        for d in pokemon_dirs:
            try:
                color_distances[d] = _shiny_color_distance(d)
            except Exception:
                color_distances[d] = 100.0
        print(f"Farbunterschiede für {len(color_distances)} Pokémon berechnet.")

    stats_data = _load_stats_data()
    if round_type == "stat_compare" and not stats_data:
        raise ValueError(
            f"Keine {STATS_PATH} gefunden - für das Stat-Vergleich-Video wird "
            "fetch_pokemon_stats.py vorausgesetzt."
        )
    print(f"{len(stats_data)} Pokémon mit gecachten Statwerten geladen." if stats_data
          else "Hinweis: Keine data/pokemon_stats.json gefunden - stat_compare-Runden werden übersprungen.")

    background_frame = _load_random_background_frame()

    rounds = []
    cry_paths = []
    pokeball_offsets = []
    question_cry_offsets_per_round = []
    reveal_starts_per_round = []

    for round_idx in range(N_ROUNDS):
        if round_type == "stat_compare":
            group = None
            for _ in range(20):  # ein paar Versuche, falls keine passende Gruppe gefunden wird
                group = _find_stat_group(pokemon_dirs, stats_data)
                if group is not None:
                    break
            if group is None:
                raise RuntimeError("Konnte keine Stat-Vergleich-Gruppe finden.")
            round_clip, cry_path, pokeball_offset, question_cry_offsets, reveal_start = _create_stat_round(
                pokemon_dirs, background_frame, group
            )
        else:
            chosen_type = round_type or _pick_round_type()
            round_clip, cry_path, pokeball_offset, question_cry_offsets, reveal_start = _create_round(
                pokemon_dirs, background_frame, color_distances, round_type=chosen_type
            )

        rounds.append(round_clip)
        cry_paths.append(cry_path)
        pokeball_offsets.append(pokeball_offset)
        question_cry_offsets_per_round.append(question_cry_offsets)
        reveal_starts_per_round.append(reveal_start)
        print(f"Runde {round_idx + 1} erzeugt.")

    final = concatenate_videoclips(rounds)
    total_duration = final.duration

    audio_clips = []

    if BACKGROUND_MUSIC_DIR.is_dir():
        music_files = sorted(
            mf for mf in BACKGROUND_MUSIC_DIR.glob("*.mp3")
            if not mf.name.startswith("._") and not mf.name.startswith(".")
        )
        print("Gefundene Background-MP3s:", [str(mf) for mf in music_files])

        if music_files:
            music_file = random.choice(music_files)
            print(f"Hintergrundmusik: {music_file}")
            bg = AudioFileClip(str(music_file))
            bg = bg.subclip(0, min(bg.duration, total_duration))
            audio_clips.append(bg)
        else:
            print("Hinweis: Keine gültigen Hintergrundmusik-Dateien gefunden.")
    else:
        print("Hinweis: BACKGROUND_MUSIC_DIR existiert nicht.")

    current_start = 0.0
    for round_clip, cry_path, pokeball_offset, question_cry_offsets, reveal_start_in_round in zip(
        rounds, cry_paths, pokeball_offsets, question_cry_offsets_per_round, reveal_starts_per_round
    ):
        # Cry-Sound im Reveal - reveal_start_in_round kommt direkt aus der
        # jeweiligen Rundenerzeugung (Frage-Phasen-Länge variiert je
        # Rundentyp, z.B. STAT_QUESTION_DURATION statt QUESTION_DURATION).
        if cry_path:
            cry = AudioFileClip(cry_path)
            reveal_duration_in_round = round_clip.duration - reveal_start_in_round
            cry = cry.subclip(0, min(cry.duration, reveal_duration_in_round))
            cry = cry.set_start(current_start + reveal_start_in_round)
            audio_clips.append(cry)

        # Cry-Sound schon während der Fragephase (Cry-Rundentyp), 2x damit er
        # trotz stummgeschaltetem Pokéball-SFX gut hörbar ist
        if cry_path and question_cry_offsets:
            for offset in question_cry_offsets:
                question_cry = AudioFileClip(cry_path)
                question_cry = question_cry.subclip(
                    0, min(question_cry.duration, QUESTION_DURATION - offset)
                )
                question_cry = question_cry.set_start(current_start + offset)
                audio_clips.append(question_cry)

        # Pokéball-SFX in der Fragephase, zur Hälfte der Pokéball-Duration
        if pokeball_offset is not None and POKEBALL_SFX_PATH.is_file():
            sfx = AudioFileClip(str(POKEBALL_SFX_PATH))
            sfx = sfx.set_start(current_start + pokeball_offset)
            audio_clips.append(sfx)

        current_start += round_clip.duration

    if audio_clips:
        final_audio = CompositeAudioClip(audio_clips).set_duration(total_duration)
        final = final.set_audio(final_audio)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    final.write_videofile(
        output_path,
        fps=30,
        codec="libx264",
        audio=bool(audio_clips),
        audio_codec="aac",
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Create shiny Pokémon quiz video (multi-round)")
    parser.add_argument(
        "--output",
        type=str,
        default="quiz.mp4",
        help="Output video file path",
    )
    parser.add_argument(
        "--round-type",
        type=str,
        default=None,
        choices=["species", "color_shift", "cry", "stat_compare"],
        help="Falls gesetzt, bestehen ALLE Runden aus diesem Typ statt der normalen Mischung "
             "(z.B. stat_compare für das eigenständige Stat-Vergleich-Video)",
    )
    args = parser.parse_args()

    create_quiz_video(output_path=args.output, round_type=args.round_type)