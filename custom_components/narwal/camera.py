"""Map camera entity for Narwal vacuum."""

from __future__ import annotations

import logging
import time

from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NarwalConfigEntry
from .coordinator import NarwalCoordinator
from .entity import NarwalEntity

_LOGGER = logging.getLogger(__name__)

# Seconds between MJPEG frames served to the frontend.
_FRAME_INTERVAL = 2.0

# Minimum seconds between re-renders (display_map arrives every ~1.5s
# but PIL rendering is CPU-bound — no need to render every broadcast).
_MIN_RENDER_INTERVAL = 2


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NarwalConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Narwal map camera entity."""
    coordinator = entry.runtime_data
    try:
        entity = NarwalMapCamera(coordinator)
        _LOGGER.warning("Camera entity created: unique_id=%s", entity._attr_unique_id)
        async_add_entities([entity])
        _LOGGER.warning("Camera entity added successfully")
    except Exception:
        _LOGGER.exception("Failed to set up Narwal camera entity")


class NarwalMapCamera(NarwalEntity, Camera):
    """Camera entity that displays the vacuum's map as a PNG via MJPEG stream.

    Uses CameraEntity so the frontend can open a persistent MJPEG connection
    with camera_view: live, getting new frames every _FRAME_INTERVAL seconds.
    The image is rendered server-side with PIL from the static map grid +
    real-time robot position overlay from display_map broadcasts.
    """

    _attr_frame_interval = _FRAME_INTERVAL
    _attr_content_type = "image/png"
    _attr_name = "Map"
    _attr_is_streaming = False
    _attr_supported_features = 0

    def __init__(self, coordinator: NarwalCoordinator) -> None:
        """Initialize the map camera entity."""
        super().__init__(coordinator)
        Camera.__init__(self)
        device_id = coordinator.config_entry.data["device_id"]
        self._attr_unique_id = f"{device_id}_map"
        self._cached_image: bytes | None = None
        self._cache_key: tuple[int, int] = (0, 0)
        self._last_render_time: float = 0.0

    def camera_image(
        self, width: int | None = None, height: int | None = None,
    ) -> bytes | None:
        """Return the current map as a PNG image.

        Called by HA's MJPEG stream handler at frame_interval cadence.
        Returns cached bytes — rendering happens in _handle_coordinator_update.
        """
        return self._cached_image

    def _handle_coordinator_update(self) -> None:
        """Re-render the map when new data arrives from the coordinator."""
        state = self.coordinator.client.state
        static_map = state.map_data
        display = state.map_display_data

        # Must have a static map to render anything
        if not static_map or not static_map.compressed_map:
            self.async_write_ha_state()
            return
        if static_map.width <= 0 or static_map.height <= 0:
            self.async_write_ha_state()
            return

        # Build cache key from both data sources
        static_ts = static_map.created_at or 0
        display_ts = display.timestamp if display else 0
        new_key = (static_ts, display_ts)

        now = time.monotonic()
        since_render = now - self._last_render_time if self._last_render_time else 999

        # Skip re-render if nothing changed
        if new_key == self._cache_key and self._cached_image:
            self.async_write_ha_state()
            return

        # Throttle renders during cleaning
        if (
            display_ts > 0
            and self._cached_image
            and since_render < _MIN_RENDER_INTERVAL
        ):
            self.async_write_ha_state()
            return

        # Schedule async render (we're in a sync callback)
        self.hass.async_create_task(self._async_render(static_map, display, new_key))

    async def _async_render(self, static_map, display, new_key) -> None:
        """Render the map image in an executor thread."""
        # Robot position from display_map (convert dm → grid pixels)
        robot_x = None
        robot_y = None
        robot_heading = None
        if display:
            grid_pos = display.to_grid_coords(
                static_map.resolution, static_map.origin_x, static_map.origin_y,
            )
            if grid_pos is not None:
                robot_x, robot_y = grid_pos
                robot_heading = display.robot_heading

        # Dock position and room names from static map
        dock_x = static_map.dock_x
        dock_y = static_map.dock_y
        room_names: dict[int, str] | None = None
        if static_map.rooms:
            room_names = {
                r.room_id: r.name for r in static_map.rooms if r.name
            }

        try:
            from .narwal_client.map_renderer import render_map_from_compressed

            png_bytes = await self.hass.async_add_executor_job(
                render_map_from_compressed,
                static_map.compressed_map,
                static_map.width,
                static_map.height,
                robot_x,
                robot_y,
                robot_heading,
                dock_x,
                dock_y,
                room_names,
            )

            if png_bytes:
                self._cached_image = png_bytes
                self._cache_key = new_key
                self._last_render_time = time.monotonic()

        except Exception:
            _LOGGER.exception("Failed to render map image")

        self.async_write_ha_state()
