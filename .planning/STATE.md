# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-01)

**Core value:** Users can control and monitor their Narwal Flow vacuum entirely locally — start/stop/pause, see status, view a live floor map — without any cloud dependency.
**Current focus:** Phase 8 IN PROGRESS — Polish & HACS Default Listing

## Current Position

Phase: 8 of 11 — IN PROGRESS (Polish & HACS Default Listing)
Current Plan: 2 of 2
Status: 08-01 complete (connection resilience), 08-02 remaining
Last activity: 2026-03-08 — connection resilience implemented

Progress: [████████░░] 68% (phases 0-7 complete, phase 8 plan 1/2 done)

## Accumulated Context

### Key Decisions (Phase 8)

- Entity availability uses coordinator.last_update_success, not client.connected
- 5 consecutive poll failures before marking unavailable (~5 min grace period)
- Removed client.connect() from poll loop to avoid racing with listener

### Key Decisions (Phase 7)

- Coordinate transform: factor 1.0, pixel = raw - origin (no scaling)
- is_returning requires BOTH field 3.7 AND 3.10 (prevents false positives)
- Room data is 100% local — ROOM_TYPE enum + instance_index for names
- Obstacles are cloud-only (get_vision_image returns empty)
- Trail segment breaks are obstacle avoidance, not a rendering bug (deferred)
- Label overlap matches Narwal app behavior (not an issue to fix)

### Pending Todos

- "Self test paused" unmapped working_status
- CleanTask payload hardcodes max suction / wet mop / single pass
- Validate: does start work WITHOUT CleanTask payload?

### Blockers/Concerns

None — Phase 7 complete, ready to plan Phase 8+

## Session Continuity

Last session: 2026-03-08
Stopped at: Completed 08-01-PLAN.md (connection resilience). Next: 08-02-PLAN.md.
