"""DataUpdateCoordinator for Narwal vacuum."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .narwal_client import NarwalClient, NarwalConnectionError, NarwalState
from .narwal_client.const import WorkingStatus

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

POLL_INTERVAL = timedelta(seconds=60)

# Fast re-poll when state is incomplete (robot asleep at startup)
FAST_POLL_INTERVAL = timedelta(seconds=10)
FAST_POLL_MAX = 6  # up to 60s of fast polling before falling back to normal


class NarwalCoordinator(DataUpdateCoordinator[NarwalState]):
    """Push-mode coordinator for Narwal vacuum.

    Primary data source is WebSocket broadcasts (every ~1.5s when awake).
    Fallback polling every 60s via get_status() in case broadcasts stop.

    The robot's command responses and broadcasts both include dock indicator
    fields (11, 47, 3.10, 3.12) — even during deep sleep. The state model
    parses these correctly; no inference or heuristics needed.
    """

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=POLL_INTERVAL,
        )
        self.client = NarwalClient(
            host=entry.data["host"],
            port=entry.data["port"],
            device_id=entry.data.get("device_id", ""),
        )
        self._listen_task: asyncio.Task[None] | None = None
        self._fast_poll_remaining = 0
        self._prev_working_status = WorkingStatus.UNKNOWN
        self._map_fetch_pending = False

    async def async_setup(self) -> None:
        """Connect to the vacuum and start the WebSocket listener.

        Keeps setup fast (<15s) so HA doesn't time out. If the robot is
        asleep, entities are created with defaults and a fast re-poll
        (every 10s) populates them once the robot wakes.
        """
        await self.client.connect()

        # Set up push callback before starting listener
        self.client.on_state_update = self._on_state_update

        # Start persistent WebSocket listener as a background task.
        self._listen_task = self.config_entry.async_create_background_task(
            self.hass,
            self.client.start_listening(),
            f"{DOMAIN}_ws_listener",
        )

        # Quick wake attempt (5s, not 20s — keep setup fast)
        await self.client.wake(timeout=5.0)

        # Always send topic subscription — wake() skips the burst if
        # the robot is already awake, which means display_map won't flow.
        try:
            await self.client.subscribe_to_topics()
        except Exception:
            _LOGGER.debug("Could not send initial topic subscription")

        # Single attempt at fetching initial state
        try:
            await self.client.get_device_info()
        except Exception:
            _LOGGER.debug("Could not fetch device info")

        try:
            await self.client.get_status(full_update=True)
        except Exception:
            _LOGGER.debug("Could not fetch initial status")

        try:
            await self.client.get_map()
        except Exception:
            _LOGGER.debug("Could not fetch initial map")

        # Brief wait for broadcasts if status is still unknown
        if self.client.state.working_status == WorkingStatus.UNKNOWN:
            for _ in range(6):  # up to 3 seconds
                await asyncio.sleep(0.5)
                if self.client.state.working_status != WorkingStatus.UNKNOWN:
                    break

        state = self.client.state

        _LOGGER.info(
            "Narwal startup: status=%s, battery=%d, docked=%s, "
            "f11=%d, f47=%d, dock_sub=%d, dock_act=%d, awake=%s",
            state.working_status.name, state.battery_level, state.is_docked,
            state.dock_field11, state.dock_field47,
            state.dock_sub_state, state.dock_activity,
            self.client.robot_awake,
        )

        self.async_set_updated_data(state)

        # If robot didn't respond, use fast polling to catch it when it wakes
        if state.working_status == WorkingStatus.UNKNOWN:
            self._fast_poll_remaining = FAST_POLL_MAX
            self.update_interval = FAST_POLL_INTERVAL
            _LOGGER.info(
                "Robot asleep — fast polling every %ds until it responds",
                int(FAST_POLL_INTERVAL.total_seconds()),
            )

    def _on_state_update(self, state: NarwalState) -> None:
        """Handle a push state update from the WebSocket listener."""
        _LOGGER.debug(
            "Broadcast update: status=%s, docked=%s, f11=%d, f47=%d, "
            "dock_sub=%d, dock_act=%d",
            state.working_status.name, state.is_docked,
            state.dock_field11, state.dock_field47,
            state.dock_sub_state, state.dock_activity,
        )

        # Fetch static map if missing — get_map() failed at startup (robot asleep)
        if state.map_data is None and not self._map_fetch_pending:
            self._map_fetch_pending = True
            self.config_entry.async_create_background_task(
                self.hass,
                self._fetch_missing_map(),
                f"{DOMAIN}_map_fetch",
            )

        # Detect return-to-dock transition: CLEANING/CLEANING_ALT → STANDBY.
        # Broadcast dock fields (f11, f47) are stale after docking — they only
        # refresh via get_status() poll. Schedule an immediate poll so the UI
        # shows DOCKED instead of IDLE within seconds instead of up to 60s.
        if (
            state.working_status == WorkingStatus.STANDBY
            and self._prev_working_status
            in (WorkingStatus.CLEANING, WorkingStatus.CLEANING_ALT)
        ):
            _LOGGER.info(
                "Return-to-dock transition detected (CLEANING→STANDBY), "
                "scheduling immediate dock status refresh"
            )
            self.hass.async_create_task(self._refresh_dock_status())
        self._prev_working_status = state.working_status

        self.async_set_updated_data(state)

        # Broadcast arrived — switch back to normal polling if in fast mode
        if self._fast_poll_remaining > 0:
            self._fast_poll_remaining = 0
            self.update_interval = POLL_INTERVAL
            _LOGGER.info(
                "Narwal broadcast received: status=%s — normal polling restored",
                state.working_status.name,
            )

    async def _fetch_missing_map(self) -> None:
        """Fetch static map when it's missing (get_map failed at startup).

        Also re-subscribes to topics since subscription likely also failed
        when the robot was asleep at startup.
        """
        try:
            await self.client.get_map()
            _LOGGER.info("Static map loaded (was missing at startup)")
        except Exception:
            _LOGGER.debug("Map fetch failed — will retry on next broadcast")
            self._map_fetch_pending = False
            return
        # Re-subscribe to topics (display_map won't flow without subscription)
        try:
            await self.client.subscribe_to_topics()
            _LOGGER.info("Topic subscription sent after map load")
        except Exception:
            _LOGGER.debug("Topic subscription failed after map load")
        self.async_set_updated_data(self.client.state)

    async def _refresh_dock_status(self) -> None:
        """Immediate get_status() after return-to-dock to refresh dock fields."""
        try:
            await self.client.get_status(full_update=True)
            self.async_set_updated_data(self.client.state)
            _LOGGER.info(
                "Dock status refreshed: docked=%s, f11=%d, f47=%d",
                self.client.state.is_docked,
                self.client.state.dock_field11,
                self.client.state.dock_field47,
            )
        except Exception:
            _LOGGER.debug("Failed to refresh dock status after transition")

    async def _async_update_data(self) -> NarwalState:
        """Polling fallback — fetch status if no push updates arrived."""
        if not self.client.connected:
            try:
                await self.client.connect()
            except NarwalConnectionError as err:
                raise UpdateFailed(f"Cannot connect to vacuum: {err}") from err

        # Try to wake the robot if not broadcasting
        if not self.client.robot_awake:
            await self.client.wake(timeout=20.0)

        # Query full status — response includes dock fields even in deep sleep
        try:
            await self.client.get_status(full_update=True)
        except Exception as err:
            raise UpdateFailed(f"Failed to get status: {err}") from err

        # Retry map fetch if it failed during setup (robot was asleep)
        if self.client.state.map_data is None:
            try:
                await self.client.get_map()
                _LOGGER.info("Map data loaded on poll retry")
            except Exception:
                _LOGGER.debug("Map fetch retry failed — will try again next poll")

        state = self.client.state

        _LOGGER.debug(
            "Poll update: status=%s, docked=%s, battery=%d, "
            "f11=%d, f47=%d, awake=%s",
            state.working_status.name, state.is_docked,
            state.battery_level,
            state.dock_field11, state.dock_field47,
            self.client.robot_awake,
        )

        # Manage fast poll countdown
        if self._fast_poll_remaining > 0:
            if self.client.state.working_status != WorkingStatus.UNKNOWN:
                self._fast_poll_remaining = 0
                self.update_interval = POLL_INTERVAL
                _LOGGER.info(
                    "Narwal poll got status=%s — normal polling restored",
                    self.client.state.working_status.name,
                )
            else:
                self._fast_poll_remaining -= 1
                if self._fast_poll_remaining <= 0:
                    self.update_interval = POLL_INTERVAL
                    _LOGGER.info("Fast poll exhausted — normal polling restored")

        return self.client.state

    async def async_shutdown(self) -> None:
        """Disconnect from the vacuum."""
        await self.client.disconnect()
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
        await super().async_shutdown()
