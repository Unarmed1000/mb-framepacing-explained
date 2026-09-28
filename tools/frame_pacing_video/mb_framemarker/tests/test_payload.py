# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Mana Battery ApS

"""The payload wire format (doc/marker-format.md): layout, round trips and rejections, as the C# library's PayloadTests; and the
sequence id."""

import unittest
import uuid
from datetime import UTC, datetime, timedelta

from .. import (
    MAX_ENCODED_PAYLOAD_BYTE_COUNT,
    PAYLOAD_BYTE_COUNT,
    SEQUENCE_ID_BYTE_COUNT,
    START_PAYLOAD_BYTE_COUNT,
    SYNC_PAYLOAD_BYTE_COUNT,
    MarkerKind,
    Payload,
    SequenceId,
    StartMetadata,
    encode_payload,
    seconds_to_ticks,
    to_date_time_ticks,
    try_decode_payload,
)

U64_MAX = 0xFFFF_FFFF_FFFF_FFFF
I64_MAX = 0x7FFF_FFFF_FFFF_FFFF
I64_MIN = -0x8000_0000_0000_0000
U32_MAX = 0xFFFF_FFFF


class PayloadTests(unittest.TestCase):
    def test_sizes(self) -> None:
        self.assertEqual(PAYLOAD_BYTE_COUNT, 48)
        self.assertEqual(SEQUENCE_ID_BYTE_COUNT, 16)
        self.assertEqual(START_PAYLOAD_BYTE_COUNT, 72)
        self.assertEqual(MAX_ENCODED_PAYLOAD_BYTE_COUNT, START_PAYLOAD_BYTE_COUNT)
        self.assertEqual(SYNC_PAYLOAD_BYTE_COUNT, 12)

    def test_encode_produces_the_documented_little_endian_layout(self) -> None:
        payload = Payload(
            0x0102030405060708,
            0x1112131415161718,
            0x21222324,
            MarkerKind.SEQUENCE_END,
            0x3132333435363738,
            0x41424344,
            0x5152535455565758,
            0x61626364,
        )
        data = encode_payload(payload)
        expected = (
            b"MF\x01\x02"
            + bytes([8, 7, 6, 5, 4, 3, 2, 1])
            + bytes([0x18, 0x17, 0x16, 0x15, 0x14, 0x13, 0x12, 0x11])
            + bytes([0x24, 0x23, 0x22, 0x21])
            + bytes([0x38, 0x37, 0x36, 0x35, 0x34, 0x33, 0x32, 0x31])
            + bytes([0x44, 0x43, 0x42, 0x41])
            + bytes([0x58, 0x57, 0x56, 0x55, 0x54, 0x53, 0x52, 0x51])
            + bytes([0x64, 0x63, 0x62, 0x61])
        )
        self.assertEqual(data, expected)
        self.assertEqual(len(data), PAYLOAD_BYTE_COUNT)

    def test_start_marker_layout(self) -> None:
        payload = Payload(1, 2, 3, MarkerKind.SEQUENCE_START, 4, 5, 6, 7)
        sequence_id = SequenceId(bytes(range(0xA0, 0xB0)))
        data = encode_payload(payload, StartMetadata(0x0102030405060708, sequence_id))
        self.assertEqual(len(data), START_PAYLOAD_BYTE_COUNT)
        # The same 48 byte header as the other kinds, then the start time and the sequence id
        end_header = encode_payload(payload.with_kind(MarkerKind.SEQUENCE_END))
        self.assertEqual(data[:3] + data[4:PAYLOAD_BYTE_COUNT], end_header[:3] + end_header[4:])
        self.assertEqual(data[3], MarkerKind.SEQUENCE_START)
        self.assertEqual(data[36:44], bytes([6, 0, 0, 0, 0, 0, 0, 0]))
        self.assertEqual(data[44:48], bytes([7, 0, 0, 0]))
        self.assertEqual(data[48:56], bytes([8, 7, 6, 5, 4, 3, 2, 1]))
        # The sequence id is stored as its bytes, in order
        self.assertEqual(data[56:72], bytes(range(0xA0, 0xB0)))

    def test_negative_ticks_are_stored_as_twos_complement(self) -> None:
        self.assertEqual(encode_payload(Payload(0, -1))[12:20], b"\xff" * 8)
        self.assertEqual(encode_payload(Payload(0, 0, 0, MarkerKind.FRAME, -2))[24:32], b"\xfe" + (b"\xff" * 7))
        self.assertEqual(encode_payload(Payload(0, 0, 0, MarkerKind.FRAME, cpu_start_ticks=-3))[36:44], b"\xfd" + (b"\xff" * 7))

    def test_the_optional_fields_default_to_unknown(self) -> None:
        payload = Payload(1, 2, 3, MarkerKind.SEQUENCE_END)
        self.assertEqual(
            (payload.intended_display_ticks, payload.target_frame_ticks, payload.cpu_start_ticks, payload.cpu_busy_ticks),
            (0, 0, 0, 0),
        )
        self.assertEqual(encode_payload(payload)[24:], bytes(24))
        self.assertEqual(StartMetadata(), StartMetadata(0, SequenceId(bytes(16))))

    def test_round_trips(self) -> None:
        for payload in (
            Payload(0, 0, 0),
            Payload(1, 166_667, 7),
            Payload(U64_MAX, I64_MAX, U32_MAX, MarkerKind.FRAME, I64_MAX, U32_MAX, I64_MAX, U32_MAX),
            Payload(7, I64_MIN, 1, MarkerKind.SEQUENCE_START, I64_MIN, 0, I64_MIN, 0),
            Payload(42, -1, 3, MarkerKind.SEQUENCE_END, -1, 333_333, -1, 1),
            Payload(5, 6, 7, target_frame_ticks=166_667),
            Payload(5, 6, 7, cpu_start_ticks=123_456_789_012),
            Payload(5, 6, 7, cpu_busy_ticks=81_234),
            Payload(5, 6, 7, cpu_busy_ticks=U32_MAX),
            Payload(5, 6, 7, cpu_start_ticks=123_456_789_012, cpu_busy_ticks=500_000),
        ):
            with self.subTest(payload):
                decoded = try_decode_payload(encode_payload(payload))
                self.assertIsNotNone(decoded)
                assert decoded is not None
                self.assertEqual(decoded[0], payload)

    def test_sync_marker_carries_only_the_frame_index(self) -> None:
        payload = Payload(0x0102030405060708, 123, 4, MarkerKind.SYNC, 5, 6, 7, 8)
        data = encode_payload(payload, StartMetadata(7, SequenceId.from_text("ignored")))
        self.assertEqual(data, b"MF\x01\x03" + bytes([8, 7, 6, 5, 4, 3, 2, 1]))
        self.assertEqual(len(data), SYNC_PAYLOAD_BYTE_COUNT)
        self.assertEqual(try_decode_payload(data), (Payload(payload.frame_index, 0, 0, MarkerKind.SYNC), None))

        # Exactly 12 bytes: longer (for example a full header with kind 3) or shorter is rejected
        self.assertIsNone(try_decode_payload(data + b"\x00"))
        self.assertIsNone(try_decode_payload(data[:-1]))
        self.assertIsNone(try_decode_payload(encode_payload(Payload(1, 2, 3))[:3] + b"\x03" + bytes(PAYLOAD_BYTE_COUNT - 4)))
        # A 12 byte payload of another kind is too short
        self.assertIsNone(try_decode_payload(b"MF\x01\x00" + bytes(8)))

    def test_sync_round_trips_and_range(self) -> None:
        for frame_index in (0, 1, 42, U64_MAX):
            with self.subTest(frame_index):
                payload = Payload(frame_index, 0, 0, MarkerKind.SYNC)
                self.assertEqual(try_decode_payload(encode_payload(payload)), (payload, None))
        # Only the frame index is range checked: the other fields are not encoded
        self.assertEqual(
            len(encode_payload(Payload(0, I64_MAX + 1, U32_MAX + 1, MarkerKind.SYNC, I64_MIN - 1, -1, I64_MAX + 1, U32_MAX + 1))),
            SYNC_PAYLOAD_BYTE_COUNT,
        )
        for frame_index in (-1, U64_MAX + 1):
            with self.subTest(frame_index), self.assertRaises(ValueError):
                _ = encode_payload(Payload(frame_index, 0, 0, MarkerKind.SYNC))

    def test_start_metadata_round_trips(self) -> None:
        payload = Payload(10, 20, 30, MarkerKind.SEQUENCE_START, 40, 50, 60, 70)
        for metadata in (
            StartMetadata(638_000_000_000_000_000, SequenceId.from_text("benchmark-run-01")),
            StartMetadata(0, SequenceId.from_uuid(uuid.UUID("0f8fad5b-d9cb-469f-a165-70867728950e"))),
            StartMetadata(-1, SequenceId(bytes([0xFF]) * 16)),
            StartMetadata(I64_MAX, SequenceId()),
        ):
            with self.subTest(metadata):
                data = encode_payload(payload, metadata)
                self.assertEqual(len(data), START_PAYLOAD_BYTE_COUNT)
                self.assertEqual(try_decode_payload(data), (payload, metadata))

        # A start marker without metadata carries an unknown time and an empty sequence id; frame payloads ignore the metadata
        self.assertEqual(try_decode_payload(encode_payload(payload)), (payload, StartMetadata()))
        self.assertEqual(len(encode_payload(Payload(1, 2, 3), StartMetadata(5, SequenceId.from_text("x")))), PAYLOAD_BYTE_COUNT)

    def test_encode_rejects_out_of_range_fields(self) -> None:
        start = Payload(1, 2, 3, MarkerKind.SEQUENCE_START)
        for metadata in (StartMetadata(I64_MAX + 1), StartMetadata(I64_MIN - 1)):
            with self.subTest(metadata), self.assertRaises(ValueError):
                _ = encode_payload(start, metadata)
        for payload in (
            Payload(-1, 0),
            Payload(U64_MAX + 1, 0),
            Payload(0, I64_MAX + 1),
            Payload(0, 0, U32_MAX + 1),
            Payload(0, 0, 0, MarkerKind.FRAME, I64_MAX + 1),
            Payload(0, 0, 0, MarkerKind.FRAME, I64_MIN - 1),
            Payload(0, 0, 0, MarkerKind.FRAME, 0, -1),
            Payload(0, 0, 0, MarkerKind.FRAME, 0, U32_MAX + 1),
            Payload(0, 0, 0, MarkerKind.FRAME, 0, 0, I64_MAX + 1),
            Payload(0, 0, 0, MarkerKind.FRAME, 0, 0, I64_MIN - 1),
            Payload(0, 0, 0, MarkerKind.FRAME, cpu_busy_ticks=-1),
            Payload(0, 0, 0, MarkerKind.FRAME, cpu_busy_ticks=U32_MAX + 1),
            Payload(0, 0, 0, MarkerKind.SEQUENCE_START, cpu_busy_ticks=U32_MAX + 1),
            Payload(0, 0, 0, MarkerKind.SEQUENCE_END, cpu_busy_ticks=-1),
            Payload(0, 0, 0, MarkerKind.SEQUENCE_END, cpu_start_ticks=I64_MAX + 1),
        ):
            with self.subTest(payload), self.assertRaises(ValueError):
                _ = encode_payload(payload)

    def test_try_decode_rejects_bad_input(self) -> None:
        data = bytearray(encode_payload(Payload(1, 2)))
        self.assertIsNone(try_decode_payload(bytes(data[:-1])), "short: 47 bytes")
        self.assertIsNone(try_decode_payload(bytes(data[:36])), "an older 36 byte header")
        self.assertIsNone(try_decode_payload(bytes(data[:44])), "an older 44 byte header")
        self.assertIsNone(try_decode_payload(bytes(data) + b"\x00"), "long: 49 bytes")
        self.assertIsNone(try_decode_payload(bytes(data) + bytes(4)), "the older 52 byte header")
        data[0] = ord("X")
        self.assertIsNone(try_decode_payload(bytes(data)), "magic")
        data[0] = ord("M")
        data[2] = 2
        self.assertIsNone(try_decode_payload(bytes(data)), "format version")
        data[2] = 1
        data[3] = 4
        self.assertIsNone(try_decode_payload(bytes(data)), "kind")
        data[3] = 3
        self.assertIsNone(try_decode_payload(bytes(data)), "a sync kind needs exactly 12 bytes")
        data[3] = 0
        self.assertIsNotNone(try_decode_payload(bytes(data)))

        # A start marker must be exactly 72 bytes: without its metadata, truncated or longer is rejected
        start = encode_payload(Payload(1, 2, 3, MarkerKind.SEQUENCE_START), StartMetadata(5, SequenceId.from_text("run")))
        self.assertEqual(len(start), 72)
        self.assertIsNotNone(try_decode_payload(start))
        for length in (PAYLOAD_BYTE_COUNT, PAYLOAD_BYTE_COUNT + 9, START_PAYLOAD_BYTE_COUNT - 1):
            with self.subTest(length):
                self.assertIsNone(try_decode_payload(start[:length]))
        self.assertIsNone(try_decode_payload(start + b"\x00"), "long: 73 bytes")
        older = start[:PAYLOAD_BYTE_COUNT] + bytes(4) + start[PAYLOAD_BYTE_COUNT:]
        self.assertIsNone(try_decode_payload(older), "the older 76 byte start marker")

    def test_ticks_match_date_time_and_time_span(self) -> None:
        time = datetime(2026, 1, 1, tzinfo=UTC)
        self.assertEqual(to_date_time_ticks(time), 639_028_224_000_000_000)
        self.assertEqual(to_date_time_ticks(time + timedelta(microseconds=1)), 639_028_224_000_000_010)
        self.assertEqual(seconds_to_ticks(1.5), 15_000_000)
        self.assertEqual(seconds_to_ticks(1.0 / 60), 166_667)


class SequenceIdTests(unittest.TestCase):
    def test_holds_exactly_16_bytes(self) -> None:
        self.assertEqual(SequenceId().data, bytes(16))
        self.assertTrue(SequenceId().is_empty)
        self.assertFalse(SequenceId(bytes(15) + b"\x01").is_empty)
        for length in (0, 15, 17):
            with self.subTest(length), self.assertRaises(ValueError):
                _ = SequenceId(bytes(length))

    def test_from_text_pads_with_zero_bytes(self) -> None:
        self.assertEqual(SequenceId.from_text("run 7").data, b"run 7" + bytes(11))
        self.assertEqual(SequenceId.from_text("~" * 16).data, b"~" * 16)
        self.assertEqual(SequenceId.from_text(" ").data, b" " + bytes(15))

    def test_from_text_rejects_anything_but_1_to_16_printable_ascii_characters(self) -> None:
        for text in ("", "x" * 17, "æ", "tab\there", "nul\x00", "del\x7f"):
            with self.subTest(text), self.assertRaises(ValueError):
                _ = SequenceId.from_text(text)

    def test_from_uuid_stores_the_bytes_in_the_order_of_the_text(self) -> None:
        value = uuid.UUID("0f8fad5b-d9cb-469f-a165-70867728950e")
        sequence_id = SequenceId.from_uuid(value)
        self.assertEqual(sequence_id.data, bytes.fromhex("0f8fad5bd9cb469fa16570867728950e"))
        self.assertEqual(str(sequence_id), "0f8fad5b-d9cb-469f-a165-70867728950e")

    def test_display_form(self) -> None:
        # Printable ASCII followed only by zero bytes shows as text, anything else in the 8-4-4-4-12 form
        self.assertEqual(str(SequenceId.from_text("benchmark-run-01")), "benchmark-run-01")
        self.assertEqual(str(SequenceId.from_text("run 7")), "run 7")
        self.assertEqual(str(SequenceId(b"ab\x00c" + bytes(12))), "61620063-0000-0000-0000-000000000000")
        self.assertEqual(str(SequenceId(b"\x00run" + bytes(12))), "0072756e-0000-0000-0000-000000000000")
        self.assertEqual(str(SequenceId()), "00000000-0000-0000-0000-000000000000")
        self.assertEqual(str(SequenceId(bytes([0xFF]) * 16)), "ffffffff-ffff-ffff-ffff-ffffffffffff")
        self.assertEqual(str(SequenceId(bytes(range(0xA0, 0xB0)))), "a0a1a2a3-a4a5-a6a7-a8a9-aaabacadaeaf")


if __name__ == "__main__":
    _ = unittest.main()
