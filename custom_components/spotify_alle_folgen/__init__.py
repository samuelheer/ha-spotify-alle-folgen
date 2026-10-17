"""Spotify: alle Folgen.

Overlay for the built-in Spotify integration: the media browser shows all albums of an
artist (spotifyaio only fetches the first 48) and sorts radio play series by episode
number, newest first. The built-in integration stays untouched and keeps receiving
Home Assistant updates; only ``SpotifyClient.get_artist_albums`` is replaced at runtime.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Replace get_artist_albums of the Spotify client.

    spotifyaio is pinned by Home Assistant core, not by this integration. If a core
    update changes the library the entry fails visibly instead of silently doing nothing.
    """
    try:
        from . import overlay  # noqa: PLC0415
    except ImportError as err:
        raise ConfigEntryError(
            f"spotifyaio has changed, overlay not applied: {err}"
        ) from err
    if not hasattr(overlay.SpotifyClient, "_get"):
        raise ConfigEntryError(
            "spotifyaio has changed (no SpotifyClient._get), overlay not applied"
        )
    overlay.apply()
    _LOGGER.info("Spotify media browser now shows all albums per artist")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Restore the original method."""
    try:
        from . import overlay  # noqa: PLC0415
    except ImportError:
        return True
    overlay.restore()
    return True
