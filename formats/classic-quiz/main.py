"""Generates a 'Guess the Pokémon' quiz video with data from the PokeAPI.

Usage:
    python main.py                # random Pokémon
    python main.py pikachu        # specific Pokémon by name
    python main.py 25             # specific Pokémon by Pokédex number
"""
from __future__ import annotations

import sys
from pathlib import Path

from history import load_used_ids, record_used
from pokeapi import fetch_pokemon, fetch_random_pokemon
from video import build_video

OUTPUT_DIR = Path(__file__).parent / "output"


def main() -> None:
    if len(sys.argv) > 1:
        identifier = sys.argv[1].lower()
        print(f"Fetching data for '{identifier}' from PokeAPI...")
        pokemon = fetch_pokemon(identifier)
    else:
        print("Picking a random Pokémon not used before...")
        pokemon = fetch_random_pokemon(exclude_ids=load_used_ids())

    print(f"Creating quiz video for: {pokemon.display_name} (#{pokemon.id})")
    output_path = OUTPUT_DIR / f"quiz_{pokemon.id:04d}_{pokemon.name}.mp4"
    build_video(pokemon, output_path)
    record_used(pokemon.id, pokemon.name)
    print(f"Done! Video saved to: {output_path}")


if __name__ == "__main__":
    main()
