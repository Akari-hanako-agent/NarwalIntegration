"""Map camera entity for Narwal vacuum."""

from __future__ import annotations

import io
import logging
import time
from collections import deque

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

# Debug view: blank canvas with robot dot + trail.
# Set to False to use the real map renderer instead.
_DEBUG_VIEW = False
_DEBUG_CANVAS_SIZE = 500  # pixels
_DEBUG_TRAIL_LENGTH = 200  # recent positions to keep


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
    """Camera entity that displays the vacuum's map as a PNG via MJPEG stream."""

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
        # Trail of recent raw positions for debug view
        self._trail: deque[tuple[float, float]] = deque(maxlen=_DEBUG_TRAIL_LENGTH)

    def camera_image(
        self, width: int | None = None, height: int | None = None,
    ) -> bytes | None:
        """Return the current map as a PNG image."""
        return self._cached_image

    async def handle_async_mjpeg_stream(
        self, request: web.Request,
    ) -> web.StreamResponse | None:
        """Serve an MJPEG stream by polling cached map frames."""
        return await async_get_still_stream(
            request, self.async_camera_image,
            self._attr_content_type, self._attr_frame_interval,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Re-render the map when new data arrives from the coordinator."""
        state = self.coordinator.client.state
        display = state.map_display_data

        if _DEBUG_VIEW:
            # Debug view only needs display_map data
            if not display or (display.robot_x == 0.0 and display.robot_y == 0.0):
                self.async_write_ha_state()
                return

            new_key = (display.robot_x, display.robot_y, display.robot_heading)
        else:
            static_map = state.map_data
            if not static_map or not static_map.compressed_map:
                self.async_write_ha_state()
                return
            if static_map.width <= 0 or static_map.height <= 0:
                self.async_write_ha_state()
                return
            static_ts = static_map.created_at or 0
            if display:
                new_key = (static_ts, display.robot_x, display.robot_y, display.robot_heading)
            else:
                new_key = (static_ts,)

        now = time.monotonic()
        since_render = now - self._last_render_time if self._last_render_time else 999

        if new_key == self._cache_key and self._cached_image:
            self.async_write_ha_state()
            return

        if self._cached_image and since_render < _MIN_RENDER_INTERVAL:
            self.async_write_ha_state()
            return

        self.hass.async_create_task(self._async_render(display, new_key))

    async def _async_render(self, display, new_key) -> None:
        """Render the map image in an executor thread."""
        if _DEBUG_VIEW and display:
            self._trail.append((display.robot_x, display.robot_y))
            trail = list(self._trail)
            try:
                png_bytes = await self.hass.async_add_executor_job(
                    _render_debug_view,
                    display.robot_x,
                    display.robot_y,
                    display.robot_heading,
                    trail,
                )
                if png_bytes:
                    self._cached_image = png_bytes
                    self._cache_key = new_key
                    self._last_render_time = time.monotonic()
                    self._render_count += 1
                    _LOGGER.debug(
                        "debug rendered #%d: raw=(%.1f,%.1f) trail=%d",
                        self._render_count,
                        display.robot_x, display.robot_y,
                        len(trail),
                    )
            except Exception:
                _LOGGER.exception("Failed to render debug view")
            self.async_write_ha_state()
            return

        # --- Normal map render path ---
        state = self.coordinator.client.state
        static_map = state.map_data
        if not static_map:
            self.async_write_ha_state()
            return

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

        except Exception:
            _LOGGER.exception("Failed to render map image")

        self.async_write_ha_state()


def _render_debug_view(
    robot_x: float,
    robot_y: float,
    robot_heading: float,
    trail: list[tuple[float, float]],
) -> bytes:
    """Render a blank canvas with robot dot + position trail.

    Raw cm coordinates are auto-scaled to fit the canvas with padding.
    Coordinate text is drawn for reference.
    """
    from PIL import Image, ImageDraw, ImageFont

    size = _DEBUG_CANVAS_SIZE
    img = Image.new("RGB", (size, size), (20, 20, 30))
    draw = ImageDraw.Draw(img)

    # Determine bounds from trail
    all_x = [p[0] for p in trail]
    all_y = [p[1] for p in trail]
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)

    # Add padding and ensure minimum range (500cm = 5m)
    padding = 200  # cm
    range_x = max(max_x - min_x, 500) + padding * 2
    range_y = max(max_y - min_y, 500) + padding * 2
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2

    # Use uniform scale (fit both axes)
    scale = size / max(range_x, range_y)
    margin = 40  # px reserved for text
    usable = size - margin * 2
    scale = usable / max(range_x, range_y)

    def to_px(cx: float, cy: float) -> tuple[int, int]:
        px = int((cx - center_x) * scale + size / 2)
        py = int(-(cy - center_y) * scale + size / 2)  # flip Y
        return px, py

    # Draw grid lines at 100cm (1m) intervals
    grid_interval = 100  # cm
    grid_start_x = int(center_x - range_x / 2)
    grid_start_x = grid_start_x - (grid_start_x % grid_interval)
    grid_start_y = int(center_y - range_y / 2)
    grid_start_y = grid_start_y - (grid_start_y % grid_interval)

    grid_color = (40, 40, 50)
    for gx in range(grid_start_x, int(center_x + range_x / 2) + grid_interval, grid_interval):
        px, _ = to_px(gx, 0)
        if 0 <= px < size:
            draw.line([(px, 0), (px, size)], fill=grid_color)
    for gy in range(grid_start_y, int(center_y + range_y / 2) + grid_interval, grid_interval):
        _, py = to_px(0, gy)
        if 0 <= py < size:
            draw.line([(0, py), (size, py)], fill=grid_color)

    # Draw trail (fading from dim to bright)
    for i, (tx, ty) in enumerate(trail[:-1]):
        alpha = int(80 + 175 * (i / max(len(trail) - 1, 1)))
        color = (0, alpha // 2, alpha)
        px, py = to_px(tx, ty)
        r = 2
        draw.ellipse([px - r, py - r, px + r, py + r], fill=color)

    # Draw robot current position (bright green dot)
    rx, ry = to_px(robot_x, robot_y)
    dot_r = 6
    draw.ellipse(
        [rx - dot_r, ry - dot_r, rx + dot_r, ry + dot_r],
        fill=(0, 255, 80),
    )

    # Draw heading indicator
    import math
    heading_rad = math.radians(robot_heading)
    hx = rx + int(15 * math.cos(heading_rad))
    hy = ry - int(15 * math.sin(heading_rad))
    draw.line([(rx, ry), (hx, hy)], fill=(0, 255, 80), width=2)

    # Draw coordinate text
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    text = f"({robot_x:.1f}, {robot_y:.1f}) cm"
    draw.text((5, 5), text, fill=(200, 200, 200), font=font)
    draw.text((5, 20), f"trail: {len(trail)} pts", fill=(120, 120, 140), font=font)
    draw.text((5, 35), f"heading: {robot_heading:.0f}°", fill=(120, 120, 140), font=font)

    # Origin crosshair (if visible)
    ox, oy = to_px(0, 0)
    if 0 <= ox < size and 0 <= oy < size:
        draw.line([(ox - 8, oy), (ox + 8, oy)], fill=(100, 100, 100))
        draw.line([(ox, oy - 8), (ox, oy + 8)], fill=(100, 100, 100))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
