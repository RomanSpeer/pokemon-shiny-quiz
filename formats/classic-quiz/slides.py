"""Renders the individual quiz slides as PIL images (1080x1920, 9:16)."""
from __future__ import annotations

import io
import textwrap
from functools import lru_cache
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

from pokeapi import PokemonData

WIDTH, HEIGHT = 1080, 1920

BG_COLOR = (17, 24, 39)          # dark blue-gray
CARD_COLOR = (30, 41, 59)
TEXT_COLOR = (245, 245, 245)
MUTED_COLOR = (156, 163, 175)
ACCENT_COLOR = (250, 204, 21)    # Poké Ball yellow

ICON_DIR = Path(__file__).parent / "assets" / "type_icons"

# Tries macOS's bundled Arial first (local dev), then Liberation Sans (metric-compatible
# Arial substitute, installed via `fonts-liberation` on the Ubuntu CI runner), then whatever
# PIL ships as a last resort.
FONT_CANDIDATES = {
    "Arial Bold": [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ],
    "Arial": [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ],
    "Arial Black": [
        "/System/Library/Fonts/Supplemental/Arial Black.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ],
}


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES.get(name, []):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


FONT_TITLE = _font("Arial Bold", 72)
FONT_HEADING = _font("Arial Bold", 56)
FONT_HEADING_SM = _font("Arial Bold", 44)
FONT_BODY = _font("Arial", 44)
FONT_BODY_BOLD = _font("Arial Bold", 44)
FONT_SMALL = _font("Arial", 34)
FONT_TINY = _font("Arial", 27)
FONT_HUGE = _font("Arial Black", 96)


TIMER_MARGIN = 60
TIMER_HEIGHT = 22
TIMER_Y = 1540  # low on screen, above where Shorts overlays title/description/progress
TIMER_INSET = 4


def timer_fill_rect() -> tuple[int, int, int, int]:
    """Inner (x0, y0, x1, y1) fill area of the timer bar, inset from its border.

    video.py reads this to know exactly which pixels to overwrite per frame when
    animating the countdown, without having to re-render the slide with PIL each frame.
    """
    x0 = TIMER_MARGIN + TIMER_INSET
    y0 = TIMER_Y + TIMER_INSET
    x1 = WIDTH - TIMER_MARGIN - TIMER_INSET
    y1 = TIMER_Y + TIMER_HEIGHT - TIMER_INSET
    return x0, y0, x1, y1


def _draw_timer_track(draw: ImageDraw.ImageDraw) -> None:
    x0, y0 = TIMER_MARGIN, TIMER_Y
    x1, y1 = WIDTH - TIMER_MARGIN, TIMER_Y + TIMER_HEIGHT
    draw.rounded_rectangle([x0, y0, x1, y1], radius=TIMER_HEIGHT / 2, fill=CARD_COLOR,
                            outline=MUTED_COLOR, width=3)


def _base_canvas(show_timer: bool = True) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    if show_timer:
        _draw_timer_track(draw)
    return img, draw


def _text_at(draw: ImageDraw.ImageDraw, cx: float, y: int, text: str, font: ImageFont.FreeTypeFont, fill=TEXT_COLOR) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    draw.text((cx - w / 2, y), text, font=font, fill=fill)
    return bbox[3] - bbox[1]


def _center_text(draw: ImageDraw.ImageDraw, y: int, text: str, font: ImageFont.FreeTypeFont, fill=TEXT_COLOR) -> int:
    return _text_at(draw, WIDTH / 2, y, text, font, fill)


def _wrapped_text(draw: ImageDraw.ImageDraw, y: int, text: str, font: ImageFont.FreeTypeFont,
                   max_width: int, fill=TEXT_COLOR, line_spacing: int = 14) -> int:
    avg_char_w = draw.textlength("x", font=font) or 1
    wrap_width = max(10, int(max_width / avg_char_w))
    lines = textwrap.wrap(text, width=wrap_width)
    cur_y = y
    for line in lines:
        h = _center_text(draw, cur_y, line, font, fill)
        cur_y += h + line_spacing
    return cur_y - y


@lru_cache(maxsize=None)
def _load_type_icon(type_name: str, size: int) -> Image.Image:
    icon = Image.open(ICON_DIR / f"{type_name}.png").convert("RGBA")
    icon.thumbnail((size, size), Image.LANCZOS)
    return icon


def _type_icon_row(img: Image.Image, draw: ImageDraw.ImageDraw, y: int, type_names: list[str],
                    icon_size: int = 130, show_labels: bool = True,
                    label_font: ImageFont.FreeTypeFont = FONT_SMALL,
                    max_width: int = 980, row_gap: int = 20) -> int:
    """Draws centered rows of type icon badges (from partywhale/pokemon-type-icons), optionally
    with the type name printed underneath each icon. Each icon gets its own slot sized to fit
    its label so labels never overlap, and rows wrap once they'd exceed max_width."""
    if not type_names:
        return 0
    gap = 30
    label_gap = 14

    slots = []
    for t in type_names:
        w = icon_size
        if show_labels:
            bbox = draw.textbbox((0, 0), t.upper(), font=label_font)
            w = max(w, bbox[2] - bbox[0])
        slots.append((t, w))

    rows: list[list[tuple[str, int]]] = []
    current_row: list[tuple[str, int]] = []
    current_w = 0
    for t, w in slots:
        candidate_w = w if not current_row else current_w + gap + w
        if current_row and candidate_w > max_width:
            rows.append(current_row)
            current_row, current_w = [(t, w)], w
        else:
            current_row.append((t, w))
            current_w = candidate_w
    if current_row:
        rows.append(current_row)

    cur_y = y
    for row in rows:
        row_w = sum(w for _, w in row) + gap * (len(row) - 1)
        x = (WIDTH - row_w) / 2
        row_bottom = cur_y
        for t, slot_w in row:
            icon = _load_type_icon(t, icon_size)
            cx = x + slot_w / 2
            icon_x = int(cx - icon.width / 2)
            icon_y = int(cur_y + (icon_size - icon.height) / 2)
            img.paste(icon, (icon_x, icon_y), icon)
            bottom = cur_y + icon_size
            if show_labels:
                h = _text_at(draw, cx, bottom + label_gap, t.upper(), label_font, TEXT_COLOR)
                bottom += label_gap + h
            row_bottom = max(row_bottom, bottom)
            x += slot_w + gap
        cur_y = row_bottom + row_gap

    return cur_y - row_gap - y


def _fetch_image(url: str) -> Image.Image:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert("RGBA")


def _paste_centered(base: Image.Image, overlay: Image.Image, y: int) -> int:
    x = (WIDTH - overlay.width) // 2
    base.paste(overlay, (x, y), overlay)
    return overlay.height


def slide_intro(pokemon: PokemonData) -> Image.Image:
    img, draw = _base_canvas(show_timer=False)
    _center_text(draw, 860, "GUESS THE FOLLOWING", FONT_TITLE, ACCENT_COLOR)
    _center_text(draw, 950, "POKÉMON?", FONT_TITLE, ACCENT_COLOR)
    return img


def slide_type_chart(pokemon: PokemonData) -> Image.Image:
    img, draw = _base_canvas()

    y = 120
    _center_text(draw, y, "TYPE CHART", FONT_TITLE, ACCENT_COLOR)
    y += 140

    sections = []
    if pokemon.matchups.weak_4x:
        sections.append(("4× WEAK AGAINST", pokemon.matchups.weak_4x, (239, 68, 68)))
    sections.append(("2× WEAK AGAINST", pokemon.matchups.weak_2x, (248, 113, 113)))
    sections.append(("RESISTANT TO", pokemon.matchups.resist, (74, 222, 128)))
    sections.append(("IMMUNE TO", pokemon.matchups.immune, (96, 165, 250)))
    sections.append(("NORMAL DAMAGE FROM", pokemon.matchups.normal, MUTED_COLOR))

    for label, types, color in sections:
        y += 18
        _center_text(draw, y, label, FONT_HEADING_SM, color)
        y += 66
        if types:
            y += _type_icon_row(img, draw, y, types, icon_size=90, label_font=FONT_TINY) + 18
        else:
            _center_text(draw, y, "none", FONT_BODY, MUTED_COLOR)
            y += 50

    return img


def slide_cry(pokemon: PokemonData) -> Image.Image:
    img, draw = _base_canvas()
    _center_text(draw, 700, "LISTEN TO ITS", FONT_TITLE, ACCENT_COLOR)
    _center_text(draw, 790, "CRY!", FONT_TITLE, ACCENT_COLOR)

    # simple soundwave icon
    bar_y = 1050
    bar_count = 9
    bar_w = 26
    gap = 20
    heights = [40, 80, 130, 180, 220, 180, 130, 80, 40]
    total_w = bar_count * bar_w + (bar_count - 1) * gap
    x = (WIDTH - total_w) / 2
    for h in heights:
        draw.rounded_rectangle(
            [x, bar_y - h / 2, x + bar_w, bar_y + h / 2], radius=bar_w / 2, fill=ACCENT_COLOR
        )
        x += bar_w + gap

    return img


def slide_ability(pokemon: PokemonData) -> Image.Image:
    img, draw = _base_canvas()

    y = 700
    _center_text(draw, y, "ABILITY", FONT_TITLE, ACCENT_COLOR)
    y += 130
    _center_text(draw, y, pokemon.ability_name.upper(), FONT_HEADING, TEXT_COLOR)
    y += 110
    if pokemon.ability_effect:
        _wrapped_text(draw, y, pokemon.ability_effect, FONT_BODY, max_width=860, fill=MUTED_COLOR)

    return img


def slide_stats(pokemon: PokemonData) -> Image.Image:
    img, draw = _base_canvas()

    y = 640
    _center_text(draw, y, "HEIGHT & WEIGHT", FONT_TITLE, ACCENT_COLOR)

    y += 220
    _center_text(draw, y, f"{pokemon.height_m:.1f} m", FONT_HUGE, TEXT_COLOR)
    y += 130
    _center_text(draw, y, "HEIGHT", FONT_SMALL, MUTED_COLOR)

    y += 180
    _center_text(draw, y, f"{pokemon.weight_kg:.1f} kg", FONT_HUGE, TEXT_COLOR)
    y += 130
    _center_text(draw, y, "WEIGHT", FONT_SMALL, MUTED_COLOR)

    return img


def _pixelated_silhouette(sprite: Image.Image, pixel_blocks: int = 20, display_size: int = 560) -> Image.Image:
    """Blackens a sprite to a silhouette (via its alpha mask), then downscales and
    scales back up with nearest-neighbor sampling to get a chunky, pixelated look."""
    sprite = sprite.convert("RGBA")
    alpha = sprite.split()[-1]
    black = Image.new("RGBA", sprite.size, (10, 10, 14, 255))
    transparent = Image.new("RGBA", sprite.size, (0, 0, 0, 0))
    silhouette = Image.composite(black, transparent, alpha)

    w, h = silhouette.size
    scale = pixel_blocks / max(w, h)
    tiny = silhouette.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.NEAREST)

    scale_up = display_size / max(tiny.size)
    return tiny.resize((round(tiny.width * scale_up), round(tiny.height * scale_up)), Image.NEAREST)


def slide_silhouette(pokemon: PokemonData, sprite: Image.Image) -> Image.Image:
    img, draw = _base_canvas()
    _center_text(draw, 160, "LAST CHANCE", FONT_TITLE, ACCENT_COLOR)
    _center_text(draw, 250, "TO GUESS!", FONT_TITLE, ACCENT_COLOR)

    pixelated = _pixelated_silhouette(sprite)
    _paste_centered(img, pixelated, 680)

    return img


def slide_reveal(pokemon: PokemonData, artwork: Image.Image) -> Image.Image:
    img, draw = _base_canvas(show_timer=False)
    _center_text(draw, 100, "IT'S...", FONT_TITLE, ACCENT_COLOR)

    art = artwork.copy()
    art.thumbnail((750, 750), Image.LANCZOS)
    _paste_centered(img, art, 260)

    y = 1080
    _center_text(draw, y, pokemon.display_name.upper(), FONT_HUGE, TEXT_COLOR)
    y += 130
    if pokemon.genus:
        _center_text(draw, y, pokemon.genus, FONT_BODY, MUTED_COLOR)
        y += 80
    y += 30
    _type_icon_row(img, draw, y, pokemon.types)

    return img
