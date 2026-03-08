# Roadmap: Narwal Flow Home Assistant Integration

## Milestones

- ✅ **v0.5 Map Validation & Polish** — Phases 0-8 (shipped 2026-03-08)
- 📋 **Phase 9: Room-Specific Cleaning** — HA 2026.3 clean_area support
- 📋 **Phase 10: Obstacle Mapping** — Furniture/object detection on map
- 📋 **Phase 11: Camera RE** — Local camera feed for security/pet-sitting

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
- [ ] 09-01-PLAN.md — Implement Segment API + start_rooms() + sync copies
- [ ] 09-02-PLAN.md — Tests + physical robot validation

**Research**: See ha-vacuum-segments.md in memory for HA 2026.3 API research

### 📋 Phase 10: Obstacle Mapping

**Goal**: Display furniture and obstacle positions as overlays on the floor map
**Depends on**: Phase 7 (complete)
**Success Criteria**:
  1. Detected obstacles render on the map at their physical locations
  2. Obstacle types are labeled (furniture, cable, shoe, etc.)
**Context**: get_vision_image returns empty (cloud-only). Need deeper RE.
**Plans**: TBD

### 📋 Phase 11: Camera RE

**Goal**: Access the robot's camera feed locally for security/pet-sitting applications
**Depends on**: Phase 0 (protocol knowledge)
**Success Criteria**:
  1. Camera video stream accessible without Narwal cloud
  2. PIN authentication bypassed or replicated locally
  3. Live feed viewable as HA camera entity or standalone
**Plans**: TBD

## Progress

**Execution Order:** Phase 9 → Phase 10 → Phase 11

| Phase | Status | Completed |
|-------|--------|-----------|
| 0-8 (v0.5) | Complete | 2026-03-08 |
| 9. Room-Specific Cleaning | Planning complete | - |
| 10. Obstacle Mapping | Not started (research needed) | - |
| 11. Camera RE | Not started (research needed) | - |
