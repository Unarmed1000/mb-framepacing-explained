# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""Presentation faults (modes ending in -dropped-frames or -out-of-order, e.g.
60-naive-5ms-diagram-slow-frames-every-1s-dropped-frames): the game renders every frame as its mode simulates it, but not every
frame reaches the screen, or not in the order it was rendered. Only what is on screen in each refresh changes; every frame keeps
its animation time, the pacer's plan for it and its CPU times, and a marker carries the values of the frame it shows.

Two fault events a second, at FAULT_POINTS of it (30 % and 70 %: the fast box is moving, and a replayed diagram's frames in the
middle of the second are clear of them), each a block of frames starting with the one on screen there:
- dropped-frames: runs of DROP_RUNS frames (1, 2, 3, 4, then again) rendered but never shown; the frame before them stays on
  screen, and the one after comes on its own refresh, on time
- out-of-order: blocks of ORDER_BLOCKS frames (a pair, 3, a pair, 4) shown in another order in the same refreshes: a pair swapped,
  the larger blocks in a random order where no frame keeps its place (the worst case), drawn from our own PCG32 generator so the
  same clip always gets the same order

A measurement counts a frame as presented when it first appears with a frame index above every one shown before it (mb-framepacing's
rule): a dropped frame is never presented, and a frame shown only after a later one is out of order and not presented either.
"""

import bisect
from dataclasses import dataclass
from fractions import Fraction

from frame_timing import FrameMode
from pcg32 import Pcg32

DROPPED = "dropped-frames"
OUT_OF_ORDER = "out-of-order"
FAULTS = (DROPPED, OUT_OF_ORDER)
# Where in each second a fault event starts
FAULT_POINTS = (Fraction(3, 10), Fraction(7, 10))
# How many frames each event takes, in turn: dropped in a row, or shown in another order
DROP_RUNS = (1, 2, 3, 4)
ORDER_BLOCKS = (2, 3, 2, 4)


@dataclass(frozen=True)
class Block:
    """A fault event: `count` frames from `first`; out of order, the order they are shown in (offsets from `first`: slot i of
    the block's refreshes shows frame first + order[i]); dropped, no order."""

    first: int
    count: int
    order: tuple[int, ...] = ()


def derangement(generator: Pcg32, size: int) -> tuple[int, ...]:
    """A random order of `size` offsets in which none keeps its place (a shuffle, drawn again until it has no fixed point)."""
    if size < 2:
        raise ValueError(f"{size} frames cannot be shown out of order")
    while True:
        order = list(range(size))
        for index in range(size - 1, 0, -1):
            other = generator.randint(0, index)
            order[index], order[other] = order[other], order[index]
        if all(offset != index for index, offset in enumerate(order)):
            return tuple(order)


def base_screen(flips: tuple[int, ...], refreshes: int) -> tuple[int, ...]:
    """The frame on screen in each refresh when every frame is shown as flipped: the last one flipped by then."""
    return tuple(bisect.bisect_right(flips, refresh) - 1 for refresh in range(refreshes))


def blocks(mode: FrameMode, flips: tuple[int, ...], late: list[int], intervals: tuple[int, ...], fps: Fraction, refreshes: int) -> list[Block]:
    """The mode's fault events: two a second, at FAULT_POINTS, each starting with the frame on screen there. Raises ValueError when
    a block's frames, or the frame before or after it, are not on time and shown for exactly one swap interval (a late or held
    frame of a replayed diagram, e.g. -3x-every-1s, whose copies sit at 30, 50 and 70 %)."""
    assert mode.fault in FAULTS, mode.name
    second = fps.numerator if fps.denominator == 1 else None
    if second is None or refreshes % second:
        raise ValueError(f"{mode.name}: a fault every second needs whole seconds of whole refreshes ({refreshes} at {float(fps):g} fps)")
    count = len(flips)
    generator = Pcg32.from_text(f"out of order, {mode.rate} Hz, {count} frames")
    events: list[Block] = []
    for start in range(0, refreshes, second):
        for point in FAULT_POINTS:
            at = point * second
            if at.denominator != 1:
                raise ValueError(f"{mode.name}: {float(point):g} of a second is not a whole refresh at {float(fps):g} fps")
            first = bisect.bisect_right(flips, start + int(at)) - 1
            if mode.fault == DROPPED:
                block = Block(first, DROP_RUNS[len(events) % len(DROP_RUNS)])
            else:
                size = ORDER_BLOCKS[len(events) % len(ORDER_BLOCKS)]
                block = Block(first, size, (1, 0) if size == 2 else derangement(generator, size))
            around = range(block.first - 1, block.first + block.count + 1)
            if around.start < 0 or around.stop >= count or any(late[index] != 0 or flips[index + 1] - flips[index] != intervals[index] for index in around):
                raise ValueError(
                    f"{mode.name}: the {block.count} frames from frame {block.first} (refresh {start + int(at)}) and their neighbours "
                    + "must be on time and shown for one swap interval each"
                )
            events.append(block)
    return events


def screen(flips: tuple[int, ...], refreshes: int, kind: str, events: list[Block]) -> tuple[int, ...]:
    """The frame on screen in each refresh with the fault events applied: a dropped frame's refreshes show the frame before its
    run; an out-of-order block's refreshes show its frames in the block's order."""
    base = base_screen(flips, refreshes)
    replaced: dict[int, int] = {}
    for block in events:
        for offset in range(block.count):
            replaced[block.first + offset] = block.first - 1 if kind == DROPPED else block.first + block.order[offset]
    return tuple(replaced.get(frame, frame) for frame in base)


def presented(on_screen: tuple[int, ...]) -> dict[int, int]:
    """The frames a measurement counts as presented, each with the refresh it first appears on: a frame whose index is above every
    frame shown before it (the frames before the clip are the previous loop's, below all of its own)."""
    first_seen: dict[int, int] = {}
    highest = -1
    for refresh, frame in enumerate(on_screen):
        if frame > highest:
            first_seen[frame] = refresh
            highest = frame
    return first_seen


def skipped_frame_indices(shown: dict[int, int]) -> int:
    """How many frame indices between presented frames were never presented."""
    frames = sorted(shown)
    return sum(b - a - 1 for a, b in zip(frames, frames[1:], strict=False))


def out_of_order_refreshes(on_screen: tuple[int, ...]) -> int:
    """How many refreshes show a frame below one shown before it: a measurement sees an older frame come back."""
    highest, count = -1, 0
    for frame in on_screen:
        if frame < highest:
            count += 1
        highest = max(highest, frame)
    return count
