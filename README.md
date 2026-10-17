# Spotify: alle Folgen

Überlagerung für die eingebaute Spotify-Integration von Home Assistant:

- Der Medien-Browser zeigt **alle Alben eines Interpreten** statt nur der ersten 48 –
  wichtig für Hörspielreihen wie Benjamin Blümchen, Die drei ??? oder TKKG.
- Hörspielreihen werden **nach Folgennummer sortiert, neueste oben**
  (`Folge 172: …`, `054/…`, `02: …`, `Folgen 48-52: …`), danach Unterreihen
  (`Benjamin Minis - Folge 2: …`), danach Specials in Spotify-Reihenfolge.
  Alben, auf denen der Interpret nur mitwirkt, zählen nicht als Folge und stehen hinten.
  Interpreten ohne nummerierte Folgen (normale Musik) bleiben in Spotify-Reihenfolge.

Die eingebaute Spotify-Integration bleibt unverändert und bekommt weiter alle Updates.
Diese Integration ersetzt zur Laufzeit nur `SpotifyClient.get_artist_albums` aus der
Bibliothek `spotifyaio` – die wird in Home Assistant ausschließlich vom Spotify-Medien-Browser
benutzt. Entfernt man den Eintrag, gilt sofort wieder das Original.

## Installation

HACS → Benutzerdefinierte Repositories → dieses Repo als *Integration* hinzufügen →
installieren → Home Assistant neu starten → *Einstellungen → Geräte & Dienste →
Integration hinzufügen → „Spotify: alle Folgen“*.

## Tests

```
uv run -q --no-project --python 3.14 --with spotifyaio==2.0.2 python tests/test_overlay.py
```
