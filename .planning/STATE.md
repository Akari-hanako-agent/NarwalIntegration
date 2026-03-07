# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-01)

**Core value:** Users can control and monitor their Narwal Flow vacuum entirely locally — start/stop/pause, see status, view a live floor map — without any cloud dependency.
**Current focus:** Phase 7 — Map Validation (wake reliability + start validation)

## Current Position

Phase: 7 of 8 (Map Validation)
Plan: 3 of 3 in current phase
Status: In Progress — wake fixes deployed (541ff36), awaiting deep-sleep wake + start command validation
Last activity: 2026-03-06 — 3 commits fixing wake regression, is_docked, entity availability

Progress: [████████░░] 87% (phases 0-6 complete, phase 7 in validation)

## Accumulated Context

### Decisions

- [07-02]: Topic subscription must be renewed every 8min (expires at 10min)
- [07-02]: Don't clear map_display_data on state transitions — let it go stale naturally
- [07-02]: display_map field 1.1 is centimeters (not decimeters) — dock field 8 IS dm
- [S8]: clean/plan/start NEVER returns field5 response — must be fire-and-forget
- [S8]: _ensure_awake must check broadcast age, not just robot_awake flag
- [S8]: wake(force=True) needed when broadcasts stale but flag not yet reset
- [S8]: is_paused stays stale after docking — only trust during CLEANING/CLEANING_ALT
- [S8]: HA 2026.3 adds vacuum.clean_area with Segment(id, name, group) — research saved for Phase 9
- [S9]: NEVER remove get_device_base_status from wake burst — forces active CPU wake
- [S9]: wake() must NOT reconnect when _listener_active — races with keepalive, robot closes old conn
- [S9]: is_docked checks dock fields for ANY non-cleaning status (not just STANDBY)
- [S9]: Entity stays available when sleeping — return stale data, not UpdateFailed
- [S9]: Broadcasts reset poll timer → need _fetch_initial_status() background task

### Pending Todos

- Deploy 541ff36 and validate deep-sleep wake (keepalive escalates after 30s)
- Validate Start button (fire-and-forget, robot should start cleaning)
- If robot doesn't start: sniff Narwal app clean/plan/start payload
- Fix trail: segment breaks on large jumps (>1m grid distance)
- Plan 07-03: post-cleaning map refresh

### Blockers/Concerns

- Start command unvalidated — fire-and-forget removes error but robot may still not clean
- "Self test paused" is unmapped working_status value — shows UNKNOWN
- Stale map after remap: unknown if get_map returns updated data

## Session Continuity

Last session: 2026-03-06
Stopped at: Session 9 — 3 commits (437ead5→541ff36) fixing wake regression. Restored get_device_base_status to burst, fixed is_docked for UNKNOWN status, prevented wake/keepalive interference, entity stays available when sleeping. Need deploy+test.
Resume file: .planning/phases/07-map-validation/.continue-here.md
