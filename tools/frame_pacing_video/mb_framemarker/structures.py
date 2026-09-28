# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Mana Battery ApS

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


@dataclass(frozen=True, slots=True)
class ModuleMatrix:
    """A QR symbol: `size` modules per side, `rows[y][x]` True for dark."""

    size: int
    rows: tuple[tuple[bool, ...], ...] = field(repr=False)

    def is_dark(self, x: int, y: int) -> bool:
        return self.rows[y][x]
