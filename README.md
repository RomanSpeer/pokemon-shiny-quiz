# Pokémon Quiz Videos (Monorepo)

Dieses Repo enthält zwei unabhängige Pipelines, die automatisiert Pokémon-Quiz-Videos
erzeugen und als YouTube Shorts hochladen. Beide nutzen die [PokeAPI](https://pokeapi.co),
haben aber unterschiedliche Formate, Abhängigkeiten und Video-Stile - deshalb leben sie
als getrennte Unterprojekte unter `formats/`, statt sich einen gemeinsamen Code zu teilen.

## Formate

- **`formats/shiny-quiz/`** - "Guess the Shiny Pokémon", 4 Rundentypen (species,
  color-shift, cry, stat-compare). Nutzt vorab heruntergeladene/gecachte Assets
  (als GitHub-Release `assets.tar.gz` gebündelt). Siehe
  [`formats/shiny-quiz/SETUP.md`](formats/shiny-quiz/SETUP.md).
- **`formats/classic-quiz/`** - "Who's That Pokémon?", ein Rundentyp (Silhouette,
  Typ-Chart, Cry, Fähigkeit, Pokédex-Eintrag, Reveal). Lädt alle Daten live von der
  PokeAPI, kein Asset-Cache nötig. Lädt zusätzlich zu YouTube optional auch zu TikTok
  hoch. Siehe [`formats/classic-quiz/README.md`](formats/classic-quiz/README.md).

Jedes Format hat sein eigenes `requirements.txt` und eigene virtuelle Umgebung -
die MoviePy/Pillow-Versionen der beiden Formate sind nicht kompatibel
(`shiny-quiz` pinnt `moviepy==1.0.3` / `pillow<10`, `classic-quiz` nutzt
`moviepy>=2.0` / `Pillow>=10.0`), daher wurden die Python-Umgebungen bewusst
getrennt gehalten statt zusammengeführt.

## GitHub Actions

Alle drei täglichen Workflows liegen unter `.github/workflows/`:

| Workflow | Format | Cron (UTC) |
|---|---|---|
| `shiny-species-cry.yml` | shiny-quiz (Species/Color/Cry-Mix) | `0 12 * * *` |
| `shiny-stat-compare.yml` | shiny-quiz (Stat-Vergleich) | `0 20 * * *` |
| `classic-quiz.yml` | classic-quiz | `0 23 * * *` |

**Wichtig vor dem ersten Lauf im gemergten Repo:** Die `classic-quiz.yml`-Secrets
wurden von `YT_*` auf `CLASSIC_YT_*` umbenannt, um Kollisionen mit den
`YT_*`-Secrets von shiny-quiz zu vermeiden (beide Formate nutzten vorher identische
Secret-Namen in getrennten Repos). Falls beide Formate tatsächlich denselben
YouTube-Kanal bespielen sollen, können die `CLASSIC_YT_*`-Referenzen in
`.github/workflows/classic-quiz.yml` einfach wieder auf `YT_*` zurückbenannt werden.
Andernfalls müssen die `CLASSIC_YT_*`-Secrets (Client-ID/Secret/Refresh-Token,
optional Playlist-ID) neu unter Repo → Settings → Secrets and variables → Actions
angelegt werden.

## Historie

Beide Formate stammen aus getrennten Repos (`pokemon-shiny-quiz` und
`pokemon-quiz-video`), deren volle Commit-Historie beim Merge erhalten blieb
(`git log --follow` funktioniert weiterhin auf Dateien in beiden `formats/`-Ordnern).
