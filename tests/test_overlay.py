"""Tests for the overlay without a Home Assistant install (HA modules are stubbed).

Run: uv run -q --no-project --python 3.14 --with spotifyaio==2.0.2 --with pytest pytest tests
Try real catalogs: … python tests/test_overlay.py titles.json [titles.json …]
"""

from __future__ import annotations

import asyncio
import importlib
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest
from spotifyaio import SpotifyClient, SpotifyError

TOTAL = 130


def _stub_homeassistant(setitem=sys.modules.__setitem__) -> None:
    for name in (
        "homeassistant",
        "homeassistant.config_entries",
        "homeassistant.core",
        "homeassistant.exceptions",
    ):
        setitem(name, ModuleType(name))
    sys.modules["homeassistant.config_entries"].ConfigEntry = object
    sys.modules["homeassistant.core"].HomeAssistant = object
    sys.modules["homeassistant.exceptions"].ConfigEntryError = type(
        "ConfigEntryError", (Exception,), {}
    )
    sys.path.insert(0, str(Path(__file__).parents[1] / "custom_components"))


@pytest.fixture
def integration(monkeypatch):
    _stub_homeassistant(lambda name, mod: monkeypatch.setitem(sys.modules, name, mod))
    return importlib.import_module("spotify_alle_folgen")


@pytest.fixture
def overlay(integration):
    return importlib.import_module("spotify_alle_folgen.overlay")


def album(i: int) -> dict:
    return {"album_type": "album", "total_tracks": 1, "available_markets": [],
            "external_urls": {"spotify": "x"}, "href": "x", "id": f"id{i}", "images": [],
            "name": f"Folge {i}: Titel", "release_date": "2020-01-01",
            "release_date_precision": "day", "type": "album", "uri": f"spotify:album:id{i}",
            "artists": [{"external_urls": {"spotify": "x"}, "href": "x", "id": "abc",
                         "name": "B", "type": "artist", "uri": "spotify:artist:a"}]}


def alb(name: str, artist: str = "me", artist_name: str = "Me") -> SimpleNamespace:
    return SimpleNamespace(
        name=name, artists=[SimpleNamespace(artist_id=artist, name=artist_name)]
    )


class FakeClient(SpotifyClient):
    def __init__(self, body=None) -> None:
        self.calls: list[dict] = []
        self.body = body

    async def _get(self, uri, params=None):
        self.calls.append(dict(params))
        if self.body is not None:
            return self.body
        off, lim = params["offset"], params["limit"]
        items = [album(i) for i in range(off, min(off + lim, TOTAL))]
        return json.dumps({"items": items, "total": TOTAL})


def test_patch_paging_unpatch(integration, overlay):
    original = SpotifyClient.get_artist_albums
    asyncio.run(integration.async_setup_entry(None, None))
    assert SpotifyClient.get_artist_albums is overlay.get_all_artist_albums
    client = FakeClient()
    res = asyncio.run(client.get_artist_albums("spotify:artist:abc"))
    assert len(res) == TOTAL
    assert sorted(c["offset"] for c in client.calls) == [0, 48, 96]
    assert res[0].name == "Folge 129: Titel" and res[-1].name == "Folge 0: Titel"
    asyncio.run(integration.async_unload_entry(None, None))
    assert SpotifyClient.get_artist_albums is original


def test_setup_fails_visibly_when_library_changed(integration, overlay, monkeypatch):
    monkeypatch.delattr(SpotifyClient, "_get")
    with pytest.raises(integration.ConfigEntryError):
        asyncio.run(integration.async_setup_entry(None, None))


def test_broken_json_raises_spotify_error(overlay):
    with pytest.raises(SpotifyError):
        asyncio.run(overlay.get_all_artist_albums(FakeClient("<html>502</html>"), "abc"))


def test_sort_main_then_subseries_then_rest(overlay):
    fake = [alb(n) for n in ["Special", "Folge 10: Zehn", "Benjamin Minis - Folge 2: B",
                             "002/Zwei", "Folge: 1: Eins", "Benjamin Minis - Folge 1: A",
                             "Folgen 3-5: Box"]]
    got = [a.name for a in overlay.sort_by_episode(fake)]
    assert got == ["Folge 10: Zehn", "Folgen 3-5: Box", "002/Zwei", "Folge: 1: Eins",
                   "Benjamin Minis - Folge 2: B", "Benjamin Minis - Folge 1: A", "Special"]


def test_appears_on_stays_in_rest(overlay):
    mixed = [alb("Folge 139: Fremde Reihe", "other"), alb("Folge 2: Zwei"), alb("Single"),
             alb("Folge 29: Neunundzwanzig")]
    got = [a.name for a in overlay.sort_by_episode(mixed, "me")]
    assert got == ["Folge 29: Neunundzwanzig", "Folge 2: Zwei", "Folge 139: Fremde Reihe", "Single"]


def test_series_named_after_artist_is_main_series(overlay):
    titles = ["Bibi & Tina - Folge 87: Tanz", "Folge 12: Alt", "Bibi & Tina - Folge 88: Reiten"]
    got = [a.name for a in overlay.sort_by_episode([alb(t, artist_name="Bibi & Tina") for t in titles])]
    assert got == ["Bibi & Tina - Folge 88: Reiten", "Bibi & Tina - Folge 87: Tanz", "Folge 12: Alt"]


def test_subseries_only_catalog_is_sorted(overlay):
    titles = ["Minis - Folge 1: A", "Minis - Folge 3: C", "Minis - Folge 2: B"]
    got = [a.name for a in overlay.sort_by_episode([alb(t) for t in titles])]
    assert got == ["Minis - Folge 3: C", "Minis - Folge 2: B", "Minis - Folge 1: A"]


def test_music_titles_with_times_are_not_episodes(overlay):
    titles = ["4:44", "2:00 AM Sessions", "24/7 (Deluxe)", "12/24: Live"]
    albums = [alb(t) for t in titles]
    assert overlay.sort_by_episode(albums) is albums


if __name__ == "__main__":
    _stub_homeassistant()
    ov = importlib.import_module("spotify_alle_folgen.overlay")
    for path in sys.argv[1:]:
        titles = json.loads(Path(path).read_text())
        out = [a.name for a in ov.sort_by_episode([alb(t) for t in titles])]
        print(Path(path).stem, "|", " | ".join(out[:3]), "…", out[-1])
