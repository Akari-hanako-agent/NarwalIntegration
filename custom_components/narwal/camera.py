"""Map camera entity for Narwal vacuum."""

from __future__ import annotations

import logging
import time

from aiohttp import web

from homeassistant.components.camera import Camera, CameraEntityFeature, async_get_still_stream
from homeassistant.core import HomeAssistant, callback
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
    entity = NarwalMapCamera(coordinator)
    async_add_entities([entity])


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

    @property
    def supported_features(self) -> CameraEntityFeature:
        """Return supported features (none — no streaming or recording)."""
        return CameraEntityFeature(0)

    @property
    def extra_state_attributes(self) -> dict[str, int] | None:
        """Expose render count so state changes trigger frontend refresh."""
        if self._render_count > 0:
            return {"render_count": self._render_count}
        return None

    def __init__(self, coordinator: NarwalCoordinator) -> None:
        """Initialize the map camera entity."""
        super().__init__(coordinator)
        Camera.__init__(self)
        device_id = coordinator.config_entry.data["device_id"]
        self._attr_unique_id = f"{device_id}_map"
        self._cached_image: bytes | None = None
        self._cache_key: tuple = ()
        self._last_render_time: float = 0.0
        self._render_count: int = 0

    def camera_image(
        self, width: int | None = None, height: int | None = None,
    ) -> bytes | None:
        """Return the current map as a PNG image."""
        return self._cached_image

    async def handle_async_mjpeg_stream(
        self, request: web.Request,
    ) -> web.StreamResponse | None:
        """Serve an MJPEG stream by polling cached map frames.

        Without this override the base Camera returns None, and the frontend
        falls back to a single static snapshot that never refreshes.
        """
        return await async_get_still_stream(
            request, self.async_camera_image,
            self._attr_content_type, self._attr_frame_interval,
        )

    @callback
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

        # Build cache key from static map + robot position (not just timestamp,
        # which may be 0 or constant across broadcasts).
        static_ts = static_map.created_at or 0
        if display:
            new_key = (static_ts, display.robot_x, display.robot_y, display.robot_heading)
        else:
            new_key = (static_ts,)

        now = time.monotonic()
        since_render = now - self._last_render_time if self._last_render_time else 999

        # Skip re-render if nothing changed
        if new_key == self._cache_key and self._cached_image:
            self.async_write_ha_state()
            return

        # Throttle renders during cleaning
        if (
            display is not None
            and self._cached_image
            and since_render < _MIN_RENDER_INTERVAL
        ):
            self.async_write_ha_state()
            return

        _LOGGER.debug(
            "map render #%d: display=%s pos=(%.1f,%.1f) since=%.1fs",
            self._render_count + 1,
            display is not None,
            display.robot_x if display else 0,
            display.robot_y if display else 0,
            since_render,
        )

        # Schedule async render (we're in a sync callback)
        self.hass.async_create_task(self._async_render(static_map, display, new_key))

    async def _async_render(self, static_map, display, new_key) -> None:
        """Render the map image in an executor thread."""
        # Robot position from display_map (convert to grid pixels)
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
                if self._render_count < 3:
                    _LOGGER.debug(
                        "transform: raw=(%.2f,%.2f) res=%d origin=(%d,%d) "
                        "→ pixel=(%.1f,%.1f) map=%dx%d",
                        display.robot_x, display.robot_y,
                        static_map.resolution,
                        static_map.origin_x, static_map.origin_y,
                        robot_x, robot_y,
                        static_map.width, static_map.height,
                    )

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
                self._render_count += 1
                _LOGGER.debug(
                    "map rendered #%d: %d bytes, robot=(%s,%s)",
                    self._render_count,
                    len(png_bytes),
                    robot_x,
                    robot_y,
                )

        except Exception:
            _LOGGER.exception("Failed to render map image")

        self.async_write_ha_state()
