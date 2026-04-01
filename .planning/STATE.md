---
gsd_state_version: 1.0
milestone: v0.5
milestone_name: milestone
status: Phase 14 ARCHIVED (cloud-only)
stopped_at: Phase 14 archived after probe confirmed shortcuts are cloud-only
last_updated: "2026-04-02T00:10:00.000Z"
last_activity: 2026-04-01 -- Phase 14 archived (shortcuts cloud-only, not local WS)
progress:
  total_phases: 8
  completed_phases: 7
  total_plans: 15
  completed_plans: 13
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-01)

**Core value:** Users can control and monitor their Narwal Flow vacuum entirely locally — start/stop/pause, see status, view a live floor map — without any cloud dependency.
**Current focus:** Phase 14 ARCHIVED — shortcuts cloud-only, no local WS API access

## Current Position

Phase: 14 (shortcuts-presets) — ARCHIVED
Last activity: 2026-04-01 -- Probe confirmed shortcuts are cloud-managed (Alibaba Alink IoT REST), not local WS

Progress: [██████████] 100% (13 plans done)

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
- Furniture obstacles are LOCAL (field 2.32, typeId = APK furniture enum). Vision obstacles likely also local — needs probing during active clean.
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

### Key Decisions (Phase 10)

- Obstacle positions are LOCAL (field 2.32), not cloud-only — corrects Phase 7 assumption
- typeId IS the specific furniture enum from APK map_furniture.json (NOT category codes — corrected after user validation)
- Pass obstacles + origin to render_base_map (not pre-computed grid coords)
- Obstacles render on base map (static, cached) not overlay
- Skip rotation for v1 — axis-aligned rectangles sufficient

### Key Decisions (Phase 11)

- Vision obstacle data source: display_map field 9 (confirmed by probe in plan 11-01)
- detection_seq (field 2) used as dedup ID — robot provides unique incrementing counter
- VisionObstacleInfo is a separate dataclass from ObstacleInfo — different lifecycle and data source
- render_overlay extended with backward-compatible vision_obstacles + origin_x/origin_y params (default None/0)
- Vision obstacles cleared in _reset_trail() — same lifecycle hook as trail (fires on new cleaning session)
- Field 9 has type_id + detection_seq but NOT coordinates — field 12 coordinate parsing deferred

### Key Decisions (Phase 12, Plan 01)

- Snapshot camera is_streaming=False — privacy-first, only fires on explicit button press or service call
- AES-encrypted images stored as raw bytes until APK decryption key extracted — NarwalSnapshotCamera will not display correctly until future plan
- HA test stubs for ButtonEntity/SwitchEntity/Camera use plain class stubs (not MagicMock) to avoid __setattr__ MRO conflicts when entities are instantiated in tests
- Service registered idempotently via has_service guard in async_setup_entry

### Key Decisions (Phase 13, Plan 01)

- X10 Pro (AX15/CNbforyZWI) inserted before "Other / Auto-detect" to preserve auto as last dropdown entry
- Room clean warning embeds per-code guidance text (CONFLICT/NOT_APPLICABLE) for actionable debugging without source knowledge
- FIX-01 (ba53ddb) was pre-committed — plan correctly noted as no-op, not redone

### Blockers/Concerns

None

## Session Continuity

Last session: 2026-04-01T19:43:49.100Z
Stopped at: Completed 13-01-PLAN.md
Resume file: None
