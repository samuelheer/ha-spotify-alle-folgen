"""Tests for the overlay without a Home Assistant install (HA modules are stubbed).

Run: uv run -q --no-project --python 3.14 --with spotifyaio==2.0.2 python tests/test_overlay.py [titles.json …]
"""

import asyncio
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

for name in ("homeassistant", "homeassistant.config_entries", "homeassistant.core"):
    sys.modules[name] = ModuleType(name)
sys.modules["homeassistant.config_entries"].ConfigEntry = object
sys.modules["homeassistant.core"].HomeAssistant = object
sys.path.insert(0, str(Path(__file__).parents[1] / "custom_components"))

from spotifyaio import SpotifyClient  # noqa: E402

import spotify_alle_folgen as overlay  # noqa: E402

TOTAL = 130


def album(i: int) -> dict:
    return {"album_type": "album", "total_tracks": 1, "available_markets": [],
            "external_urls": {"spotify": "x"}, "href": "x", "id": f"id{i}", "images": [],
            "name": f"Folge {i}: Titel", "release_date": "2020-01-01",
            "release_date_precision": "day", "type": "album", "uri": f"spotify:album:id{i}",
            "artists": [{"external_urls": {"spotify": "x"}, "href": "x", "id": "abc",
                         "name": "B", "type": "artist", "uri": "spotify:artist:a"}]}


class FakeClient(SpotifyClient):
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def _get(self, uri, params=None):
        self.calls.append(dict(params))
        off, lim = params["offset"], params["limit"]
        items = [album(i) for i in range(off, min(off + lim, TOTAL))]
        return json.dumps({"items": items, "next": "more" if off + lim < TOTAL else None})


# Patch is applied and removed again
original = SpotifyClient.get_artist_albums
asyncio.run(overlay.async_setup_entry(None, None))
assert SpotifyClient.get_artist_albums is overlay.get_all_artist_albums
client = FakeClient()
res = asyncio.run(client.get_artist_albums("spotify:artist:abc"))
assert len(res) == TOTAL and len(client.calls) == 3, (len(res), client.calls)
assert res[0].name == "Folge 129: Titel" and res[-1].name == "Folge 0: Titel"
asyncio.run(overlay.async_unload_entry(None, None))
assert SpotifyClient.get_artist_albums is original
print("Paging + Patch/Unpatch OK")

fake = [SimpleNamespace(name=n) for n in ["Special", "Folge 10: Zehn", "Benjamin Minis - Folge 2: B",
                                          "002/Zwei", "Folge: 1: Eins", "Benjamin Minis - Folge 1: A",
                                          "Folgen 3-5: Box"]]
got = [a.name for a in overlay.sort_by_episode(fake)]
assert got == ["Folge 10: Zehn", "Folgen 3-5: Box", "002/Zwei", "Folge: 1: Eins",
               "Benjamin Minis - Folge 2: B", "Benjamin Minis - Folge 1: A", "Special"], got

def alb(name, artist):
    return SimpleNamespace(name=name, artists=[SimpleNamespace(artist_id=artist)])
mixed = [alb("Folge 139: Fremde Reihe", "other"), alb("Folge 2: Zwei", "me"), alb("Single", "me"),
         alb("Folge 29: Neunundzwanzig", "me")]
got = [a.name for a in overlay.sort_by_episode(mixed, "me")]
assert got == ["Folge 29: Neunundzwanzig", "Folge 2: Zwei", "Folge 139: Fremde Reihe", "Single"], got
print("Sortierung OK")

for path in sys.argv[1:]:
    out = [a.name for a in overlay.sort_by_episode([SimpleNamespace(name=t) for t in json.load(open(path))])]
    print(Path(path).stem, "|", " | ".join(out[:3]), "…", out[-1])
