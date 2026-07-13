"""Tracks which Pokémon have already had a quiz video made, so we can skip them
next time and avoid repeats across runs (e.g. the same Pokémon on back-to-back days).

Persisted to used_pokemon.json, which is meant to be committed back to the repo
after each run (see .github/workflows/generate-and-upload.yml) so the history
survives across CI runs, not just within a single one.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

HISTORY_PATH = Path(__file__).parent / "used_pokemon.json"


def _read_entries() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    return json.loads(HISTORY_PATH.read_text())


def load_used_ids() -> set[int]:
    return {entry["id"] for entry in _read_entries()}


def record_used(pokemon_id: int, name: str) -> None:
    entries = _read_entries()
    entries.append({
        "id": pokemon_id,
        "name": name,
        "date": date.today().isoformat(),
    })
    HISTORY_PATH.write_text(json.dumps(entries, indent=2) + "\n")
