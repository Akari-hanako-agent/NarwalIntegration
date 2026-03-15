---
phase: 11-vision-obstacles
verified: 2026-03-15T14:42:48Z
status: passed
score: 7/7 must-haves verified
re_verification: false
gaps: []
human_verification:
  - test: "Trigger a cleaning run with detectable objects on the floor"
    expected: "Colored circles appear on the map camera feed at obstacle positions, labeled with type names (e.g. Cable, Shoes, Pet Waste)"
    why_human: "End-to-end render path requires live display_map broadcasts with field 9 detections and robot running in HA"
  - test: "Start a second cleaning run after the first completes"
    expected: "Vision obstacle circles from the previous session disappear before new ones accumulate"
    why_human: "Session lifecycle (clear on new session start) requires two real cleaning cycles to verify"
---

# Phase 11: Vision Obstacles Verification Report

**Phase Goal:** Display transient camera-detected obstacles (pet waste, cables, shoes, clothing, etc.) on the map during and after cleaning runs
**Verified:** 2026-03-15T14:42:48Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (from Plan 02 must_haves)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | VisionObstacleInfo dataclass parses vision obstacle protobuf from display_map field 9 + field 12 | VERIFIED | `_parse_vision_obstacles()` in models.py parses field 9 (current detections) and field 12 (trail segments with coordinates), enriches field 9 detections with field 12 coords; 11 dedicated parsing tests pass |
| 2 | All 42 vision obstacle types have display names in TYPE_NAMES | VERIFIED | TYPE_NAMES has 39 entries covering IDs 1-22, 25-32, 34-42; IDs 23, 24, 33 are absent from the APK switch statement (documented in docstring); `test_type_names_coverage_all_42` validates exactly this set |
| 3 | Vision obstacles render as semi-transparent colored circles with type labels on the overlay layer | VERIFIED | `render_overlay()` draws filled ellipses with white outline + display_name label; 9 rendering tests confirm valid PNG, pixel changes, color categories, and out-of-bounds skip |
| 4 | Vision obstacles use yellow/amber color family (hazards=red-amber, clothing=yellow, pet=orange, misc=amber) | VERIFIED | VISION_COLORS dict in render_overlay: hazard=(212,85,58), clothing=(232,184,48), pet=(224,120,48), misc=(200,144,32); `test_hazard_obstacle_uses_red_amber_color` and `test_clothing_obstacle_uses_yellow_color` pass |
| 5 | Vision obstacles accumulate during cleaning and clear when a new cleaning session starts | VERIFIED | `_reset_trail()` clears `self._vision_obstacles = []`; `_handle_coordinator_update` deduplicates and appends new ids; `_reset_trail` called on `is_cleaning and not was_cleaning` transition |
| 6 | narwal_client/ copies are in sync (standalone and embedded) | VERIFIED | `diff narwal_client/models.py custom_components/narwal/narwal_client/models.py` → IDENTICAL; same for client.py and map_renderer.py |
| 7 | Tests verify VisionObstacleInfo parsing and display_name for all type categories | VERIFIED | 31 vision tests in test_models.py (17 TestVisionObstacleInfo + 11 TestParseVisionObstacles + 2 NarwalState + new field12 tests); 9 tests in test_map_renderer.py; all 181 total tests pass |

**Score:** 7/7 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `narwal_client/models.py` | VisionObstacleInfo + _parse_vision_obstacles | VERIFIED | VisionObstacleInfo dataclass at line 182; _parse_vision_obstacles at line 295; _obstacles_from_field12 helper at line 391; _decode_float32_array at line 278 |
| `narwal_client/map_renderer.py` | vision obstacle overlay rendering | VERIFIED | render_overlay() has vision_obstacles + origin_x/origin_y params (line 570-580); VISION_COLORS block with category colors at line 617 |
| `custom_components/narwal/camera.py` | vision obstacle lifecycle | VERIFIED | _vision_obstacles list in __init__ (line 72); cleared in _reset_trail (line 142); accumulated in _handle_coordinator_update (lines 196-201); passed to render_overlay (line 352) |
| `tests/test_models.py` | VisionObstacleInfo tests | VERIFIED | TestVisionObstacleInfo (17 tests), TestParseVisionObstacles (11 tests including 4 field12 tests), TestNarwalStateVisionObstacles (2 tests) |
| `tests/test_map_renderer.py` | vision overlay rendering tests | VERIFIED | TestVisionObstacleOverlay (9 tests) covering PNG validity, pixel changes, colors, ordering, bounds |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| display_map broadcast (field 9 + 12) | VisionObstacleInfo objects | `_parse_vision_obstacles(decoded)` in client.py line 428 | WIRED | `decoded` dict from display_map handler passed directly; field 12 coord extraction inside `_parse_vision_obstacles` |
| VisionObstacleInfo.to_grid_coords | render_overlay vision drawing | `obs.to_grid_coords(origin_x, origin_y)` at map_renderer.py line 634 | WIRED | origin_x/origin_y come from static_map fields passed through camera.py lines 353-354 |
| camera.py session lifecycle | vision obstacle accumulate/clear | `_reset_trail()` at line 138-142; accumulation at lines 196-201 | WIRED | clear fired on `is_cleaning and not was_cleaning`; accumulate deduplicates by obs.id |
| narwal_client/ standalone | custom_components/narwal/narwal_client/ sync | file copy | WIRED | diff confirms all three files (models.py, client.py, map_renderer.py) are byte-identical |

---

### Requirements Coverage

No `REQUIREMENTS.md` file exists in `.planning/`. Requirements VIS-01, VIS-02, VIS-03 are defined only in ROADMAP.md as success criteria for Phase 11. Cross-referencing against ROADMAP.md success criteria:

| Requirement | Source | Description | Status | Evidence |
|-------------|--------|-------------|--------|---------|
| VIS-01 | ROADMAP.md SC1 + 11-01-PLAN.md | Vision obstacle positions retrieved from robot during/after cleaning via display_map | SATISFIED | display_map field 9 parses type_id + detection_seq; field 12 provides float32 coordinates; wired in client.py display_map handler |
| VIS-02 | ROADMAP.md SC2 + 11-02-PLAN.md | Transient obstacles render on map with vision obstacle type labels (42-type enum from APK) | SATISFIED | render_overlay draws colored circles with display_name labels; TYPE_NAMES covers all 39 APK-defined IDs (23/24/33 absent from APK) |
| VIS-03 | ROADMAP.md SC3 + 11-02-PLAN.md | Vision obstacles distinguished from persistent furniture annotations | SATISFIED | Furniture uses `render_base_map` (static, rectangles, tan/brown palette); vision uses `render_overlay` (live, circles, red/yellow/orange palette); separate data sources (get_map field 2.32 vs display_map field 9) |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `narwal_client/map_renderer.py` | 95 | `# round placeholder - gray` | Info | Comment refers to a furniture type name ("Round Placeholder") in the obstacle color table — not a code stub |

No blockers or warnings found. The one "placeholder" hit is a furniture type name in a comment, not an incomplete implementation.

---

### TYPE_NAMES Coverage Note

The plan's truth "All 42 vision obstacle types have display names in TYPE_NAMES" requires clarification: the APK defines 42 type IDs but three (23, 24, 33) have no entry in the APK's switch statement. The implementation correctly covers all 39 APK-defined types and falls back to `"Obstacle N"` for the three undefined ones. The test `test_type_names_coverage_all_42` validates the same 39-entry set, making this consistent and correct — not a gap.

---

### Human Verification Required

#### 1. Live Vision Obstacle Rendering

**Test:** During an active cleaning run with objects (cable, shoe, or fabric) on the floor, open the Narwal map camera in the HA dashboard and watch for colored circles with type labels to appear on the map.
**Expected:** Colored circles (amber for cables, yellow for shoes/fabric) appear at the physical obstacle locations on the floor map as the robot's camera detects them. Labels match the object type.
**Why human:** Requires a live cleaning session with field 9 detections flowing through the full coordinator -> camera -> render_overlay pipeline. Cannot be verified programmatically without a robot.

#### 2. Session Lifecycle Clear

**Test:** Complete one cleaning run (observe obstacles appear), wait for robot to dock, then start a second cleaning run.
**Expected:** All vision obstacle circles from the previous session are gone at the start of the second run, before any new detections appear.
**Why human:** Requires two sequential cleaning sessions to trigger the `is_cleaning and not was_cleaning` transition that calls `_reset_trail()`. The logic is correct in code but only observable on real hardware.

---

### Gaps Summary

No gaps. All must-haves verified:

- VisionObstacleInfo is substantive, not a stub (42-type enum, category classification, coordinate transform, field 9 + field 12 parsing).
- render_overlay is wired end-to-end (camera.py passes vision_obstacles + origin params through to the renderer).
- Session lifecycle is complete (clear on new session, accumulate with dedup, separate from state list).
- narwal_client copies are byte-identical between standalone and embedded.
- 181 tests pass, 40 of which are vision-specific.

The implementation includes one meaningful deviation from the original plan: coordinate population from field 12 trail segments (deferred in plan 02, then added in commit c38904e). This is an improvement over the plan, not a gap — coordinates are now populated when field 12 data is available.

---

_Verified: 2026-03-15T14:42:48Z_
_Verifier: Claude (gsd-verifier)_
