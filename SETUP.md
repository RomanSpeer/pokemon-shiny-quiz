# Setup: automatischer Upload zu YouTube

Die Pipeline ([.github/workflows/generate-and-upload.yml](.github/workflows/generate-and-upload.yml))
läuft 3x täglich (`cron: 0 12,16,23 * * *`, UTC), erzeugt ein Video und lädt
es als YouTube Short hoch.

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

## Testen

Workflow manuell über "Run workflow" (workflow_dispatch) starten und den
Log des Schritts "Upload to YouTube Shorts" prüfen, bevor der Cron-Zeitplan
scharf geschaltet wird.
