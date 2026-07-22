# Setup: automatischer Upload zu YouTube

Es gibt zwei getrennte, täglich laufende Pipelines/Videos:

- [../../.github/workflows/shiny-species-cry.yml](../../.github/workflows/shiny-species-cry.yml)
  (`cron: 0 12 * * *`, UTC) - das Shiny-Quiz-Video (Species-Guess,
  Color-Shift, Cry-Guess gemischt).
- [../../.github/workflows/shiny-stat-compare.yml](../../.github/workflows/shiny-stat-compare.yml)
  (`cron: 0 20 * * *`, UTC) - das eigenständige Stat-Vergleich-Video
  (`quiz_video.py --round-type stat_compare`).

Beide nutzen dieselben YouTube-Secrets (siehe unten), nur der optionale
Playlist-Secret ist getrennt (`YT_PLAYLIST_ID` vs. `YT_STAT_PLAYLIST_ID`).

Damit das funktioniert, muss einmalig ein Zugang bei Google eingerichtet und
als GitHub Secret hinterlegt werden (Repo → Settings → Secrets and
variables → Actions → New repository secret).

## YouTube

1. Google Cloud Console → neues Projekt → "YouTube Data API v3" aktivieren.
2. OAuth-Zustimmungsbildschirm konfigurieren (Publishing status "Testing"
   reicht aus) und dich selbst unter "Test users" mit deiner Google-Mail-
   Adresse eintragen.
3. Anmeldedaten → OAuth-Client-ID → Typ "Desktop-App" → `client_secret.json`
   herunterladen, neben `get_youtube_refresh_token.py` legen.
4. Lokal ausführen: `python get_youtube_refresh_token.py`, im Browser mit dem
   Ziel-YouTube-Account einloggen und Zugriff erlauben.
5. Die drei ausgegebenen Werte als Secrets speichern:
   - `YT_CLIENT_ID`
   - `YT_CLIENT_SECRET`
   - `YT_REFRESH_TOKEN`

## Playlist (optional)

Damit jedes hochgeladene Video automatisch einer Playlist hinzugefügt wird:

1. Playlist-ID aus der YouTube-URL kopieren (`https://www.youtube.com/playlist?list=`**`PLxxxxxxxx`**).
2. Als Secret `YT_PLAYLIST_ID` speichern.

Falls dein `YT_REFRESH_TOKEN` bereits **vor** diesem Feature erzeugt wurde,
reicht das Secret allein nicht: `get_youtube_refresh_token.py` fordert jetzt
zusätzlich den Scope `youtube.force-ssl` an (nötig, um Videos zu Playlists
hinzuzufügen). In dem Fall `get_youtube_refresh_token.py` erneut ausführen
und `YT_REFRESH_TOKEN` mit dem neuen Wert überschreiben.

## Assets (Pokémon-Sprites, Fonts, Audio, Hintergründe)

Die Assets liegen **nicht im Repo** (bewusst weiterhin `.gitignore`d), sondern
werden lokal unter `assets/` gehalten und als `assets.tar.gz` an ein
GitHub Release gehängt. Der Workflow lädt dieses Release-Asset bei jedem Lauf
herunter und entpackt es (siehe "Download assets from latest release"-Step) -
daran ändert sich durch die interne Neusortierung nichts.

Struktur seit der Umstrukturierung:

```
assets/
  pokemon/<name>/normal.gif, shiny.gif   (bisher: assets/<name>/...)
  fonts/pokemon/PokemonSolid.ttf          (bisher: fonts/pokemon/...)
  audio/music/*.mp3                       (bisher: music/video_background_music/...)
  audio/sfx/pokeball.mp3                  (bisher: music/sound_effects/...)
  backgrounds/images/*                    (bisher: background_images/backgrounds/...)
  backgrounds/animations/pokeball_animation.gif
```

**Wichtig:** Das aktuelle Release-Asset `assets.tar.gz` wurde mit der alten
Struktur gepackt und passt nicht mehr zum Code. Vor dem nächsten Workflow-Lauf
neu packen und das Release-Asset ersetzen:

```
tar czf assets.tar.gz assets
gh release upload <tag> assets.tar.gz --clobber
```

## Stat-Vergleich-Runde (stat_compare)

Einer der vier Rundentypen in `quiz_video.py` vergleicht Basiswerte
(HP/Attack/Defense/Sp. Attack/Sp. Defense/Speed/Height/Weight) zweier
Pokémon. Die Werte kommen aus `data/pokemon_stats.json`, die einmalig lokal
erzeugt und ins Repo committet wird (kein Live-API-Call während der
Videoerstellung, kein Extra-Schritt im Workflow nötig):

```
python fetch_pokemon_stats.py
```

Danach `data/pokemon_stats.json` committen. Ohne diese Datei überspringt
`quiz_video.py` den `stat_compare`-Rundentyp automatisch. Das Skript nach
jeder Änderung an `assets/pokemon/` erneut laufen lassen (fügt neue/aktualisiert
bestehende Einträge hinzu, ohne alles neu abzufragen wäre aufwendiger -
aktuell wird komplett neu geschrieben).

## TikTok (Sandbox, privat)

Beide Workflows laden zusätzlich zu YouTube auch zu TikTok hoch
(`upload_tiktok.py`), mit `continue-on-error: true` - schlägt TikTok fehl,
läuft der YouTube-Upload trotzdem durch.

Nutzt dieselben `TT_CLIENT_KEY` / `TT_CLIENT_SECRET` / `TT_REFRESH_TOKEN`
Secrets wie `formats/classic-quiz/` (gleicher TikTok-Account). Falls diese
noch nicht existieren, siehe
[`formats/classic-quiz/get_tiktok_refresh_token.py`](../classic-quiz/get_tiktok_refresh_token.py)
für die einmalige Einrichtung.

**Wichtig:** Solange die TikTok-App nicht von TikTok für "Direct Post"
freigegeben ist (Sandbox/unaudited), postet `upload_tiktok.py` nur mit
`privacy_level: SELF_ONLY` - das Video ist nur für dich selbst sichtbar,
bis du es in der App manuell auf öffentlich stellst. Ein Antrag auf
Produktionsfreigabe für rein privaten/internen Gebrauch wird von TikTok
abgelehnt (siehe TikTok-Antwort dazu) - SELF_ONLY ist aktuell der einzig
gangbare automatisierte Weg.

## Testen

Workflow manuell über "Run workflow" (workflow_dispatch) starten und die
Logs der Schritte "Upload to YouTube Shorts" und "Upload to TikTok" prüfen,
bevor der Cron-Zeitplan scharf geschaltet wird.
