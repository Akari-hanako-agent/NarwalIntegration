"""Tests for narwal_client.models — state data models."""

from __future__ import annotations

import struct

from narwal_client.const import WorkingStatus
from narwal_client.models import (
    MapData,
    NarwalState,
    ObstacleInfo,
    VisionObstacleInfo,
    _decode_float32_array,
    _parse_obstacles,
    _parse_vision_obstacles,
)


class TestNarwalState:
    """Tests for NarwalState data model."""

    def test_default_state(self) -> None:
        state = NarwalState()
        assert state.working_status == WorkingStatus.UNKNOWN
        assert state.battery_level == 0
        assert state.firmware_version == ""
        assert not state.is_cleaning
        assert not state.is_docked
        assert not state.is_returning

    def test_update_from_working_status(self) -> None:
        """working_status topic sets cleaning metrics, not robot state."""
        state = NarwalState()
        state.update_from_working_status({"3": 120, "13": 18000, "15": 600})
        assert state.cleaning_time == 120
        assert state.cleaning_area == 18000
        # working_status is NOT set by this method (comes from base_status)
        assert state.working_status == WorkingStatus.UNKNOWN

    def test_update_from_base_status_cleaning(self) -> None:
        state = NarwalState()
        state.update_from_base_status({"3": {"1": 4}, "2": _float_to_uint32(85.0)})
        assert state.working_status == WorkingStatus.CLEANING
        assert state.is_cleaning
        assert state.battery_level == 85

    def test_update_from_base_status_docked(self) -> None:
        state = NarwalState()
        state.update_from_base_status({"3": {"1": 10, "10": 1}})
        assert state.working_status == WorkingStatus.DOCKED
        assert state.is_docked

    def test_update_from_base_status_charged(self) -> None:
        """Status 14 = fully charged on dock."""
        state = NarwalState()
        state.update_from_base_status({
            "3": {"1": 14, "10": 1},
            "2": _float_to_uint32(100.0),
            "38": 100,
        })
        assert state.working_status == WorkingStatus.CHARGED
        assert state.is_docked
        assert state.battery_level == 100
        assert state.battery_health == 100

    def test_update_from_base_status_standby_on_dock(self) -> None:
        """STANDBY(1) with dock sub-state=1 means docked."""
        state = NarwalState()
        state.update_from_base_status({"3": {"1": 1, "10": 1}})
        assert state.working_status == WorkingStatus.STANDBY
        assert state.is_docked

    def test_update_from_base_status_standby_off_dock_field11(self) -> None:
        """STANDBY(1) with field 11=1 means off dock (validated via dock_research)."""
        state = NarwalState()
        state.update_from_base_status({
            "3": {"1": 1, "3": 2}, "11": 1, "47": 2,
            "2": _float_to_uint32(100.0),
        })
        assert state.working_status == WorkingStatus.STANDBY
        assert state.dock_field11 == 1
        assert state.dock_field47 == 2
        assert not state.is_docked

    def test_update_from_base_status_standby_on_dock_field11(self) -> None:
        """STANDBY(1) with field 11=2 means on dock (validated via dock_research).

        5 captures: field 11=2 in all 3 on-dock, field 11=1 in both off-dock.
        """
        state = NarwalState()
        state.update_from_base_status({
            "3": {"1": 1, "3": 6}, "11": 2, "47": 3,
        })
        assert state.working_status == WorkingStatus.STANDBY
        assert state.dock_field11 == 2
        assert state.dock_field47 == 3
        assert state.is_docked

    def test_update_from_base_status_standby_on_dock_field47_only(self) -> None:
        """STANDBY(1) with field 47=3 means on dock (secondary signal)."""
        state = NarwalState()
        state.update_from_base_status({"3": {"1": 1}, "47": 3})
        assert state.working_status == WorkingStatus.STANDBY
        assert state.is_docked

    def test_update_from_base_status_standby_no_signals(self) -> None:
        """STANDBY(1) with no dock signals at all — NOT docked (safe default)."""
        state = NarwalState()
        state.update_from_base_status({"3": {"1": 1}})
        assert state.working_status == WorkingStatus.STANDBY
        assert not state.is_docked

    def test_update_from_base_status_standby_dock_activity(self) -> None:
        """STANDBY(1) with dock_activity > 0 means docked."""
        state = NarwalState()
        state.update_from_base_status({"3": {"1": 1, "12": 2}})
        assert state.working_status == WorkingStatus.STANDBY
        assert state.is_docked

    def test_update_from_base_status_paused(self) -> None:
        """Paused overlay: field 3 sub-field 2 = 1."""
        state = NarwalState()
        state.update_from_base_status({"3": {"1": 4, "2": 1}})
        assert state.working_status == WorkingStatus.CLEANING
        assert state.is_paused
        assert not state.is_cleaning  # is_cleaning is False when paused

    def test_update_from_base_status(self) -> None:
        state = NarwalState()
        state.update_from_base_status({
            "2": _float_to_uint32(85.0),
            "38": 100,
            "36": 1757252225,
            "13": "d4bec8c82c484a3ba0428bb0dd4359e2",
        })
        assert state.battery_level == 85
        assert state.battery_health == 100
        assert state.timestamp == 1757252225
        assert state.session_id == "d4bec8c82c484a3ba0428bb0dd4359e2"

    def test_update_from_upgrade_status(self) -> None:
        state = NarwalState()
        state.update_from_upgrade_status({
            "7": "v01.02.19.02",
            "8": "v01.02.19.02",
            "4": 10,
        })
        assert state.firmware_version == "v01.02.19.02"
        assert state.firmware_target == "v01.02.19.02"
        assert state.upgrade_status_code == 10

    def test_update_from_download_status(self) -> None:
        state = NarwalState()
        state.update_from_download_status({"1": 2})
        assert state.download_status == 2

    def test_incremental_updates(self) -> None:
        """State should accumulate across multiple topic updates."""
        state = NarwalState()
        state.update_from_base_status({"3": {"1": 4}, "2": _float_to_uint32(95.0)})
        state.update_from_working_status({"3": 120, "13": 18000})
        state.update_from_upgrade_status({"7": "v01.02.19.02"})

        assert state.battery_level == 95
        assert state.is_cleaning
        assert state.cleaning_time == 120
        assert state.cleaning_area == 18000
        assert state.firmware_version == "v01.02.19.02"

    def test_raw_data_preserved(self) -> None:
        state = NarwalState()
        raw = {"2": _float_to_uint32(100.0), "38": 100, "47": 2, "unknown_field": "value"}
        state.update_from_base_status(raw)
        assert state.raw_base_status == raw

    def test_battery_field2_float32_83(self) -> None:
        """Field 2 = 1118175232 → 83.0% battery (confirmed from monitor capture)."""
        state = NarwalState()
        state.update_from_base_status({"2": 1118175232})
        assert state.battery_level == 83

    def test_battery_field2_float32_85(self) -> None:
        """Field 2 = 1118437376 → 85.0% battery."""
        state = NarwalState()
        state.update_from_base_status({"2": 1118437376})
        assert state.battery_level == 85

    def test_battery_field2_as_python_float(self) -> None:
        """bbp may return field 2 as a Python float directly."""
        state = NarwalState()
        state.update_from_base_status({"2": 83.0})
        assert state.battery_level == 83

    def test_battery_health_field38_static(self) -> None:
        """Field 38 is static battery health (always 100), not real-time SOC."""
        state = NarwalState()
        state.update_from_base_status({"38": 100})
        assert state.battery_health == 100
        # battery_level unchanged (no field 2)
        assert state.battery_level == 0

    def test_battery_only_update_ignores_working_status(self) -> None:
        """update_battery_from_base_status updates battery but NOT working_status.

        When robot is in deep sleep, get_status() returns current battery
        but stale working_status. The battery-only method must not overwrite
        the last authoritative working_status.
        """
        state = NarwalState()
        # Simulate last authoritative state from a broadcast: DOCKED
        state.update_from_base_status({
            "3": {"1": 10, "10": 1},
            "2": _float_to_uint32(80.0),
        })
        assert state.working_status == WorkingStatus.DOCKED
        assert state.battery_level == 80

        # Now simulate a deep-sleep get_status() response with stale CLEANING
        # but fresh battery. Use battery-only update.
        stale_response = {
            "3": {"1": 4, "7": 1},  # stale CLEANING+returning
            "2": _float_to_uint32(85.0),
            "38": 100,
        }
        state.update_battery_from_base_status(stale_response)

        # Battery updated, working_status preserved from last authoritative source
        assert state.battery_level == 85
        assert state.battery_health == 100
        assert state.working_status == WorkingStatus.DOCKED  # NOT overwritten
        assert state.is_docked  # still correct

    def test_returning_to_dock_field7(self) -> None:
        """Field 3.7=1 indicates returning to dock (confirmed live)."""
        state = NarwalState()
        # Live data: {1=4, 7=1, 10=2} — CLEANING + returning + docking
        state.update_from_base_status({"3": {"1": 4, "7": 1, "10": 2}})
        assert state.working_status == WorkingStatus.CLEANING
        assert state.is_returning_to_dock
        assert state.dock_sub_state == 2
        assert state.is_returning  # should be True via field 3.7
        assert not state.is_cleaning  # returning takes priority

    def test_returning_clears_when_docked(self) -> None:
        """Returning flag clears when robot docks."""
        state = NarwalState()
        # During return
        state.update_from_base_status({"3": {"1": 4, "7": 1, "10": 2}})
        assert state.is_returning
        # After docking: {1=14, 12=2}
        state.update_from_base_status({"3": {"1": 14, "12": 2}})
        assert not state.is_returning
        assert state.is_docked
        assert state.dock_activity == 2

    def test_returning_via_dock_sub_state_only(self) -> None:
        """dock_sub_state=2 alone is NOT enough — both field 3.7 AND 3.10 required."""
        state = NarwalState()
        # Only dock_sub_state=2 without field 3.7 — should NOT be returning
        # (single stale field causes false positives during normal cleaning)
        state.update_from_base_status({"3": {"1": 4, "10": 2}})
        assert not state.is_returning

    def test_not_returning_when_standby_with_dock_sub_state(self) -> None:
        """STANDBY with dock_sub_state=2 means docked, not returning."""
        state = NarwalState()
        state.update_from_base_status({"3": {"1": 1, "10": 2}})
        assert not state.is_returning

    def test_not_returning_when_cleaning_without_field7(self) -> None:
        """Cleaning without field 3.7 is NOT returning (just cleaning)."""
        state = NarwalState()
        state.update_from_base_status({"3": {"1": 4}})
        assert state.is_cleaning
        assert not state.is_returning

    def test_unknown_working_status_value(self) -> None:
        """Unknown status values should fall back to UNKNOWN."""
        state = NarwalState()
        state.update_from_base_status({"3": {"1": 255}})
        assert state.working_status == WorkingStatus.UNKNOWN


def _float_to_uint32(f: float) -> int:
    """Encode a float as the uint32 bit pattern (for protobuf simulation)."""
    return struct.unpack("I", struct.pack("f", f))[0]


class TestMapData:
    """Tests for MapData.from_response()."""

    def test_basic_map_parsing(self) -> None:
        decoded = {"2": {
            "3": 60,
            "4": 341,
            "5": 494,
            "12": [{"1": 3, "2": 0, "3": b"Kitchen"}],
            "17": b"\x78\x01" + b"\x00" * 20,
            "33": 944,
            "34": 1740000000,
        }}
        m = MapData.from_response(decoded)
        assert m.width == 341
        assert m.height == 494
        assert m.resolution == 60
        assert len(m.rooms) == 1
        assert m.rooms[0].name == "Kitchen"
        assert m.area == 944

    def test_dock_position_from_field8_uint32(self) -> None:
        """Dock parsed from field 8 (dm coords as uint32, same as display_map field 5)."""
        decoded = {"2": {
            "3": 60,
            "4": 341,
            "5": 494,
            "6": {"1": -341, "2": 152, "3": -280, "4": 60},
            "8": {"1": {"1": _float_to_uint32(-8.0188), "2": _float_to_uint32(0.221)}, "2": _float_to_uint32(0.036)},
            "17": b"",
        }}
        m = MapData.from_response(decoded)
        # factor 1.0: -8.0188 - (-280) = 271.98, 0.221 - (-341) = 341.22
        assert m.dock_x is not None
        assert m.dock_y is not None
        assert abs(m.dock_x - 272.0) < 1.0
        assert abs(m.dock_y - 341.2) < 1.0

    def test_dock_position_from_field8_float(self) -> None:
        """bbp may return fixed32 fields as Python floats directly."""
        decoded = {"2": {
            "3": 60,
            "4": 341,
            "5": 494,
            "6": {"1": -341, "3": -280},
            "8": {"1": {"1": -8.0188, "2": 0.221}, "2": 0.036},
            "17": b"",
        }}
        m = MapData.from_response(decoded)
        # factor 1.0: -8.0188 - (-280) = 271.98, 0.221 - (-341) = 341.22
        assert m.dock_x is not None
        assert m.dock_y is not None
        assert abs(m.dock_x - 272.0) < 1.0
        assert abs(m.dock_y - 341.2) < 1.0

    def test_dock_position_missing_field8(self) -> None:
        """No dock position when field 8 is missing."""
        decoded = {"2": {
            "3": 60,
            "4": 341,
            "5": 494,
            "6": {"1": -341, "3": -280},
            "17": b"",
        }}
        m = MapData.from_response(decoded)
        assert m.dock_x is None
        assert m.dock_y is None

    def test_dock_position_zero_resolution(self) -> None:
        """No dock position when resolution is zero."""
        decoded = {"2": {
            "3": 0,
            "4": 341,
            "5": 494,
            "8": {"1": {"1": -8.0, "2": 0.2}, "2": 0.0},
            "17": b"",
        }}
        m = MapData.from_response(decoded)
        assert m.dock_x is None
        assert m.dock_y is None

    def test_empty_response(self) -> None:
        m = MapData.from_response({})
        assert m.width == 0
        assert m.dock_x is None

    def test_obstacles_from_field32(self) -> None:
        """MapData.from_response includes obstacles parsed from field 32."""
        decoded = {"2": {
            "3": 60,
            "4": 341,
            "5": 494,
            "6": {"1": -341, "3": -280},
            "17": b"",
            "32": {
                "1": [
                    {
                        "1": 1,
                        "2": 14,
                        "3": {"1": {"1": _float_to_uint32(-110.5), "2": _float_to_uint32(-129.5)}, "2": _float_to_uint32(11.0), "3": _float_to_uint32(41.0)},
                        "4": _float_to_uint32(180.0),
                    },
                ],
            },
        }}
        m = MapData.from_response(decoded)
        assert len(m.obstacles) == 1
        obs = m.obstacles[0]
        assert obs.id == 1
        assert obs.type_id == 14
        assert obs.display_name == "Sofa"
        assert abs(obs.center_x - (-110.5)) < 0.5
        assert abs(obs.center_y - (-129.5)) < 0.5
        assert abs(obs.width - 11.0) < 0.5
        assert abs(obs.height - 41.0) < 0.5

    def test_obstacles_empty_when_no_field32(self) -> None:
        """MapData.from_response returns empty obstacles when field 32 is missing."""
        decoded = {"2": {"3": 60, "4": 10, "5": 10, "17": b""}}
        m = MapData.from_response(decoded)
        assert m.obstacles == []


class TestObstacleInfo:
    """Tests for ObstacleInfo dataclass."""

    def test_display_name_known_type(self) -> None:
        """ObstacleInfo with type_id=14 has display_name 'Sofa'."""
        obs = ObstacleInfo(id=1, type_id=14)
        assert obs.display_name == "Sofa"

    def test_display_name_unknown_type(self) -> None:
        """ObstacleInfo with unknown type_id=99 has display_name 'Object 99'."""
        obs = ObstacleInfo(id=1, type_id=99)
        assert obs.display_name == "Object 99"

    def test_display_name_all_known_types(self) -> None:
        """All known type IDs have correct display names."""
        expected = {2: "Double Bed", 4: "Dining Table", 6: "Tea Table", 14: "Sofa", 28: "Toilet"}
        for type_id, name in expected.items():
            obs = ObstacleInfo(id=1, type_id=type_id)
            assert obs.display_name == name

    def test_to_grid_coords(self) -> None:
        """to_grid_coords subtracts origin correctly."""
        obs = ObstacleInfo(id=1, type_id=14, center_x=-110.5, center_y=-129.5)
        gx, gy = obs.to_grid_coords(origin_x=-280, origin_y=-341)
        assert abs(gx - 169.5) < 0.01
        assert abs(gy - 211.5) < 0.01


class TestParseObstacles:
    """Tests for _parse_obstacles function."""

    def test_parse_obstacles_list(self) -> None:
        """_parse_obstacles with bbp-decoded field 32 data returns correct list."""
        field32 = {
            "1": [
                {
                    "1": 1,
                    "2": 14,
                    "3": {"1": {"1": _float_to_uint32(-110.5), "2": _float_to_uint32(-129.5)}, "2": _float_to_uint32(11.0), "3": _float_to_uint32(41.0)},
                    "4": _float_to_uint32(180.0),
                },
                {
                    "1": 4,
                    "2": 2,
                    "3": {"1": {"1": _float_to_uint32(10.0), "2": _float_to_uint32(95.5)}, "2": _float_to_uint32(36.0), "3": _float_to_uint32(29.0)},
                    "4": _float_to_uint32(180.0),
                },
            ],
        }
        obstacles = _parse_obstacles(field32)
        assert len(obstacles) == 2
        assert obstacles[0].id == 1
        assert obstacles[0].type_id == 14
        assert obstacles[0].display_name == "Sofa"
        assert abs(obstacles[0].center_x - (-110.5)) < 0.5
        assert obstacles[1].id == 4
        assert obstacles[1].type_id == 2
        assert obstacles[1].display_name == "Double Bed"

    def test_parse_obstacles_empty_field32(self) -> None:
        """_parse_obstacles handles missing/empty field 32 gracefully."""
        assert _parse_obstacles({}) == []
        assert _parse_obstacles({"1": []}) == []

    def test_parse_obstacles_single_item_dict(self) -> None:
        """_parse_obstacles handles single item (dict not list) in field 32.1."""
        field32 = {
            "1": {
                "1": 13,
                "2": 4,
                "3": {"1": {"1": _float_to_uint32(-154.0), "2": _float_to_uint32(-55.5)}, "2": _float_to_uint32(13.0), "3": _float_to_uint32(20.0)},
                "4": _float_to_uint32(90.0),
            },
        }
        obstacles = _parse_obstacles(field32)
        assert len(obstacles) == 1
        assert obstacles[0].id == 13
        assert obstacles[0].type_id == 4
        assert obstacles[0].display_name == "Dining Table"

    def test_parse_obstacles_float32_conversion(self) -> None:
        """float32 conversion works for coordinate values (uint32 bit patterns)."""
        # Use known value: -110.5 as uint32 = struct.unpack('I', struct.pack('f', -110.5))[0]
        field32 = {
            "1": {
                "1": 1,
                "2": 14,
                "3": {"1": {"1": _float_to_uint32(-110.5), "2": _float_to_uint32(-129.5)}, "2": _float_to_uint32(11.0), "3": _float_to_uint32(41.0)},
                "4": _float_to_uint32(180.0),
            },
        }
        obstacles = _parse_obstacles(field32)
        assert len(obstacles) == 1
        assert abs(obstacles[0].center_x - (-110.5)) < 0.1
        assert abs(obstacles[0].center_y - (-129.5)) < 0.1
        assert abs(obstacles[0].width - 11.0) < 0.1
        assert abs(obstacles[0].height - 41.0) < 0.1
        assert abs(obstacles[0].angle - 180.0) < 0.1

    def test_parse_obstacles_skips_bad_items(self) -> None:
        """_parse_obstacles skips non-dict items without crashing."""
        field32 = {
            "1": [
                "not a dict",
                42,
                {"1": 1, "2": 28, "3": {"1": {"1": 0.0, "2": 0.0}}},
            ],
        }
        obstacles = _parse_obstacles(field32)
        assert len(obstacles) == 1
        assert obstacles[0].type_id == 28


class TestVisionObstacleInfo:
    """Tests for VisionObstacleInfo dataclass."""

    def test_display_name_cable(self) -> None:
        """VisionObstacleInfo with label=1 has display_name 'Cable'."""
        obs = VisionObstacleInfo(id=1, label=1, center_x=10.0, center_y=20.0)
        assert obs.display_name == "Cable"

    def test_display_name_floor_mirror(self) -> None:
        """label=4 is 'Floor Mirror' (verified against Narwal app)."""
        obs = VisionObstacleInfo(id=1, label=4)
        assert obs.display_name == "Floor Mirror"

    def test_display_name_unknown_label(self) -> None:
        """VisionObstacleInfo with unknown label=99 falls back to 'Unknown'."""
        obs = VisionObstacleInfo(id=2, label=99)
        assert obs.display_name == "Unknown"

    def test_display_name_type_name_override(self) -> None:
        """type_name from robot overrides TYPE_NAMES lookup."""
        obs = VisionObstacleInfo(id=1, label=5, type_name="Custom Name")
        assert obs.display_name == "Custom Name"

    def test_type_names_confirmed_entries(self) -> None:
        """TYPE_NAMES has entries for confirmed vision types."""
        assert 1 in VisionObstacleInfo.TYPE_NAMES  # Cable
        assert 4 in VisionObstacleInfo.TYPE_NAMES  # Floor Mirror

    def test_category_hazard(self) -> None:
        """label=3 (Obstacle) is in hazard category."""
        obs = VisionObstacleInfo(id=1, label=3)
        assert obs.category == "hazard"

    def test_category_clothing_shoes(self) -> None:
        """label=2 (Shoes) is in clothing category."""
        obs = VisionObstacleInfo(id=1, label=2)
        assert obs.category == "clothing"

    def test_category_misc_fallback(self) -> None:
        """Unmapped labels fall back to misc category."""
        obs = VisionObstacleInfo(id=1, label=4)
        assert obs.category == "misc"

    def test_category_unknown_label(self) -> None:
        """Unknown labels fall back to misc category."""
        obs = VisionObstacleInfo(id=1, label=99)
        assert obs.category == "misc"

    def test_category_misc_cable(self) -> None:
        """label=1 (Cable) is in misc category."""
        obs = VisionObstacleInfo(id=1, label=1)
        assert obs.category == "misc"

    def test_category_misc_unknown_label(self) -> None:
        """Unknown label defaults to misc category."""
        obs = VisionObstacleInfo(id=1, label=99)
        assert obs.category == "misc"

    def test_to_grid_coords(self) -> None:
        """to_grid_coords subtracts origin correctly."""
        obs = VisionObstacleInfo(id=1, label=5, center_x=-10.0, center_y=-20.0)
        gx, gy = obs.to_grid_coords(origin_x=-280, origin_y=-341)
        assert abs(gx - 270.0) < 0.01
        assert abs(gy - 321.0) < 0.01

    def test_to_grid_coords_zero_origin(self) -> None:
        """to_grid_coords with zero origin returns center coords directly."""
        obs = VisionObstacleInfo(id=1, label=1, center_x=50.0, center_y=75.0)
        gx, gy = obs.to_grid_coords(origin_x=0, origin_y=0)
        assert abs(gx - 50.0) < 0.01
        assert abs(gy - 75.0) < 0.01


class TestParseVisionObstacles:
    """Tests for _parse_vision_obstacles function."""

    def test_parse_field9_basic(self) -> None:
        """_parse_vision_obstacles parses field 9 items from display_map."""
        # Field 9 schema: {1: type_id, 2: detection_seq, 3: unknown, 4: constant, 5: constant}
        field9 = [
            {"1": 1, "2": 101, "3": 1, "4": 1, "5": 2},  # Cable, seq=101
            {"1": 4, "2": 102, "3": 2, "4": 1, "5": 2},  # Floor Mirror, seq=102
        ]
        decoded = {"9": field9}
        obstacles = _parse_vision_obstacles(decoded)
        assert len(obstacles) == 2
        assert obstacles[0].label == 1
        assert obstacles[0].display_name == "Cable"
        assert obstacles[0].id == 101
        assert obstacles[1].label == 4
        assert obstacles[1].display_name == "Floor Mirror"
        assert obstacles[1].id == 102

    def test_parse_field9_type_id_zero_unknown(self) -> None:
        """type_id=0 (missing field 1) is handled as label=0, display_name='Obstacle 0'."""
        # When type_id=0, bbp omits field 1 entirely
        field9 = [
            {"2": 103, "3": 1, "4": 1, "5": 2},  # type_id missing (=0)
        ]
        decoded = {"9": field9}
        obstacles = _parse_vision_obstacles(decoded)
        assert len(obstacles) == 1
        assert obstacles[0].label == 0
        assert obstacles[0].id == 103

    def test_parse_field9_single_item_dict(self) -> None:
        """Handles single item returned as dict instead of list."""
        decoded = {"9": {"1": 2, "2": 200, "3": 1, "4": 1, "5": 2}}
        obstacles = _parse_vision_obstacles(decoded)
        assert len(obstacles) == 1
        assert obstacles[0].label == 2

    def test_parse_empty_field9(self) -> None:
        """Returns empty list when field 9 is absent."""
        obstacles = _parse_vision_obstacles({})
        assert obstacles == []

    def test_parse_empty_list(self) -> None:
        """Returns empty list when field 9 is empty list."""
        obstacles = _parse_vision_obstacles({"9": []})
        assert obstacles == []

    def test_parse_malformed_data(self) -> None:
        """Returns empty list for malformed/non-dict data."""
        obstacles = _parse_vision_obstacles({"9": "not a list"})
        assert obstacles == []

    def test_parse_skips_non_dict_items(self) -> None:
        """Skips non-dict items in field 9 list."""
        decoded = {"9": [
            "bad",
            42,
            {"1": 3, "2": 104},
        ]}
        obstacles = _parse_vision_obstacles(decoded)
        assert len(obstacles) == 1
        assert obstacles[0].label == 3

    def test_parse_deduplicates_by_id(self) -> None:
        """Deduplicates detections by detection_seq (used as id)."""
        decoded = {"9": [
            {"1": 1, "2": 101},
            {"1": 1, "2": 101},  # duplicate
            {"1": 2, "2": 102},
        ]}
        obstacles = _parse_vision_obstacles(decoded)
        assert len(obstacles) == 2

    def test_parse_field12_coordinates(self) -> None:
        """Field 12 trail segments provide coordinates for field 9 detections."""
        # Encode two float32 values: -10.5, 20.3
        x_hex = struct.pack("<2f", -10.5, 20.3).hex()
        y_hex = struct.pack("<2f", 5.0, -15.7).hex()
        decoded = {
            "9": [{"1": 1, "2": 42}],  # Cable, seq=42
            "12": [{
                "1": {
                    "1": {"_hex": x_hex, "_len": 8},
                    "2": {"_hex": y_hex, "_len": 8},
                },
                "2": [{"1": 1, "2": 42, "3": 1, "4": 1, "5": 2}],
            }],
        }
        obstacles = _parse_vision_obstacles(decoded)
        assert len(obstacles) == 1
        # Last coordinate in segment: (20.3, -15.7)
        assert abs(obstacles[0].center_x - 20.3) < 0.1
        assert abs(obstacles[0].center_y - (-15.7)) < 0.1

    def test_parse_field12_only_no_field9(self) -> None:
        """When field 9 is absent, obstacles still extracted from field 12."""
        x_hex = struct.pack("<1f", 7.5).hex()
        y_hex = struct.pack("<1f", -3.2).hex()
        decoded = {
            "12": [{
                "1": {
                    "1": {"_hex": x_hex, "_len": 4},
                    "2": {"_hex": y_hex, "_len": 4},
                },
                "2": {"1": 4, "2": 99},  # single detection as dict
            }],
        }
        obstacles = _parse_vision_obstacles(decoded)
        assert len(obstacles) == 1
        assert obstacles[0].label == 4
        assert obstacles[0].display_name == "Floor Mirror"
        assert abs(obstacles[0].center_x - 7.5) < 0.1
        assert abs(obstacles[0].center_y - (-3.2)) < 0.1

    def test_parse_field12_multiple_segments(self) -> None:
        """Multiple field 12 segments each contribute detection coordinates."""
        seg1_x = struct.pack("<1f", 1.0).hex()
        seg1_y = struct.pack("<1f", 2.0).hex()
        seg2_x = struct.pack("<1f", 10.0).hex()
        seg2_y = struct.pack("<1f", 20.0).hex()
        decoded = {
            "9": [
                {"1": 1, "2": 50},  # Cable at seg1
                {"1": 3, "2": 51},  # Pet Waste at seg2
            ],
            "12": [
                {
                    "1": {"1": {"_hex": seg1_x, "_len": 4}, "2": {"_hex": seg1_y, "_len": 4}},
                    "2": [{"1": 1, "2": 50}],
                },
                {
                    "1": {"1": {"_hex": seg2_x, "_len": 4}, "2": {"_hex": seg2_y, "_len": 4}},
                    "2": [{"1": 3, "2": 51}],
                },
            ],
        }
        obstacles = _parse_vision_obstacles(decoded)
        assert len(obstacles) == 2
        cable = next(o for o in obstacles if o.label == 1)
        pet = next(o for o in obstacles if o.label == 3)
        assert abs(cable.center_x - 1.0) < 0.01
        assert abs(cable.center_y - 2.0) < 0.01
        assert abs(pet.center_x - 10.0) < 0.01
        assert abs(pet.center_y - 20.0) < 0.01

    def test_parse_field12_no_coordinates_falls_back_zero(self) -> None:
        """Detections without field 12 match get (0,0) coordinates."""
        decoded = {
            "9": [{"1": 2, "2": 77}],
            # No field 12
        }
        obstacles = _parse_vision_obstacles(decoded)
        assert len(obstacles) == 1
        assert obstacles[0].center_x == 0.0
        assert obstacles[0].center_y == 0.0


class TestDecodeFloat32Array:
    """Tests for _decode_float32_array helper."""

    def test_decode_basic(self) -> None:
        """Decodes hex-encoded float32 array."""
        values = [1.5, -2.5, 3.0]
        hex_str = struct.pack("<3f", *values).hex()
        result = _decode_float32_array({"_hex": hex_str, "_len": 12})
        assert len(result) == 3
        for a, b in zip(result, values):
            assert abs(a - b) < 0.001

    def test_decode_empty(self) -> None:
        """Returns empty list for empty hex."""
        assert _decode_float32_array({"_hex": "", "_len": 0}) == []
        assert _decode_float32_array({}) == []

    def test_decode_raw_bytes(self) -> None:
        """Decodes raw bytes (common bbp output format)."""
        values = [1.5, -2.5, 3.0]
        raw = struct.pack("<3f", *values)
        result = _decode_float32_array(raw)
        assert len(result) == 3
        for a, b in zip(result, values):
            assert abs(a - b) < 0.001

    def test_decode_empty_bytes(self) -> None:
        """Returns empty list for empty bytes."""
        assert _decode_float32_array(b"") == []

    def test_decode_invalid_hex(self) -> None:
        """Returns empty list for invalid hex string."""
        assert _decode_float32_array({"_hex": "zzzz"}) == []

    def test_decode_non_dict_non_bytes(self) -> None:
        """Returns empty list for unsupported types."""
        assert _decode_float32_array(42) == []
        assert _decode_float32_array("not bytes") == []


class TestNarwalStateVisionObstacles:
    """Tests for NarwalState.vision_obstacles field."""

    def test_default_vision_obstacles_empty(self) -> None:
        """NarwalState.vision_obstacles defaults to empty list."""
        state = NarwalState()
        assert state.vision_obstacles == []

    def test_vision_obstacles_is_list(self) -> None:
        """vision_obstacles is a mutable list."""
        state = NarwalState()
        obs = VisionObstacleInfo(id=1, label=5)
        state.vision_obstacles.append(obs)
        assert len(state.vision_obstacles) == 1
