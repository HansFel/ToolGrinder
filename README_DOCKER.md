# Grinder Webapp in Docker

Lokale Webapp fuer den Grinder G-Code Generator.

## Start

```powershell
cd C:\Users\HTFel\OneDrive\CNCProgramms\Grinder
wsl -e sh -lc "cd /mnt/c/Users/HTFel/OneDrive/CNCProgramms/Grinder && docker compose up -d --build"
```

Danach im Browser:

```text
http://localhost:18088
```

## Stop

```powershell
wsl -e sh -lc "cd /mnt/c/Users/HTFel/OneDrive/CNCProgramms/Grinder && docker compose down"
```

## Test

```powershell
curl.exe http://localhost:18088/health
```

Die erzeugten G-Code-Dateien liegen im Docker-Volume `grinder_grinder_data` und sind ueber die Download-Links in der Webapp abrufbar.

Im selben Volume liegt die SQLite-Datenbank. Dadurch bleiben Vorlagen,
Werkzeugbestand, Strategien und Auftragshistorie bei einem Container-Neustart
erhalten.
