# Setup: automatischer Upload zu YouTube

Es gibt zwei getrennte, täglich laufende Pipelines/Videos:

- [.github/workflows/generate-and-upload.yml](.github/workflows/generate-and-upload.yml)
  (`cron: 0 12 * * *`, UTC) - das Shiny-Quiz-Video (Species-Guess,
  Color-Shift, Cry-Guess gemischt).
- [.github/workflows/generate-and-upload-stats.yml](.github/workflows/generate-and-upload-stats.yml)
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
jeder Änderung an `assets/` erneut laufen lassen (fügt neue/aktualisiert
bestehende Einträge hinzu, ohne alles neu abzufragen wäre aufwendiger -
aktuell wird komplett neu geschrieben).

## Testen

Workflow manuell über "Run workflow" (workflow_dispatch) starten und den
Log des Schritts "Upload to YouTube Shorts" prüfen, bevor der Cron-Zeitplan
scharf geschaltet wird.
