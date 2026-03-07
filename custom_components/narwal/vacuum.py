"""Vacuum entity for Narwal robot vacuum."""

from __future__ import annotations

import logging

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .narwal_client import FanLevel, NarwalCommandError, WorkingStatus

from . import NarwalConfigEntry
from .const import FAN_SPEED_LIST, FAN_SPEED_MAP
from .coordinator import NarwalCoordinator
from .entity import NarwalEntity

_LOGGER = logging.getLogger(__name__)

WORKING_STATUS_TO_ACTIVITY: dict[WorkingStatus, VacuumActivity] = {
    WorkingStatus.DOCKED: VacuumActivity.DOCKED,
    WorkingStatus.CHARGED: VacuumActivity.DOCKED,
    WorkingStatus.STANDBY: VacuumActivity.IDLE,
    WorkingStatus.CLEANING: VacuumActivity.CLEANING,
    WorkingStatus.CLEANING_ALT: VacuumActivity.CLEANING,
    WorkingStatus.ERROR: VacuumActivity.ERROR,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NarwalConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Narwal vacuum entity."""
    coordinator = entry.runtime_data
    async_add_entities([NarwalVacuum(coordinator)])


class NarwalVacuum(NarwalEntity, StateVacuumEntity):
    """Representation of a Narwal robot vacuum."""

    _attr_translation_key = "vacuum"
    _attr_supported_features = (
        VacuumEntityFeature.STATE
        | VacuumEntityFeature.START
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.LOCATE
    )
    _attr_fan_speed_list = FAN_SPEED_LIST

    def __init__(self, coordinator: NarwalCoordinator) -> None:
        """Initialize the vacuum entity."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.config_entry.data["device_id"]
        self._last_fan_speed: str | None = None

    @property
    def activity(self) -> VacuumActivity:
        """Return the current vacuum activity."""
        state = self.coordinator.data
        if state is None:
            return VacuumActivity.IDLE
        is_cleaning_state = state.working_status in (
            WorkingStatus.CLEANING, WorkingStatus.CLEANING_ALT,
        )
        # Returning takes priority over paused — robot can report both
        # flags simultaneously during return-to-dock sequence.
        if state.is_returning:
            return VacuumActivity.RETURNING
        # Robot still broadcasts CLEANING after physically docking —
        # dock fields update before working_status transitions.
        # Check dock signals while in CLEANING state to catch this.
        if is_cleaning_state and (
            state.dock_sub_state == 1
            or state.dock_field11 == 2
            or state.dock_field47 == 3
        ):
            return VacuumActivity.DOCKED
        # is_paused (field 3.2) stays stale after docking — only trust
        # during active cleaning when not docked.
        if state.is_paused and is_cleaning_state:
            return VacuumActivity.PAUSED
        if state.is_cleaning:
            return VacuumActivity.CLEANING
        if state.is_docked:
            return VacuumActivity.DOCKED
        return WORKING_STATUS_TO_ACTIVITY.get(
            state.working_status, VacuumActivity.IDLE
        )

    @property
    def fan_speed(self) -> str | None:
        """Return the current fan speed.

        The robot protocol does not broadcast the active fan speed setting,
        so we track the last value set via the integration. Returns None
        until the user sets a fan speed for the first time.
        """
        return self._last_fan_speed

    # Timeout for action commands (start/stop/return) — robot may need
    # time to load map, plan route, etc., especially after waking.
    _ACTION_TIMEOUT = 10.0

    # If no broadcast in this many seconds, treat robot as shallow-sleeping
    # even if robot_awake is True (one stale broadcast doesn't mean "ready").
    _BROADCAST_STALE_FOR_CMD = 10.0

    async def _ensure_awake(self) -> None:
        """Wake the robot if it is sleeping or broadcasts have gone stale.

        Checks both the robot_awake flag AND broadcast recency.  The robot
        can appear awake (one broadcast received) but drop back to shallow
        sleep within seconds — in that state it won't process commands.

        The wake burst itself includes get_device_base_status which forces
        the robot's main processor into command-ready state, so no separate
        priming step is needed here.
        """
        client = self.coordinator.client
        broadcast_age = client.last_broadcast_age
        stale = broadcast_age > self._BROADCAST_STALE_FOR_CMD
        if not client.robot_awake or stale:
            _LOGGER.debug(
                "Robot not ready (awake=%s, last_broadcast=%.1fs ago) — waking",
                client.robot_awake,
                broadcast_age,
            )
            if not await client.wake(timeout=15.0, force=stale):
                raise NarwalCommandError("Robot did not wake up — cannot send command")

    async def async_start(self) -> None:
        """Start or resume cleaning."""
        await self._ensure_awake()
        state = self.coordinator.data
        # is_paused stays stale after docking — only trust it during cleaning
        is_cleaning = state and state.working_status in (
            WorkingStatus.CLEANING, WorkingStatus.CLEANING_ALT,
        )
        if is_cleaning and state.is_paused:
            await self.coordinator.client.resume(timeout=self._ACTION_TIMEOUT)
        else:
            resp = await self.coordinator.client.start()
            _LOGGER.info(
                "Start command response: code=%s, success=%s",
                resp.result_code, resp.success,
            )
            if not resp.success:
                _LOGGER.warning(
                    "Start command did not succeed (code=%s) — robot may not have started",
                    resp.result_code,
                )

    async def async_stop(self, **kwargs) -> None:
        """Stop cleaning."""
        await self._ensure_awake()
        await self.coordinator.client.stop(timeout=self._ACTION_TIMEOUT)

    async def async_pause(self) -> None:
        """Pause cleaning."""
        await self.coordinator.client.pause()

    async def async_return_to_base(self, **kwargs) -> None:
        """Return to the dock."""
        await self._ensure_awake()
        await self.coordinator.client.return_to_base(timeout=self._ACTION_TIMEOUT)

    async def async_locate(self, **kwargs) -> None:
        """Locate the vacuum — robot says 'Robot is here'."""
        await self._ensure_awake()
        await self.coordinator.client.locate()

    async def async_set_fan_speed(self, fan_speed: str, **kwargs) -> None:
        """Set the fan speed."""
        level = FAN_SPEED_MAP.get(fan_speed)
        if level is not None:
            await self.coordinator.client.set_fan_speed(level)
            self._last_fan_speed = fan_speed
            self.async_write_ha_state()
