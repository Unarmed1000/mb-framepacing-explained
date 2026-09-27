# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Mana Battery ApS

"""The marker's data types, as in the C# library (MB.FrameMarker) and the C++ library (MB::FrameMarker).

Coordinates are pixels with the origin at the top-left corner, +x to the right and +y down. Every quad edge and every vertex lies on an
integer pixel edge.
"""

from dataclasses import dataclass, field, replace
from enum import IntEnum
from typing import Self


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
    same clock for the whole run) and the target frame time (u32 ticks, 166_667 for 60 fps); 0 = unknown for both. A sync marker only
    carries the frame index."""

    frame_index: int
    animation_ticks: int
    run_id: int = 0
    kind: MarkerKind = MarkerKind.FRAME
    intended_display_ticks: int = 0
    target_frame_ticks: int = 0

    def with_kind(self, kind: MarkerKind) -> Self:
        return replace(self, kind=kind)


@dataclass(frozen=True, slots=True)
class StartMetadata:
    """What a start marker carries besides the payload: the start time in DateTime UTC ticks (0 = unknown) and a name of at most 60
    bytes as UTF-8."""

    utc_ticks: int = 0
    name: str = ""


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
