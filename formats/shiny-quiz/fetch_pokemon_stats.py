"""Fetch base stats, height and weight for every Pokémon we have assets for
and cache them locally as JSON, so quiz_video.py can compare stats without
hitting PokeAPI during video generation.

Run this once (and again whenever assets/ changes):
    python fetch_pokemon_stats.py

Output: data/pokemon_stats.json, e.g.
    {
        "pikachu": {
            "hp": 35, "attack": 55, "defense": 40,
            "special-attack": 50, "special-defense": 50, "speed": 90,
            "height": 4, "weight": 60
        },
        ...
    }
"""
import json
import time
from pathlib import Path

import requests
from tqdm import tqdm

BASE_URL = "https://pokeapi.co/api/v2"
ASSETS_ROOT = Path("assets")
OUTPUT_PATH = Path("data/pokemon_stats.json")
REQUEST_DELAY = 0.6


def _is_valid_pokemon_dir(p: Path) -> bool:
    return p.is_dir() and (p / "normal.gif").is_file() and (p / "shiny.gif").is_file()


def _fetch_stats(name: str) -> dict:
    resp = requests.get(f"{BASE_URL}/pokemon/{name}", timeout=15)
    resp.raise_for_status()
    data = resp.json()

    stats = {s["stat"]["name"]: s["base_stat"] for s in data["stats"]}
    stats["height"] = data["height"]
    stats["weight"] = data["weight"]
    return stats


def main() -> None:
    pokemon_dirs = sorted(p for p in ASSETS_ROOT.iterdir() if _is_valid_pokemon_dir(p))
    print(f"{len(pokemon_dirs)} Pokémon-Ordner gefunden.")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    all_stats: dict = {}
    if OUTPUT_PATH.is_file():
        all_stats = json.loads(OUTPUT_PATH.read_text())
        print(f"{len(all_stats)} bereits vorhandene Einträge geladen, werden ergänzt/aktualisiert.")

    for pokemon_dir in tqdm(pokemon_dirs, desc="Pokémon", unit="poke"):
        name = pokemon_dir.name
        try:
            all_stats[name] = _fetch_stats(name)
        except Exception as exc:  # noqa: BLE001
            tqdm.write(f"Fehler bei {name}: {exc}")
        time.sleep(REQUEST_DELAY)

    OUTPUT_PATH.write_text(json.dumps(all_stats, indent=2, sort_keys=True))
    print(f"{len(all_stats)} Einträge gespeichert unter {OUTPUT_PATH}.")


if __name__ == "__main__":
    main()
