"""Tests for narwal_client room-specific clean payload and start_rooms."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from narwal_client.client import NarwalClient
from narwal_client.const import CommandResult
from narwal_client.models import CommandResponse


class TestBuildRoomCleanPayload:
    """Tests for _build_room_clean_payload protobuf encoding."""

    def test_single_room_encodes_room_id_and_params(self) -> None:
        """Single room has roomId + clean params in field 1.2."""
        import blackboxprotobuf

        client = NarwalClient("127.0.0.1")
        payload = client._build_room_clean_payload([11])
        decoded, _ = blackboxprotobuf.decode_message(payload)

        field1_2 = decoded["1"]["2"]
        # Single room: field 1.2.1 = roomId
        assert field1_2["1"] == 11
        # Per-room clean params must be present (robot ignores bare roomId)
        assert field1_2["2"] == 2, "cleanMode should be 2 (sweep+mop)"
        assert field1_2["3"] == 1, "cleanTimes should be 1"
        assert field1_2["6"] == 3, "sweepMode should be 3 (max suction)"
        assert field1_2["7"] == 2, "mopMode should be 2 (wet)"

    def test_multiple_rooms_encodes_all(self) -> None:
        """Multiple rooms encode as repeated messages in field 1.2."""
        import blackboxprotobuf

        client = NarwalClient("127.0.0.1")
        payload = client._build_room_clean_payload([11, 9])
        decoded, _ = blackboxprotobuf.decode_message(payload)

        field1_2 = decoded["1"]["2"]
        assert isinstance(field1_2, list), "Multiple rooms should be a list"
        room_ids = [entry["1"] for entry in field1_2]
        assert 11 in room_ids
        assert 9 in room_ids
        # Each entry has clean params
        for entry in field1_2:
            assert entry["2"] == 2, "cleanMode"
            assert entry["6"] == 3, "sweepMode"

    def test_preserves_global_clean_settings(self) -> None:
        """Payload preserves suction=3, mop=2, passes=1 in field 1.5."""
        import blackboxprotobuf

        client = NarwalClient("127.0.0.1")
        payload = client._build_room_clean_payload([11])
        decoded, _ = blackboxprotobuf.decode_message(payload)

        settings = decoded["1"]["5"]["1"]
        assert settings["1"] == 3, "Suction should be 3 (max)"
        assert settings["2"] == 2, "Mop humidity should be 2 (wet)"
        assert settings["3"] == 1, "Passes should be 1 (single)"

    def test_empty_room_ids_returns_default(self) -> None:
        """Empty room list returns the default whole-house payload."""
        client = NarwalClient("127.0.0.1")
        payload = client._build_room_clean_payload([])
        assert payload == client._DEFAULT_CLEAN_PAYLOAD

    def test_room_payload_differs_from_default(self) -> None:
        """Room-specific payload is different from whole-house default."""
        client = NarwalClient("127.0.0.1")
        room_payload = client._build_room_clean_payload([11])
        assert room_payload != client._DEFAULT_CLEAN_PAYLOAD
        assert len(room_payload) > 0


class TestStartRooms:
    """Tests for start_rooms async method."""

    def test_empty_rooms_calls_start(self) -> None:
        """start_rooms([]) falls back to whole-house start()."""
        client = NarwalClient("127.0.0.1")
        client._ws = AsyncMock()  # fake connected state
        client._connected = True

        with patch.object(client, "start", new_callable=AsyncMock) as mock_start:
            mock_start.return_value = AsyncMock()
            asyncio.get_event_loop().run_until_complete(client.start_rooms([]))
            mock_start.assert_awaited_once()

    def test_room_ids_sends_room_payload(self) -> None:
        """start_rooms with IDs sends room-specific payload via send_command."""
        client = NarwalClient("127.0.0.1")
        client._ws = AsyncMock()
        client._connected = True

        success = CommandResponse(result_code=CommandResult.SUCCESS)
        with patch.object(
            client, "send_command", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = success
            asyncio.get_event_loop().run_until_complete(client.start_rooms([11, 9]))
            mock_send.assert_awaited_once()
            payload_arg = mock_send.await_args.kwargs.get("payload")
            assert payload_arg is not None
            assert payload_arg != client._DEFAULT_CLEAN_PAYLOAD


class TestStartRoomsV2Fallback:
    """Tests for the legacy→v2 schema fallback in start_rooms (issue #37)."""

    def _connected_client(self) -> NarwalClient:
        client = NarwalClient("127.0.0.1")
        client._ws = AsyncMock()
        client._connected = True
        return client

    def test_success_on_legacy_does_not_retry(self) -> None:
        """If the legacy room payload is accepted, no v2 retry happens."""
        client = self._connected_client()
        success = CommandResponse(result_code=CommandResult.SUCCESS)

        with patch.object(
            client, "send_command", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = success
            result = asyncio.get_event_loop().run_until_complete(
                client.start_rooms([5])
            )

        assert result is success
        mock_send.assert_awaited_once()

    def test_not_applicable_triggers_v2_retry(self) -> None:
        """NOT_APPLICABLE on the legacy payload triggers a v2 retry with
        the same caller-supplied room IDs (not all rooms)."""
        client = self._connected_client()
        not_applicable = CommandResponse(result_code=CommandResult.NOT_APPLICABLE)
        success = CommandResponse(result_code=CommandResult.SUCCESS)

        with patch.object(
            client, "send_command", new_callable=AsyncMock
        ) as mock_send:
            mock_send.side_effect = [not_applicable, success]
            result = asyncio.get_event_loop().run_until_complete(
                client.start_rooms([5, 7])
            )

        assert mock_send.await_count == 2
        legacy_payload = mock_send.await_args_list[0].kwargs.get("payload")
        v2_payload = mock_send.await_args_list[1].kwargs.get("payload")
        assert legacy_payload != v2_payload
        # v2 payload must encode exactly the requested rooms, not all rooms
        import blackboxprotobuf
        decoded, _ = blackboxprotobuf.decode_message(v2_payload)
        entries = decoded["1"]["2"]
        ids = [e["1"]["2"] for e in entries]
        assert ids == [5, 7]
        assert result is success

    def test_conflict_does_not_trigger_retry(self) -> None:
        """A CONFLICT response (robot busy) surfaces as-is — no retry."""
        client = self._connected_client()
        conflict = CommandResponse(result_code=CommandResult.CONFLICT)

        with patch.object(
            client, "send_command", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = conflict
            result = asyncio.get_event_loop().run_until_complete(
                client.start_rooms([5])
            )

        mock_send.assert_awaited_once()
        assert result.result_code == CommandResult.CONFLICT

    def test_force_v2_skips_legacy_attempt(self) -> None:
        """force_v2=True for firmwares that ack legacy but ignore rooms."""
        client = self._connected_client()
        success = CommandResponse(result_code=CommandResult.SUCCESS)

        with patch.object(
            client, "send_command", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = success
            result = asyncio.get_event_loop().run_until_complete(
                client.start_rooms([5, 7], force_v2=True)
            )

        mock_send.assert_awaited_once()
        # Payload must be the v2 schema (single call only)
        import blackboxprotobuf
        payload = mock_send.await_args.kwargs.get("payload")
        decoded, _ = blackboxprotobuf.decode_message(payload)
        entries = decoded["1"]["2"]
        ids = [e["1"]["2"] for e in entries]
        assert ids == [5, 7]
        assert result is success
