"""Map camera entity for Narwal vacuum."""

from __future__ import annotations

import io
import logging
import math
import time

from aiohttp import web

from homeassistant.components.camera import Camera, CameraEntityFeature, async_get_still_stream
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NarwalConfigEntry
from .coordinator import NarwalCoordinator
from .entity import NarwalEntity
from .narwal_client.const import WorkingStatus

_LOGGER = logging.getLogger(__name__)

# Seconds between MJPEG frames served to the frontend.
_FRAME_INTERVAL = 2.0

# Minimum seconds between re-renders (display_map arrives every ~1.5s
# but PIL rendering is CPU-bound — no need to render every broadcast).
_MIN_RENDER_INTERVAL = 2

# Debug view: blank canvas with robot dot + trail.
# Set to False to use the real map renderer instead.
_DEBUG_VIEW = True
_DEBUG_CANVAS_SIZE = 600  # pixels
_DEBUG_TRAIL_MAX = 50000  # positions — full cleaning session worth
_DEBUG_RECORD_INTERVAL = 5  # seconds between trail point recordings


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
        # Debug view state — full session trail with growing viewport
        self._trail: list[tuple[float, float]] = []
        self._dock_pos: tuple[float, float] | None = None
        self._vp_min_x: float = 0.0
        self._vp_max_x: float = 0.0
        self._vp_min_y: float = 0.0
        self._vp_max_y: float = 0.0
        self._vp_initialized: bool = False
        self._last_trail_record: float = 0.0  # monotonic time of last trail append
        self._last_cleaning_status: WorkingStatus = WorkingStatus.UNKNOWN

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

    def _reset_debug_trail(self) -> None:
        """Clear trail and viewport for a new cleaning session."""
        self._trail.clear()
        self._dock_pos = None
        self._vp_initialized = False
        self._last_trail_record = 0.0

    def _record_debug_position(self, x: float, y: float) -> None:
        """Record a position and expand viewport bounds.

        Called on every display_map update, regardless of whether we render.
        Throttled to one trail point per _DEBUG_RECORD_INTERVAL seconds —
        the robot moves slowly enough that 5s intervals capture the full path.
        The first position is always recorded immediately (dock marker).
        Viewport bounds expand on every call (even when trail point is skipped).
        """
        now = time.monotonic()

        # First position = dock/start marker — always record immediately
        if self._dock_pos is None:
            self._dock_pos = (x, y)
            self._trail.append((x, y))
            self._last_trail_record = now
        elif (
            now - self._last_trail_record >= _DEBUG_RECORD_INTERVAL
            and len(self._trail) < _DEBUG_TRAIL_MAX
        ):
            self._trail.append((x, y))
            self._last_trail_record = now

        # Expand viewport on EVERY update (not just recorded points)
        if not self._vp_initialized:
            self._vp_min_x = x
            self._vp_max_x = x
            self._vp_min_y = y
            self._vp_max_y = y
            self._vp_initialized = True
        else:
            if x < self._vp_min_x:
                self._vp_min_x = x
            if x > self._vp_max_x:
                self._vp_max_x = x
            if y < self._vp_min_y:
                self._vp_min_y = y
            if y > self._vp_max_y:
                self._vp_max_y = y

    @callback
    def _handle_coordinator_update(self) -> None:
        """Re-render the map when new data arrives from the coordinator."""
        state = self.coordinator.client.state
        display = state.map_display_data

        _LOGGER.debug(
            "camera update: debug=%s, display=%s, robot=(%.2f, %.2f), cached=%s",
            _DEBUG_VIEW,
            display is not None,
            display.robot_x if display else 0,
            display.robot_y if display else 0,
            self._cached_image is not None,
        )

        if _DEBUG_VIEW:
            # Detect new cleaning session — clear trail for fresh tracking
            current_status = state.working_status
            if (
                current_status
                in (WorkingStatus.CLEANING, WorkingStatus.CLEANING_ALT)
                and self._last_cleaning_status
                not in (WorkingStatus.CLEANING, WorkingStatus.CLEANING_ALT)
            ):
                _LOGGER.info(
                    "New cleaning session detected (%s -> %s) — clearing debug trail",
                    self._last_cleaning_status.name,
                    current_status.name,
                )
                self._reset_debug_trail()
            if current_status != WorkingStatus.UNKNOWN:
                self._last_cleaning_status = current_status

            # Skip if no display data or robot at origin
            if not display or (display.robot_x == 0.0 and display.robot_y == 0.0):
                self.async_write_ha_state()
                return

            # Always record position BEFORE throttle check — never lose trail points
            self._record_debug_position(display.robot_x, display.robot_y)

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
            trail = list(self._trail)
            dock = self._dock_pos
            viewport = None
            if self._vp_initialized:
                viewport = (
                    self._vp_min_x, self._vp_min_y,
                    self._vp_max_x, self._vp_max_y,
                )
            try:
                png_bytes = await self.hass.async_add_executor_job(
                    _render_debug_view,
                    display.robot_x,
                    display.robot_y,
                    display.robot_heading,
                    trail,
                    dock,
                    viewport,
                )
                if png_bytes:
                    self._cached_image = png_bytes
                    self._cache_key = new_key
                    self._last_render_time = time.monotonic()
                    self._render_count += 1
                    _LOGGER.debug(
                        "debug rendered #%d: raw=(%.1f,%.1f) trail=%d vp=%s",
                        self._render_count,
                        display.robot_x, display.robot_y,
                        len(trail),
                        viewport,
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
    dock_pos: tuple[float, float] | None = None,
    viewport: tuple[float, float, float, float] | None = None,
) -> bytes:
    """Render a blank canvas with full cleaning trail, dock marker, and robot dot.

    The viewport only grows (never shrinks) so the view is stable as the robot
    explores. Trail is drawn as connected line segments for a clean path.
    Long trails are downsampled for rendering performance.
    """
    from PIL import Image, ImageDraw, ImageFont

    size = _DEBUG_CANVAS_SIZE
    img = Image.new("RGB", (size, size), (20, 20, 30))
    draw = ImageDraw.Draw(img)

    # Determine viewport from growing bounds
    if viewport:
        min_x, min_y, max_x, max_y = viewport
    elif trail:
        all_x = [p[0] for p in trail]
        all_y = [p[1] for p in trail]
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
    else:
        min_x = robot_x - 250
        max_x = robot_x + 250
        min_y = robot_y - 250
        max_y = robot_y + 250

    # Padding and minimum range (200cm = 2m)
    padding = 100  # cm
    range_x = max(max_x - min_x, 200) + padding * 2
    range_y = max(max_y - min_y, 200) + padding * 2
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2

    # Uniform scale with margin for text
    margin = 50  # px reserved for text overlay
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

    grid_color = (35, 35, 45)
    for gx in range(grid_start_x, int(center_x + range_x / 2) + grid_interval, grid_interval):
        px, _ = to_px(gx, 0)
        if 0 <= px < size:
            draw.line([(px, 0), (px, size)], fill=grid_color)
    for gy in range(grid_start_y, int(center_y + range_y / 2) + grid_interval, grid_interval):
        _, py = to_px(0, gy)
        if 0 <= py < size:
            draw.line([(0, py), (size, py)], fill=grid_color)

    # Draw trail as connected line segments
    # Downsample for rendering if trail is very long (>3000 points)
    if trail:
        n = len(trail)
        if n > 3000:
            # Keep every Nth point for the bulk, plus all of the last 200
            step = max(n // 2000, 2)
            bulk = trail[: n - 200 : step]
            recent = trail[n - 200 :]
            render_trail = bulk + recent
        else:
            render_trail = trail

        # Draw path lines — dim blue for old, bright blue for recent
        recent_start = max(len(render_trail) - 200, 0)
        for i in range(len(render_trail) - 1):
            if i >= recent_start:
                # Recent: bright blue
                color = (30, 120, 255)
            else:
                # Older: dim blue
                color = (15, 60, 130)
            x1, y1 = to_px(render_trail[i][0], render_trail[i][1])
            x2, y2 = to_px(render_trail[i + 1][0], render_trail[i + 1][1])
            draw.line([(x1, y1), (x2, y2)], fill=color, width=2)

    # Draw dock/start marker (orange)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    if dock_pos:
        dx, dy = to_px(dock_pos[0], dock_pos[1])
        r = 8
        draw.ellipse(
            [dx - r, dy - r, dx + r, dy + r],
            fill=(255, 140, 0),
            outline=(255, 200, 100),
        )
        draw.text((dx + 12, dy - 6), "DOCK", fill=(255, 140, 0), font=font)

    # Draw robot current position (bright green dot)
    rx, ry = to_px(robot_x, robot_y)
    dot_r = 7
    draw.ellipse(
        [rx - dot_r, ry - dot_r, rx + dot_r, ry + dot_r],
        fill=(0, 255, 80),
        outline=(150, 255, 180),
    )

    # Draw heading indicator
    heading_rad = math.radians(robot_heading)
    hx = rx + int(18 * math.cos(heading_rad))
    hy = ry - int(18 * math.sin(heading_rad))
    draw.line([(rx, ry), (hx, hy)], fill=(0, 255, 80), width=2)

    # Info overlay (top-left)
    text_color = (180, 180, 190)
    dim_color = (100, 100, 120)
    y_text = 5
    draw.text((5, y_text), f"pos: ({robot_x:.1f}, {robot_y:.1f}) cm", fill=text_color, font=font)
    y_text += 15
    draw.text((5, y_text), f"trail: {len(trail)} pts", fill=dim_color, font=font)
    y_text += 15
    draw.text((5, y_text), f"heading: {robot_heading:.0f}", fill=dim_color, font=font)
    y_text += 15
    view_w = range_x / 100
    view_h = range_y / 100
    draw.text((5, y_text), f"view: {view_w:.1f}x{view_h:.1f}m", fill=dim_color, font=font)

    # Origin crosshair (if visible)
    ox, oy = to_px(0, 0)
    if 0 <= ox < size and 0 <= oy < size:
        draw.line([(ox - 8, oy), (ox + 8, oy)], fill=(80, 80, 80))
        draw.line([(ox, oy - 8), (ox, oy + 8)], fill=(80, 80, 80))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
