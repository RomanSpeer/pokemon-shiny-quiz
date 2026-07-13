"""Baut aus den gerenderten Slides ein MP4-Video inkl. Cry-Audio zusammen."""
from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import requests
from moviepy import AudioFileClip, CompositeAudioClip, ImageClip, VideoClip, concatenate_videoclips
from moviepy.audio.fx import AudioLoop, MultiplyVolume
from PIL import Image

import slides
from pokeapi import PokemonData

FPS = 30
SLIDE_DURATION = 7.0
INTRO_DURATION = 2.0

MUSIC_DIR = Path(__file__).parent / "video_background_music"
MUSIC_VOLUME = 0.15  # kept low so it sits under the cries instead of competing with them

BAR_GREEN = (74, 222, 128)
BAR_YELLOW = (250, 204, 21)
BAR_RED = (239, 68, 68)


def _to_array(img: Image.Image) -> np.ndarray:
    return np.array(img.convert("RGB"))


def _download_bytes(url: str) -> bytes:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.content


def _bar_color(fraction: float) -> tuple[int, int, int]:
    if fraction > 0.5:
        return BAR_GREEN
    if fraction > 0.2:
        return BAR_YELLOW
    return BAR_RED


def _slide_clip(img: Image.Image, duration: float) -> VideoClip:
    """Wraps a static slide image in a clip that animates a Pokémon-style HP bar,
    baked into the timer track at the top of the slide, depleting over `duration`."""
    base = _to_array(img)
    x0, y0, x1, y1 = slides.timer_fill_rect()
    full_width = x1 - x0

    def make_frame(t: float) -> np.ndarray:
        frame = base.copy()
        fraction = max(0.0, 1.0 - t / duration)
        fill_w = int(round(full_width * fraction))
        if fill_w > 0:
            frame[y0:y1, x0:x0 + fill_w] = _bar_color(fraction)
        return frame

    return VideoClip(make_frame, duration=duration)


def _random_background_music(duration: float) -> AudioFileClip | None:
    """Picks a random track from video_background_music/, loops it to cover the
    full video, and turns it down so it sits quietly under the cry sound effects."""
    tracks = sorted(MUSIC_DIR.glob("*.mp3"))
    if not tracks:
        return None
    track = random.choice(tracks)
    music = AudioFileClip(str(track))
    return music.with_effects([AudioLoop(duration=duration), MultiplyVolume(MUSIC_VOLUME)])


def build_video(pokemon: PokemonData, output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    artwork = slides._fetch_image(pokemon.artwork_url)
    sprite = slides._fetch_image(pokemon.sprite_url)

    clips: list[VideoClip] = []

    def add_slide(img: Image.Image, duration: float = SLIDE_DURATION) -> None:
        clips.append(_slide_clip(img, duration))

    # Intro is just a quick title card: no timer bar to animate, so a plain static clip.
    clips.append(ImageClip(_to_array(slides.slide_intro(pokemon))).with_duration(INTRO_DURATION))

    add_slide(slides.slide_type_chart(pokemon))

    # Cry slide: plays the cry twice, the 2nd time starting at the timer's halfway point.
    cry_bytes = _download_bytes(pokemon.cry_url)
    cry_tmp_path = output_path.parent / f"_cry_{pokemon.id}.ogg"
    cry_tmp_path.write_bytes(cry_bytes)
    cry_audio = AudioFileClip(str(cry_tmp_path))
    first_start = 0.4
    cry_duration = max(SLIDE_DURATION, 2 * cry_audio.duration + 1.2)
    second_start = cry_duration / 2
    cry_track = CompositeAudioClip([
        cry_audio.with_start(first_start),
        cry_audio.with_start(second_start),
    ])
    cry_clip = _slide_clip(slides.slide_cry(pokemon), cry_duration).with_audio(cry_track)
    clips.append(cry_clip)

    add_slide(slides.slide_ability(pokemon))
    add_slide(slides.slide_stats(pokemon))
    add_slide(slides.slide_silhouette(pokemon, sprite))

    # Reveal has no timer bar (it's the answer, not a guessing beat) but plays the cry
    # once more so viewers hear it alongside the answer.
    reveal_clip = ImageClip(_to_array(slides.slide_reveal(pokemon, artwork))).with_duration(SLIDE_DURATION)
    clips.append(reveal_clip.with_audio(cry_audio.with_start(0.4)))

    final = concatenate_videoclips(clips, method="compose")

    music = _random_background_music(final.duration)
    if music is not None:
        final = final.with_audio(CompositeAudioClip([final.audio, music]))

    final.write_videofile(
        str(output_path),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        logger=None,
    )

    cry_tmp_path.unlink(missing_ok=True)
    return output_path
