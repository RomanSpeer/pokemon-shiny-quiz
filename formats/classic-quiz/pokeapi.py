"""Kleiner Client für die PokeAPI (https://pokeapi.co).

Holt alle Daten, die wir für das Quiz-Video brauchen: Basisdaten, Typen samt
Effektivitäten, Fähigkeit, Pokédex-Eintrag und die URL zum Schrei (Cry).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from functools import lru_cache

import requests

BASE_URL = "https://pokeapi.co/api/v2"

ALL_TYPES = [
    "normal", "fire", "water", "electric", "grass", "ice", "fighting", "poison",
    "ground", "flying", "psychic", "bug", "rock", "ghost", "dragon", "dark",
    "steel", "fairy",
]


@dataclass
class TypeMatchups:
    weak_4x: list[str] = field(default_factory=list)   # Takes 4x damage
    weak_2x: list[str] = field(default_factory=list)   # Takes 2x damage
    resist: list[str] = field(default_factory=list)    # Takes reduced damage
    immune: list[str] = field(default_factory=list)    # Takes no damage
    normal: list[str] = field(default_factory=list)    # Takes normal damage


@dataclass
class PokemonData:
    id: int
    name: str
    display_name: str
    genus: str
    types: list[str]
    height_m: float
    weight_kg: float
    ability_name: str
    ability_effect: str
    matchups: TypeMatchups
    artwork_url: str
    sprite_url: str
    cry_url: str


@lru_cache(maxsize=None)
def _get(url: str) -> dict:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_pokemon_count() -> int:
    """Anzahl der aktuell in der PokeAPI bekannten Pokémon-Spezies."""
    data = _get(f"{BASE_URL}/pokemon-species?limit=1")
    return data["count"]


def _clean_flavor_text(text: str) -> str:
    return text.replace("\n", " ").replace("\f", " ").replace("­", "").strip()


def _pick_localized(entries: list[dict], lang: str, text_key: str, fallback_lang: str = "en") -> str | None:
    for entry in entries:
        if entry["language"]["name"] == lang:
            return _clean_flavor_text(entry[text_key])
    for entry in entries:
        if entry["language"]["name"] == fallback_lang:
            return _clean_flavor_text(entry[text_key])
    return None


def _get_type_damage_relations(type_name: str) -> dict:
    data = _get(f"{BASE_URL}/type/{type_name}")
    return data["damage_relations"]


def compute_type_matchups(types: list[str]) -> TypeMatchups:
    """Combines the type multipliers of all of a Pokémon's types.

    A dual-type Pokémon inherits the weaknesses/resistances of both types,
    which stack multiplicatively (e.g. 2x * 2x = 4x damage). Starting every
    type at a 1.0 multiplier means a type that isn't mentioned by either of
    the Pokémon's types (or one that cancels out, e.g. 2x * 0.5x) correctly
    ends up in the "normal damage" bucket instead of being silently dropped.
    """
    multiplier: dict[str, float] = {t: 1.0 for t in ALL_TYPES}

    def apply(type_names: list[dict], factor: float) -> None:
        for t in type_names:
            name = t["name"]
            if name in multiplier:
                multiplier[name] *= factor

    for type_name in types:
        relations = _get_type_damage_relations(type_name)
        apply(relations["double_damage_from"], 2.0)
        apply(relations["half_damage_from"], 0.5)
        apply(relations["no_damage_from"], 0.0)

    matchups = TypeMatchups()
    for type_name, factor in sorted(multiplier.items()):
        if factor == 0:
            matchups.immune.append(type_name)
        elif factor >= 4:
            matchups.weak_4x.append(type_name)
        elif factor > 1:
            matchups.weak_2x.append(type_name)
        elif factor < 1:
            matchups.resist.append(type_name)
        else:
            matchups.normal.append(type_name)
    return matchups


def fetch_pokemon(identifier: int | str) -> PokemonData:
    pokemon = _get(f"{BASE_URL}/pokemon/{identifier}")
    species = _get(f"{BASE_URL}/pokemon-species/{pokemon['id']}")

    types = [t["type"]["name"] for t in sorted(pokemon["types"], key=lambda t: t["slot"])]
    matchups = compute_type_matchups(types)

    # Prefers a non-hidden ability so the quiz isn't too easy.
    abilities = sorted(pokemon["abilities"], key=lambda a: a["is_hidden"])
    ability_ref = abilities[0]["ability"]
    ability_data = _get(ability_ref["url"])
    ability_name = _pick_localized(ability_data["names"], "en", "name") or ability_ref["name"]
    ability_effect = _pick_localized(ability_data["effect_entries"], "en", "short_effect") or ""

    genus = _pick_localized(species["genera"], "en", "genus") or ""
    display_name = _pick_localized(species["names"], "en", "name") or pokemon["name"].capitalize()

    artwork_url = pokemon["sprites"]["other"]["official-artwork"]["front_default"]
    sprite_url = pokemon["sprites"]["front_default"]
    cries = pokemon.get("cries") or {}
    cry_url = cries.get("latest") or cries.get("legacy")

    return PokemonData(
        id=pokemon["id"],
        name=pokemon["name"],
        display_name=display_name,
        genus=genus,
        types=types,
        height_m=pokemon["height"] / 10,
        weight_kg=pokemon["weight"] / 10,
        ability_name=ability_name,
        ability_effect=ability_effect,
        matchups=matchups,
        artwork_url=artwork_url,
        sprite_url=sprite_url,
        cry_url=cry_url,
    )


def fetch_random_pokemon(max_attempts: int = 30, exclude_ids: set[int] | None = None) -> PokemonData:
    """Wählt ein zufälliges Pokémon, das einen Cry-Sound hat und nicht in exclude_ids ist.

    Baut den Kandidaten-Pool einmal auf und mischt ihn, statt unabhängig zu würfeln,
    damit wir bei einer wachsenden exclude_ids-Liste nicht wiederholt dieselben
    (bereits ausgeschlossenen) IDs treffen und `max_attempts` sinnlos verbrauchen.
    """
    exclude_ids = exclude_ids or set()
    pool = [i for i in range(1, get_pokemon_count() + 1) if i not in exclude_ids]
    if not pool:
        raise RuntimeError(
            "Every Pokémon has already been used - reset used_pokemon.json to start over."
        )
    random.shuffle(pool)

    last_error: Exception | None = None
    for candidate_id in pool[:max_attempts]:
        try:
            data = fetch_pokemon(candidate_id)
            if data.cry_url and data.artwork_url:
                return data
        except requests.RequestException as exc:
            last_error = exc
    raise RuntimeError("Konnte kein passendes Pokémon finden") from last_error
