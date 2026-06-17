"""Select entity for Narwal vacuum clean mode."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NarwalConfigEntry
from .const import CLEAN_MODE_LIST, CLEAN_MODE_MAP
from .coordinator import NarwalCoordinator
from .entity import NarwalEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NarwalConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the clean mode select entity."""
    coordinator = entry.runtime_data
    async_add_entities([NarwalCleanModeSelect(coordinator)])


class NarwalCleanModeSelect(NarwalEntity, SelectEntity):
    """Select entity for choosing the cleaning mode."""

    _attr_translation_key = "clean_mode"
    _attr_options = CLEAN_MODE_LIST
    _attr_current_option = "sweep_mop"

    def __init__(self, coordinator: NarwalCoordinator) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        device_id = coordinator.config_entry.data["device_id"]
        self._attr_unique_id = f"{device_id}_clean_mode"

    @property
    def current_option(self) -> str | None:
        """Return the current clean mode."""
        return self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        """Set the clean mode."""
        if option not in CLEAN_MODE_MAP:
            _LOGGER.warning("Unknown clean mode: %s", option)
            return
        value = CLEAN_MODE_MAP[option]
        self._attr_current_option = option
        self.coordinator.clean_mode = value
        self.async_write_ha_state()
        _LOGGER.info("Clean mode set to: %s (value=%d)", option, value)
