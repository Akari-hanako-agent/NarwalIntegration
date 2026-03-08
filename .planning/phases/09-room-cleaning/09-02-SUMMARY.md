---
phase: 09-room-cleaning
plan: 02
subsystem: testing
tags: [segment-api, room-cleaning, protobuf, physical-validation, pytest]

requires:
  - phase: 09-room-cleaning
    plan: 01
    provides: start_rooms(), Segment API, _build_room_clean_payload()
provides:
  - 18 unit tests covering client room payload and HA Segment API
  - Physical validation confirming room-specific cleaning works on real hardware
  - Corrected payload format: per-room MapCleanParamInfo fields required (not bare roomId)
affects: []

tech-stack:
  added: []
  patterns: [MapCleanParamInfo per-room fields in protobuf payload]

key-files:
  created:
    - tests/test_client_rooms.py
    - tests/test_vacuum_segments.py
  modified:
    - narwal_client/client.py
    - custom_components/narwal/narwal_client/client.py

key-decisions:
  - "Bare roomId in field 1.2 is ignored by robot; each room entry needs full MapCleanParamInfo fields (cleanMode=2, cleanTimes=1, sweepMode=3, mopMode=2)"
  - "Room-clean response returns code=0 with config data, not the usual code=1 ack"

patterns-established:
  - "Room payload: each room entry must include MapCleanParamInfo (cleanMode, cleanTimes, sweepMode, mopMode)"

requirements-completed: [ROOM-01, ROOM-02, ROOM-03]

duration: 15min
completed: 2026-03-08
---

# Phase 9 Plan 02: Room-Specific Cleaning Tests & Validation Summary

**18 unit tests for Segment API and room payload, plus physical robot validation confirming per-room MapCleanParamInfo fields required**

## Performance

- **Duration:** ~15 min (across checkpoint pause for physical validation)
- **Started:** 2026-03-08T22:00:27Z
- **Completed:** 2026-03-08T23:48:00Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- 7 client-level tests covering payload encoding, multi-room payloads, clean settings preservation, and empty fallback
- 11 vacuum-level tests covering Segment API (get_segments, clean_segments, change detection)
- Physical robot validation confirmed room-specific cleaning works -- robot cleaned only room 14 (Utility Room 2)
- Key discovery: bare roomId in field 1.2 is ignored; full MapCleanParamInfo fields required per room entry
- All 121 tests passing after payload fix (aefcea6)

## Task Commits

Each task was committed atomically:

1. **Task 1: Tests for client start_rooms and payload builder** - `cafd1d2` (test)
2. **Task 2: Tests for vacuum segment API** - `b869679` (test)
3. **Task 3: Physical robot validation** - `aefcea6` (fix) -- payload corrected based on physical test results

## Files Created/Modified
- `tests/test_client_rooms.py` - 7 tests for _build_room_clean_payload and start_rooms
- `tests/test_vacuum_segments.py` - 11 tests for async_get_segments, async_clean_segments, _check_segment_changes
- `narwal_client/client.py` - _build_room_clean_payload updated to include per-room MapCleanParamInfo fields
- `custom_components/narwal/narwal_client/client.py` - Embedded copy synced

## Decisions Made
- Bare roomId in protobuf field 1.2 is ignored by the robot; each room entry must include full MapCleanParamInfo fields (cleanMode=2, cleanTimes=1, sweepMode=3, mopMode=2)
- Room-clean response format differs from whole-house: returns code=0 with config data instead of code=1 ack

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Room clean payload required per-room MapCleanParamInfo fields**
- **Found during:** Task 3 (Physical robot validation)
- **Issue:** Original payload hypothesis (bare roomId as repeated varint in field 1.2) was partially wrong -- robot ignored bare IDs
- **Fix:** Updated _build_room_clean_payload to include cleanMode=2, cleanTimes=1, sweepMode=3, mopMode=2 per room entry
- **Files modified:** narwal_client/client.py, custom_components/narwal/narwal_client/client.py, tests/test_client_rooms.py
- **Verification:** Physical robot cleaned only room 14 with updated payload; all 121 tests pass
- **Committed in:** aefcea6

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential correction discovered during physical validation. This was the expected risk the plan was designed to catch.

## Issues Encountered
None beyond the expected payload format discovery (which the plan explicitly anticipated).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Room-specific cleaning fully validated and working on physical hardware
- Phase 9 complete -- all 3 success criteria met:
  1. Users can select rooms from HA UI and clean only those rooms
  2. Room names in HA match map labels (via RoomInfo.display_name)
  3. Robot cleans only selected rooms and returns to dock
- Ready for Phase 10 (Obstacle Mapping) or Phase 11 (Camera RE)

## Self-Check: PASSED

- FOUND: tests/test_client_rooms.py
- FOUND: tests/test_vacuum_segments.py
- FOUND: cafd1d2 (Task 1)
- FOUND: b869679 (Task 2)
- FOUND: aefcea6 (Task 3 payload fix)

---
*Phase: 09-room-cleaning*
*Completed: 2026-03-08*
