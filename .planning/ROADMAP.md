# Roadmap: Narwal Flow Home Assistant Integration

## Milestones

- ✅ **v0.5 Map Validation & Polish** — Phases 0-8 (shipped 2026-03-08)
- 📋 **Phase 9: Room-Specific Cleaning** — HA 2026.3 clean_area support
- 📋 **Phase 10: Obstacle Mapping** — Furniture/object detection on map
- 📋 **Phase 11: Vision Obstacles** — Transient camera-detected obstacles during cleaning
- 📋 **Phase 12: Camera & Patrol** — Snapshot capture, patrol/cruise, LED control, live feed RE

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

### 📋 Phase 11: Vision Obstacles

**Goal**: Display transient camera-detected obstacles (pet waste, cables, shoes, clothing, etc.) on the map during and after cleaning runs
**Depends on**: Phase 10 (obstacle rendering infrastructure)
**Success Criteria**:
  1. Vision obstacle positions retrieved from robot during/after cleaning via `get_vision_image` or `display_map`
  2. Transient obstacles render on map with vision obstacle type labels (42-type enum from APK)
  3. Vision obstacles distinguished from persistent furniture annotations
**Requirements:** [VIS-01, VIS-02, VIS-03]
**Plans:** 2 plans

Plans:
- [x] 11-01-PLAN.md — Probe script + live data capture during cleaning (checkpoint)
- [x] 11-02-PLAN.md — VisionObstacleInfo model, parsing, overlay rendering, tests, sync

**Research**: See 11-RESEARCH.md — APK schema confirmed (MapVisionInfo, MapVisionBox, 42-type enum). Data source needs live probing during clean.

### 📋 Phase 12: Camera & Patrol

**Goal**: Local camera snapshot capture, patrol/cruise mode, and LED control for security/pet-sitting automation
**Depends on**: Phase 0 (protocol knowledge)
**Success Criteria**:
  1. Take a photo via `/developer/take_picture` and retrieve the image
  2. Control camera LED via `/developer/led_control` for low-light scenarios
  3. HA automation: presence detection → send robot to room → capture photo → notify
  4. Patrol/cruise mode: navigate room waypoints capturing photos (`/video_cruise_record`, `/cruise_image_preview`)
**Plans**: TBD (needs probing of camera topics first)

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

## Progress

**Execution Order:** Phase 9 → Phase 10 → Phase 11 → Phase 12

| Phase | Status | Completed |
|-------|--------|-----------|
| 0-8 (v0.5) | Complete | 2026-03-08 |
| 9. Room-Specific Cleaning | Complete | 2026-03-08 |
| 10. Obstacle Mapping | Complete | 2026-03-09 |
| 11. Vision Obstacles | 2/2 | Complete    | 2026-03-15 | 12. Camera & Patrol | Not started (research needed) | - |
