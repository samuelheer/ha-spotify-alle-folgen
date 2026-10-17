"""Spotify: alle Folgen.

Overlay for the built-in Spotify integration: the media browser shows all albums of an
artist (spotifyaio only fetches the first 48) and sorts radio play series by episode
number, newest first. The built-in integration stays untouched and keeps receiving
Home Assistant updates; only ``SpotifyClient.get_artist_albums`` is replaced at runtime.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from spotifyaio import SimplifiedAlbum, SpotifyClient
from spotifyaio.models import NewReleasesResponseInner

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

PAGE_LIMIT = 48
MAX_ARTIST_ALBUMS = 1000

# Episode number at the start: "Folge 172: …", "Folge: 45: …", "054/…", "02: …", "Folgen 48-52: …"
_EPISODE_RE = re.compile(r"^(?:Folgen?:?\s*)?(\d{1,4})(?:\s*-\s*\d+)?\s*[:/]")
# Sub-series with its own numbering: "Benjamin Minis - Folge 2: …"
_SUBSERIES_RE = re.compile(r"^(.+?)\s+-\s+Folge\s+(\d{1,4})\b")

_ORIGINAL = SpotifyClient.get_artist_albums


def _natural_key(title: str) -> list[int | str]:
    """Sort key that compares numbers inside a title numerically."""
    return [
        int(part) if part.isdigit() else part.casefold()
        for part in re.split(r"(\d+)", title)
    ]


def sort_by_episode(
    albums: list[SimplifiedAlbum], artist_id: str | None = None
) -> list[SimplifiedAlbum]:
    """Sort radio play series by episode number (descending), keep the rest in Spotify order.

    Order: main series newest first, then sub-series (each newest first), then the rest.
    Only albums whose main artist is ``artist_id`` count as episodes, so albums the artist
    merely appears on stay in the rest. Artists with fewer than two episodes are left untouched.
    """

    def own(album: SimplifiedAlbum) -> bool:
        return artist_id is None or (
            bool(album.artists) and album.artists[0].artist_id == artist_id
        )

    def key(indexed: tuple[int, SimplifiedAlbum]) -> tuple[Any, ...]:
        index, album = indexed
        if not own(album):
            return (2, "", index, [])
        if match := _EPISODE_RE.match(album.name):
            return (0, "", -int(match.group(1)), _natural_key(album.name))
        if match := _SUBSERIES_RE.match(album.name):
            return (
                1,
                match.group(1).casefold(),
                -int(match.group(2)),
                _natural_key(album.name),
            )
        return (2, "", index, [])

    if sum(1 for album in albums if own(album) and _EPISODE_RE.match(album.name)) < 2:
        return albums
    return [album for _, album in sorted(enumerate(albums), key=key)]


async def get_all_artist_albums(
    self: SpotifyClient, artist_id: str
) -> list[SimplifiedAlbum]:
    """Get all albums of an artist by following Spotify's pagination."""
    identifier = artist_id.rsplit(":", maxsplit=1)[-1]
    albums: list[SimplifiedAlbum] = []
    offset = 0
    while offset < MAX_ARTIST_ALBUMS:
        response = await self._get(  # noqa: SLF001
            f"v1/artists/{identifier}/albums",
            params={"limit": PAGE_LIMIT, "offset": offset},
        )
        page = NewReleasesResponseInner.from_json(response).items
        albums.extend(page)
        if not page or json.loads(response).get("next") is None:
            break
        offset += len(page)
    return sort_by_episode(albums, identifier)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Replace get_artist_albums of the Spotify client."""
    if not hasattr(SpotifyClient, "_get"):
        _LOGGER.warning(
            "spotifyaio has changed (no SpotifyClient._get), overlay not applied"
        )
        return True
    SpotifyClient.get_artist_albums = get_all_artist_albums  # type: ignore[method-assign]
    _LOGGER.info("Spotify media browser now shows all albums per artist")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Restore the original method."""
    SpotifyClient.get_artist_albums = _ORIGINAL  # type: ignore[method-assign]
    return True
