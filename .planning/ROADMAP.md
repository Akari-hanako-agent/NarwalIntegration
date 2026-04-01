# Roadmap: Narwal Flow Home Assistant Integration

## Milestones

- ✅ **v0.5 Map Validation & Polish** — Phases 0-8 (shipped 2026-03-08)
- 📋 **Phase 9: Room-Specific Cleaning** — HA 2026.3 clean_area support
- 📋 **Phase 10: Obstacle Mapping** — Furniture/object detection on map
- 🗃️ **Phase 11: Vision Obstacles** — ARCHIVED (raw AI stream unusable for map overlay)
- 📋 **Phase 12: Camera & Patrol** — Snapshot capture, patrol/cruise, LED control, live feed RE
- 📋 **Phase 13: Community Fixes & Multi-Model** — Critical bug fixes, X10 Pro support, room clean investigation
- 🗃️ **Phase 14: Shortcuts & Presets** — ARCHIVED (cloud-only, not accessible via local WS API)

## Phases

<details>
<summary>✅ v0.5 Map Validation & Polish (Phases 0-8) — SHIPPED 2026-03-08</summary>

- Phase 0: Protocol reverse engineering
- Phase 1: narwal_client standalone library
- Phase 2: Push-mode coordinator + 60s polling fallback
- Phase 3: HA integration (config flow, vacuum entity, sensors)
- Phase 4-5: Map image entity (static floor plan + live overlay)
- Phase 6: HACS installable via custom repo URL
- Phase 7: Map validation & command hardening (room labels, coordinate transform, state mapping)
- Phase 8: Polish and HACS Default (connection resilience, config flow tests, coordinator tests)

</details>

### 📋 Phase 9: Room-Specific Cleaning

**Goal**: Users can select specific rooms to clean from the HA dashboard using the HA 2026.3 vacuum.clean_area service
**Depends on**: Phase 7 (complete — room IDs decoded)
**Success Criteria**:
  1. User can select one or more rooms from the HA UI and start cleaning only those rooms
  2. Room names in HA match the room labels on the map
  3. Robot cleans only the selected rooms and returns to dock
**Requirements:** [ROOM-01, ROOM-02, ROOM-03]
**Plans:** 2 plans

Plans:
- [x] 09-01-PLAN.md — Implement Segment API + start_rooms() + sync copies
- [x] 09-02-PLAN.md — Tests + physical robot validation

**Research**: See ha-vacuum-segments.md in memory for HA 2026.3 API research

### 📋 Phase 10: Obstacle Mapping

**Goal**: Display furniture and obstacle positions as colored rectangles with type labels on the floor map, parsed from local get_map field 2.32 data
**Depends on**: Phase 7 (complete)
**Success Criteria**:
  1. Detected obstacles render on the map at their physical locations
  2. Obstacle types are labeled (furniture, cable, shoe, etc.)
**Requirements:** [OBS-01, OBS-02]
**Plans:** 1 plan

Plans:
- [x] 10-01-PLAN.md — ObstacleInfo model + map rendering + tests + sync

**Research**: See 10-RESEARCH.md — obstacle data is LOCAL in field 2.32 (not cloud-only as previously assumed)

### 🗃️ Phase 11: Vision Obstacles — ARCHIVED

**Goal**: Display transient camera-detected obstacles on the map during cleaning
**Outcome**: ARCHIVED — Feature built, tested live, and removed. display_map field 9/12 provides raw AI detection candidates (every object the camera tentatively identifies), not confirmed objects. The confirmed/filtered set shown in the Narwal app is not accessible via the local WebSocket API.
**Plans:** 2 plans (executed, then reverted)

Plans:
- [x] 11-01-PLAN.md — Probe script + live data capture during cleaning
- [x] 11-02-PLAN.md — VisionObstacleInfo model, parsing, overlay rendering, tests, sync
- Removal commit: 21bbdea

**Key findings**:
- Field 9: raw AI detection stream (3-6x more detections than app shows)
- Detection positions drift with robot (trail endpoints, not fixed positions)
- `get_vision_image` returns NOT_APPLICABLE during cleaning
- Feature recoverable from git history if confirmed data source found later

### 📋 Phase 12: Camera & Patrol

**Goal**: On-demand camera snapshot capture and LED fill light control via local WebSocket API, providing building blocks for "motion detected -> robot goes to room -> takes photos" automation
**Depends on**: Phase 0 (protocol knowledge), Phase 9 (room navigation)
**Success Criteria**:
  1. Take a photo via `/developer/take_picture` and retrieve the image
  2. Control camera LED via `/developer/led_control` for low-light scenarios
  3. Button entity + custom service for snapshot trigger (single + burst mode)
  4. Snapshot camera entity displays latest capture; images saved to HA media directory
**Requirements:** [CAM-01, CAM-02, CAM-03]
**Plans:** 2 plans

Plans:
- [ ] 12-01-PLAN.md — Client commands + button/switch/snapshot camera entities + service + tests
- [ ] 12-02-PLAN.md — Live probe of LED control + snapshot format analysis + physical verification

**Known local topics (from APK)**:
- `/developer/take_picture` — snapshot capture
- `/developer/led_control` — camera fill light
- `/developer/get_robot_debug_image` — debug image retrieval
- `/video_cruise_record` — patrol mission management
- `/video_cruise_edit` — edit patrol waypoints (has `cruisePointRoomId`)
- `/cruise_image_preview` — preview patrol captured images
- `/cruise_album` — patrol photo album
- `/timing_cruise_list` — scheduled patrol tasks
- `/status/video_cruise_task_status` — patrol task status

**Note**: Live video streaming uses Agora P2P via cloud auth (Alibaba IoT REST APIs). PIN auth is cloud-side for live stream only — snapshot and patrol features appear to be separate local commands.

**Update (2026-04-01)**: @northwestsupra shared full APK decompilation (v2.6.81) including .proto files — critical for AES snapshot decryption research in plan 12-02.

### 📋 Phase 13: Community Fixes & Multi-Model

**Goal**: Fix critical bugs reported by community, add X10 Pro model support, investigate room cleaning issues
**Depends on**: Phase 9 (room cleaning), Phase 12 (current)
**Success Criteria**:
  1. Z10 Ultra `last_seen_segments` crash fixed — listener no longer crashes (#11)
  2. Freo X10 Pro recognized in config flow with correct naming (#12)
  3. Room clean CONFLICT (code=3) root cause identified and documented (#10)
  4. Product key annotations updated (AX15 = X10 Pro confirmed)
  5. README compatibility table updated with X10 Pro
**Requirements:** [FIX-01, FIX-02, FIX-03]
**Plans:** 1 plan

Plans:
- [x] 13-01-PLAN.md — X10 Pro model support (FIX-02), room clean error logging (FIX-03); FIX-01 pre-committed

Issues:
- #11 — `last_seen_segments` AttributeError crashes listener (HIGH — breaks Z10 Ultra) -- FIXED (ba53ddb)
- #12 — X10 Pro product key confirmed (CNbforyZWI = AX15), needs config flow + naming
- #10 — Room clean returns CONFLICT or ignores room selection (needs investigation)

### 🗃️ Phase 14: Shortcuts & Presets — ARCHIVED

**Goal**: Discover and expose Narwal app "Shutcut" presets via HA select entity + execute service, enabling automation of robot-stored cleaning configurations
**Outcome**: ARCHIVED — Shortcuts are cloud-managed (Alibaba Alink IoT REST APIs), not exposed via local WebSocket API on port 9002. Probed 8 topic candidates; all shortcut-specific topics timed out, general config/feature topics contain no shortcut data. The feature exists in the Narwal app but definitions and execution are routed through cloud infrastructure.
**Plans:** 2 plans (01 partially executed, 02 not started)

Plans:
- [x] 14-01-PLAN.md — Probe robot for shortcut WS topics (discovery) — **cloud-only confirmed**
- [ ] 14-02-PLAN.md — ShortcutInfo model + SelectEntity — NOT EXECUTED (no local data source)

**Key findings**:
- `shortcut/get`, `clean/shortcut/get`, `robot/shortcut/get` all timeout (topics don't exist)
- `config/get` and `common/get_feature_list` return no shortcut fields
- `clean/cur_plan/get` returns current cleaning plan (per-room MapCleanParamInfo) — room-specific cleaning via Phase 9 already covers this use case
- APK `NrRobotShortcutListGetRequester` confirms cloud REST path
- Shortcuts feature exists in app (user-created presets) but is cloud-only

Issues:
- #13 — Feature request from @ShifuSonny (Flow user) — findings posted

## Progress

**Execution Order:** Phase 9 → Phase 10 → Phase 11 → Phase 12 → Phase 13 → Phase 14

| Phase | Status | Completed |
|-------|--------|-----------|
| 0-8 (v0.5) | Complete | 2026-03-08 |
| 9. Room-Specific Cleaning | Complete | 2026-03-08 |
| 10. Obstacle Mapping | Complete | 2026-03-09 |
| 11. Vision Obstacles | ARCHIVED | 2026-03-15 |
| 12. Camera & Patrol | In Progress (plan 01 done) | - |
| 13. Community Fixes & Multi-Model | Complete | 2026-04-01 |
| 14. Shortcuts & Presets | ARCHIVED | 2026-04-01 |
