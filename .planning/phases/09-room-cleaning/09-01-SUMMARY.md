---
phase: 09-room-cleaning
plan: 01
subsystem: vacuum
tags: [segment-api, room-cleaning, protobuf, ha-2026.3]

requires:
  - phase: 07-map-validation
    provides: RoomInfo model with display_name, MapData.rooms from get_map
provides:
  - start_rooms() method for room-specific cleaning via clean/plan/start
  - HA Segment API (async_get_segments, async_clean_segments)
  - CLEAN_AREA feature flag on vacuum entity
  - Segment change detection with repair issue creation
affects: [09-02-robot-validation]

tech-stack:
  added: []
  patterns: [HA 2026.3 Segment API, blackboxprotobuf encode for room payloads]

key-files:
  created: []
  modified:
    - narwal_client/client.py
    - custom_components/narwal/vacuum.py
    - custom_components/narwal/narwal_client/client.py
    - tests/ha_stubs.py

key-decisions:
  - "Room IDs encoded as repeated varint in field 1.2 of CleanTask protobuf"
  - "Segment.group uses Rooms/Utility based on RoomInfo.category"
  - "Empty room_ids falls back to whole-house clean"

patterns-established:
  - "Segment API: RoomInfo.room_id -> str for Segment.id, int conversion back for robot commands"
  - "Segment change detection via coordinator update callback comparing (id, name) sets"

requirements-completed: [ROOM-01, ROOM-02, ROOM-03]

duration: 2min
completed: 2026-03-08
---

# Phase 9 Plan 01: Room-Specific Cleaning API Summary

**HA 2026.3 Segment API with start_rooms() sending room IDs as repeated varint in CleanTask field 1.2**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-08T21:58:11Z
- **Completed:** 2026-03-08T22:00:27Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- NarwalClient.start_rooms() builds protobuf payload with room IDs in field 1.2 via blackboxprotobuf
- NarwalVacuum implements full HA 2026.3 Segment API (get_segments, clean_segments, change detection)
- CLEAN_AREA feature flag advertised, segments grouped by room category (Rooms/Utility)
- Embedded narwal_client copy synced with start_rooms() method

## Task Commits

Each task was committed atomically:

1. **Task 1: Add start_rooms() to narwal_client** - `dbd5541` (feat)
2. **Task 2: Implement HA Segment API in vacuum.py** - `862a598` (feat)
3. **Task 3: Sync embedded narwal_client copy** - `88282d2` (chore)

## Files Created/Modified
- `narwal_client/client.py` - Added start_rooms() and _build_room_clean_payload() methods
- `custom_components/narwal/vacuum.py` - Added Segment API methods, CLEAN_AREA feature, change detection
- `custom_components/narwal/narwal_client/client.py` - Synced embedded copy with start_rooms()
- `tests/ha_stubs.py` - Added Segment stub for test compatibility

## Decisions Made
- Room IDs encoded as repeated varint in field 1.2 using blackboxprotobuf.encode_message() with explicit typedef
- Segment.group set to "Rooms" (category=1) or "Utility" (category=2) for UI organization
- Empty room_ids in start_rooms() falls back to whole-house clean via start()
- Payload hypothesis (field 1.2 = room selection) requires physical robot validation in Plan 02

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added Segment to HA test stubs**
- **Found during:** Task 2 (Segment API implementation)
- **Issue:** `Segment` class not in ha_stubs.py, tests would fail on import
- **Fix:** Added `ha_vac.Segment = MagicMock` to ha_stubs.py
- **Files modified:** tests/ha_stubs.py
- **Verification:** All 103 tests pass
- **Committed in:** 862a598 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary for test compatibility. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Segment API complete, ready for physical robot validation in Plan 02
- Room-clean payload format (field 1.2 = repeated varint room IDs) needs empirical validation
- If validation fails, only _build_room_clean_payload() needs updating

---
*Phase: 09-room-cleaning*
*Completed: 2026-03-08*
