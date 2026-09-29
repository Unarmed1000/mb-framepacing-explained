# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: BSD-3-Clause

"""The marker's data types, as in the C# library (MB.FrameMarker) and the C++ library (MB::FrameMarker).

Coordinates are pixels with the origin at the top-left corner, +x to the right and +y down. Every quad edge and every vertex lies on an
integer pixel edge.
"""

from dataclasses import dataclass, field, replace
from enum import IntEnum
from typing import Self
from uuid import UUID

SEQUENCE_ID_BYTE_COUNT = 16
"""A sequence id is 16 opaque bytes."""


class MarkerKind(IntEnum):
    """What a marker marks: a frame of a run, or the start or end of a run (a test sequence). SYNC is the small second marker for
    tearing checks and camera timing: it only carries the frame index."""

    FRAME = 0
    SEQUENCE_START = 1
    SEQUENCE_END = 2
    SYNC = 3


@dataclass(frozen=True, slots=True)
class Payload:
    """What a marker carries: the frame index (u64), the animation time in TimeSpan ticks (100 ns, i64), the run id (u32), the kind
    and, when the application paces its frames, the intended display time (i64 ticks on the frame pacer's steady clock, any epoch, the
    same clock for the whole run) and the target frame time (u32 ticks, 166_667 for 60 fps), then the CPU start time (i64 ticks on the
    same steady clock) and CPU busy (u32 ticks); 0 = unknown for all four. A sync marker only carries the frame index."""

    frame_index: int
    animation_ticks: int
    run_id: int = 0
    kind: MarkerKind = MarkerKind.FRAME
    intended_display_ticks: int = 0
    target_frame_ticks: int = 0
    cpu_start_ticks: int = 0
    """CPU start time: when the CPU started working on this frame (PresentMon's CPUStartTime), in ticks (100 ns) on the same steady clock
    as the intended display time. Anywhere inside a refresh; frames can overlap. 0 = unknown."""
    cpu_busy_ticks: int = 0
    """CPU busy: how long the CPU worked on this frame before presenting it (PresentMon's MsCPUBusy), from the CPU start time until
    Present is called, in ticks (100 ns, u32). The marker is drawn last, so the application measures it as it draws the marker. It does
    not include the GPU's work. May span several refreshes. 0 = unknown."""

    def with_kind(self, kind: MarkerKind) -> Self:
        return replace(self, kind=kind)


@dataclass(frozen=True, slots=True)
class SequenceId:
    """The start marker's sequence id: 16 opaque bytes that identify the capture sequence, any content as long as it is unique to it (a
    UUID's bytes, or a short text tag padded with zeros). All zero (the default) means no sequence id. str() shows it as text when it is
    printable ASCII, otherwise as a UUID's 8-4-4-4-12 hex form. Raises ValueError unless `data` is 16 bytes."""

    data: bytes = bytes(SEQUENCE_ID_BYTE_COUNT)

    def __post_init__(self) -> None:
        data = bytes(self.data)  # a bytearray or memoryview becomes immutable bytes
        if len(data) != SEQUENCE_ID_BYTE_COUNT:
            raise ValueError(f"a sequence id is {SEQUENCE_ID_BYTE_COUNT} bytes, not {len(data)}")
        object.__setattr__(self, "data", data)

    @property
    def is_empty(self) -> bool:
        """All zero: no sequence id."""
        return not any(self.data)

    @classmethod
    def from_uuid(cls, value: UUID) -> Self:
        """A UUID's bytes in the order its text shows them, so str() gives the same text as the UUID."""
        return cls(value.bytes)

    @classmethod
    def from_text(cls, text: str) -> Self:
        """A text tag of 1 to 16 printable ASCII characters, padded with zero bytes. Raises ValueError for any other text."""
        if not 0 < len(text) <= SEQUENCE_ID_BYTE_COUNT or not all(0x20 <= ord(character) <= 0x7E for character in text):
            raise ValueError(f"a sequence id text is 1 to {SEQUENCE_ID_BYTE_COUNT} printable ASCII characters: {text!r}")
        return cls(text.encode("ascii").ljust(SEQUENCE_ID_BYTE_COUNT, b"\x00"))

    def __str__(self) -> str:  # pyright: ignore[reportImplicitOverride]  (typing.override needs Python 3.12)
        """The text when the bytes are printable ASCII followed only by zero bytes, otherwise the 8-4-4-4-12 hex form."""
        text = self.data.rstrip(b"\x00")
        if text and all(0x20 <= byte <= 0x7E for byte in text):
            return text.decode("ascii")
        return str(UUID(bytes=self.data))


@dataclass(frozen=True, slots=True)
class StartMetadata:
    """What a start marker carries besides the payload: the start time in DateTime UTC ticks (0 = unknown) and the sequence id that
    identifies the capture sequence."""

    utc_ticks: int = 0
    sequence_id: SequenceId = SequenceId()


@dataclass(frozen=True, slots=True)
class Options:
    """The marker's size: pixels per module and the quiet zone around the symbol, in modules."""

    module_size_px: int = 6
    quiet_zone_modules: int = 4


@dataclass(frozen=True, slots=True)
class Point:
    x: int
    y: int


@dataclass(frozen=True, slots=True)
class Quad:
    """A filled rectangle covering pixels left <= x < right and top <= y < bottom, dark (luma 0) or light (luma 255)."""

    left: int
    top: int
    right: int
    bottom: int
    dark: bool

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


@dataclass(frozen=True, slots=True)
class Vertex:
    """A vertex on a pixel corner, with the luma of its quad (0 or 255)."""

    x: int
    y: int
    luma: int


def packed_module_byte_count(size: int) -> int:
    """The bytes of a packed module matrix of size x size modules: 211 for the main marker (41), 79 for the sync marker (25)."""
    return 0 if size <= 0 else ((size * size) + 7) // 8


@dataclass(frozen=True, slots=True)
class ModuleMatrix:
    """The encoded marker: the QR symbol's modules, 1 bit each (1 = dark), packed row-major, most significant bit first, continuous across
    rows, the last byte zero padded (exactly test-data/markers/modules.csv's modulesHex). generate_modules makes it once per marker; every
    drawing output (modules_to_quads, modules_to_triangles, modules_to_indexed, modules_to_bitmap) is made from it.

    `size` modules per side (41 for the main marker, 25 for the sync marker). Building one from bits checks the size (21 to 41, in steps
    of 4) and the length (at least packed_module_byte_count(size) bytes), and ignores bits past the last module."""

    size: int
    bits: bytes = field(repr=False)

    def __post_init__(self) -> None:
        count = packed_module_byte_count(self.size)
        if self.size < 21 or self.size > 41 or (self.size - 17) % 4 != 0 or len(self.bits) < count:
            raise ValueError(f"not a packed QR symbol: size {self.size}, {len(self.bits)} bytes")
        bits = bytearray(self.bits[:count])
        used = (self.size * self.size) % 8
        if used:
            bits[-1] &= (0xFF << (8 - used)) & 0xFF
        object.__setattr__(self, "bits", bytes(bits))

    def is_dark(self, x: int, y: int) -> bool:
        index = (y * self.size) + x
        return (self.bits[index >> 3] >> (7 - (index & 7))) & 1 == 1


class PixelFormat(IntEnum):
    """The pixels modules_to_bitmap writes. Each pixel is a run of bytes in memory order; pixels follow each other left to right, rows are
    the stride apart, top row first. Every colour channel holds the same value: 0 for a dark module, 255 for a light one.

        GRAY8   1 byte:  [L]
        RGB24   3 bytes: [R, G, B]          (R = G = B = L)
        RGBA32  4 bytes: [R, G, B, A]       (R = G = B = L, A = 255)

    Because R, G and B are equal, a BGR24 or BGRA32 buffer (PIL's "BGR;24", OpenCV's default order) gets exactly the same bytes: use RGB24
    or RGBA32 for them. A buffer with alpha first (ARGB) is not supported."""

    GRAY8 = 0
    RGB24 = 1
    RGBA32 = 2

    @property
    def bytes_per_pixel(self) -> int:
        return (1, 3, 4)[self]
