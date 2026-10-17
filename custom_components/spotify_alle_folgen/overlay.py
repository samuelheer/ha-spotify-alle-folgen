"""Replacement for ``SpotifyClient.get_artist_albums``: all pages, sorted by episode.

Everything that touches spotifyaio lives here, so ``__init__`` can import this module
lazily and report a changed library as a config entry error instead of failing to load.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from operator import itemgetter
import re
from typing import Any

from mashumaro.mixins.orjson import DataClassORJSONMixin
from spotifyaio import SimplifiedAlbum, SpotifyClient
from spotifyaio.spotify import catch_json_decode_error

PAGE_LIMIT = 48
MAX_ARTIST_ALBUMS = 1000

# Episode number at the start: "Folge 172: …", "Folge: 45: …", "054/…", "02: …", "Folgen 48-52: …"
# The separator must not be followed by a digit, otherwise times and dates in ordinary album
# titles ("4:44", "24/7", "12/24: …") would count as episodes.
_EPISODE_RE = re.compile(r"^(?:Folgen?:?\s*)?(\d{1,4})(?:\s*-\s*\d+)?\s*[:/](?!\d)")
# Series name in front of the number: "Benjamin Minis - Folge 2: …"
_SUBSERIES_RE = re.compile(r"^(.+?)\s+-\s+Folge\s+(\d{1,4})\b")

_MAIN, _SUB, _REST = 0, 1, 2

ORIGINAL = SpotifyClient.get_artist_albums


@dataclass
class _AlbumPage(DataClassORJSONMixin):
    """One page of ``/v1/artists/{id}/albums``."""

    items: list[SimplifiedAlbum]
    total: int


def _natural_key(title: str) -> list[int | str]:
    """Sort key that compares numbers inside a title numerically."""
    return [
        int(part) if part.isdigit() else part.casefold()
        for part in re.split(r"(\d+)", title)
    ]


def _artist_name(album: SimplifiedAlbum) -> str:
    return album.artists[0].name.casefold() if album.artists else ""


def sort_by_episode(
    albums: list[SimplifiedAlbum], artist_id: str | None = None
) -> list[SimplifiedAlbum]:
    """Sort radio play series by episode number (descending), keep the rest in Spotify order.

    Order: main series newest first, then sub-series (each newest first), then the rest.
    A series prefix equal to the artist name ("Bibi & Tina - Folge 87: …") belongs to the
    main series. Only albums whose main artist is ``artist_id`` count as episodes, so albums
    the artist merely appears on stay in the rest. Artists with fewer than two numbered
    episodes are left untouched.
    """

    def key(index: int, album: SimplifiedAlbum) -> tuple[Any, ...]:
        rest = (_REST, "", index, [])
        if artist_id is not None and not (
            album.artists and album.artists[0].artist_id == artist_id
        ):
            return rest
        if match := _EPISODE_RE.match(album.name):
            return (_MAIN, "", -int(match.group(1)), _natural_key(album.name))
        if match := _SUBSERIES_RE.match(album.name):
            series = match.group(1).casefold()
            group = _MAIN if series == _artist_name(album) else _SUB
            return (group, "" if group == _MAIN else series, -int(match.group(2)), _natural_key(album.name))
        return rest

    keys = [key(index, album) for index, album in enumerate(albums)]
    if sum(k[0] != _REST for k in keys) < 2:
        return albums
    return [album for _, album in sorted(zip(keys, albums), key=itemgetter(0))]


@catch_json_decode_error
async def get_all_artist_albums(
    self: SpotifyClient, artist_id: str
) -> list[SimplifiedAlbum]:
    """Get all albums of an artist: first page tells the total, the rest is fetched in parallel."""
    identifier = artist_id.rsplit(":", maxsplit=1)[-1]

    async def page(offset: int) -> _AlbumPage:
        response = await self._get(  # noqa: SLF001
            f"v1/artists/{identifier}/albums",
            params={"limit": PAGE_LIMIT, "offset": offset},
        )
        return _AlbumPage.from_json(response)

    first = await page(0)
    total = min(first.total, MAX_ARTIST_ALBUMS)
    rest = await asyncio.gather(
        *(page(offset) for offset in range(PAGE_LIMIT, total, PAGE_LIMIT))
    )
    albums = [album for current in (first, *rest) for album in current.items]
    return sort_by_episode(albums, identifier)


def apply() -> None:
    """Replace get_artist_albums of every SpotifyClient."""
    SpotifyClient.get_artist_albums = get_all_artist_albums  # type: ignore[method-assign]


def restore() -> None:
    """Put the original method back."""
    SpotifyClient.get_artist_albums = ORIGINAL  # type: ignore[method-assign]
