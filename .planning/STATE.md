---
gsd_state_version: 1.0
milestone: v0.5
milestone_name: milestone
status: in-progress
last_updated: "2026-03-08T23:48:00Z"
progress:
  total_phases: 2
  completed_phases: 2
  total_plans: 6
  completed_plans: 6
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-01)

**Core value:** Users can control and monitor their Narwal Flow vacuum entirely locally — start/stop/pause, see status, view a live floor map — without any cloud dependency.
**Current focus:** Phase 9 COMPLETE — Room-Specific Cleaning

## Current Position

Phase: 9 of 11 — COMPLETE (Room-Specific Cleaning)
Current Plan: 2 of 2 (all complete)
Status: Phase 9 complete — Segment API, tests, and physical robot validation all done
Last activity: 2026-03-08 — Room-specific cleaning validated on physical robot

Progress: [█████████░] 82% (phases 0-9 complete)

## Accumulated Context

### Key Decisions (Phase 8)

- Entity availability uses coordinator.last_update_success, not client.connected
- 5 consecutive poll failures before marking unavailable (~5 min grace period)
- Removed client.connect() from poll loop to avoid racing with listener
- Mock HA framework via sys.modules stubs (ha_stubs.py) instead of pytest-homeassistant-custom-component
- Test config flow with __new__ + mocked base methods for isolated async_step_user testing

### Key Decisions (Phase 7)

- Coordinate transform: factor 1.0, pixel = raw - origin (no scaling)
- is_returning requires BOTH field 3.7 AND 3.10 (prevents false positives)
- Room data is 100% local — ROOM_TYPE enum + instance_index for names
- Obstacles are cloud-only (get_vision_image returns empty)
- Trail segment breaks are obstacle avoidance, not a rendering bug (deferred)
- Label overlap matches Narwal app behavior (not an issue to fix)

### Key Decisions (Phase 9)

- Room IDs encoded as repeated varint in field 1.2 of CleanTask protobuf
- Segment.group uses Rooms/Utility based on RoomInfo.category
- Empty room_ids in start_rooms() falls back to whole-house clean
- Bare roomId in field 1.2 is IGNORED by robot; each room entry needs full MapCleanParamInfo fields (cleanMode=2, cleanTimes=1, sweepMode=3, mopMode=2)
- Room-clean response returns code=0 with config data (not usual code=1 ack)

### Pending Todos

- "Self test paused" unmapped working_status
- CleanTask payload hardcodes max suction / wet mop / single pass
- Validate: does start work WITHOUT CleanTask payload?

### Blockers/Concerns

None — Phase 9 complete

## Session Continuity

Last session: 2026-03-08
Stopped at: Completed 09-02-PLAN.md (tests + physical robot validation). Phase 9 complete.
