"""Config flow for Spotify: alle Folgen."""

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class SpotifyAlleFolgenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Single-step flow, there is nothing to configure."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the entry right away."""
        return self.async_create_entry(title="Spotify: alle Folgen", data={})
