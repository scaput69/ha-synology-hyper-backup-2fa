"""The Synology Tasks integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.synology_dsm.const import DOMAIN as SYNOLOGY_DOMAIN
from homeassistant.exceptions import ConfigEntryNotReady

from .api import SynologyHyperBackupApi
from .const import (
    CONF_API,
    CONF_COORDINATOR,
    CONFIG_DSM_ENTRY_ID,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import SynologyTasksCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType


async def async_setup(hass: HomeAssistant, _: ConfigType) -> bool:
    """Set up the Synology Tasks component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Synology Tasks from a config entry."""
    try:
        # Reuse the already-authenticated DSM client. This preserves the device
        # token created by the official integration's OTP/2FA config flow.
        dsm_entry = next(
            e
            for e in hass.config_entries.async_entries(SYNOLOGY_DOMAIN)
            if e.entry_id == entry.data.get(CONFIG_DSM_ENTRY_ID)
        )

        runtime_data = dsm_entry.runtime_data
        if runtime_data is None:
            raise ConfigEntryNotReady("Selected Synology DSM integration is not loaded")

        synology_backup = SynologyHyperBackupApi(runtime_data.api.dsm)

        coordinator = SynologyTasksCoordinator(
            hass, entry, runtime_data.api, synology_backup
        )
        await coordinator.async_config_entry_first_refresh()
    except StopIteration as err:
        raise ConfigEntryNotReady(
            "Selected Synology DSM integration was not found"
        ) from err
    except ConfigEntryNotReady:
        raise
    except Exception as err:
        raise ConfigEntryNotReady from err

    hass.data[DOMAIN][entry.entry_id] = {
        CONF_COORDINATOR: coordinator,
        CONF_API: synology_backup,
    }

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Do not log out: the session is owned and shared by Synology DSM.
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
