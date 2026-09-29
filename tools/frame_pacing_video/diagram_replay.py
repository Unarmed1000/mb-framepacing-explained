# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""Replay a timing diagram in the videos (modes like 60-diagram-slow-frames): the frames of one of tools/timing_diagrams' diagrams,
when each is shown and which animation time it shows, with one diagram refresh per frame of the mode's rate, repeated to fill the
clip. So a video shows exactly what its diagram shows: the same frames held or late, the same pattern of animation error, at real
speed.

The diagram is reduced to its smallest repeating unit (slow frames: a frame on time, one a refresh late, the one that catches up;
bad half rate: a frame held for one refresh, the next for three), which is repeated back to back; when the unit does not divide
the clip, on-time frames at full rate fill each repetition up to the next one. With -every-Ns (e.g.
60-diagram-slow-frames-every-1s) the whole diagram plays once every N seconds, in the middle of the period, with on-time frames
around it; -Kx-every-Ns plays it K times per period, spread over the middle 40 % of it (60-diagram-slow-frames-3x-every-1s: at
30 %, 50 % and 70 % of each second, where the fast box moves quickly, apart from each other). A VRR diagram cannot be replayed: its frames appear between the refreshes of a fixed rate video.
"""

import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "timing_diagrams"))

import generate_diagrams as diagrams  # noqa: E402  (after the path to tools/timing_diagrams)


@dataclass(frozen=True)
class Pattern:
    """A diagram's smallest repeating unit, in diagram refreshes: the refresh each frame is shown on, the animation time it shows,
    the unit's length (the next unit's first frame is shown then), how long each frame takes until it is presented (its render
    time), and, when the game starts its frames by its own clock (a cap: half rate, bad frame pacing), when each starts; without,
    None: a frame starts when the previous one is shown."""

    shown: tuple[int, ...]
    animation: tuple[Fraction, ...]
    length: int
    render: tuple[Fraction, ...] = ()
    starts: tuple[Fraction, ...] | None = None


@dataclass(frozen=True)
class Replay:
    """The frames of a clip replaying a diagram: the refresh each is flipped on, and in seconds (the clip's first refresh is 0) the
    animation time it shows, when it starts and how long it takes until it is presented (0: unknown, the on-time frames that fill
    the clip around the diagram's)."""

    flips: list[int]
    animation: list[Fraction]
    starts: list[Fraction]
    render: list[Fraction]


def replayable() -> tuple[str, ...]:
    """The diagrams a video can replay: every one at a fixed refresh rate."""
    return tuple(diagram.name for diagram in diagrams.DIAGRAMS if not diagram.vrr)


def _refreshes(value_ms: float) -> Fraction:
    """A diagram time (ms) in diagram refreshes, exact to a microsecond of the diagram."""
    return Fraction(round(value_ms * 1000), round(diagrams.PERIOD * 1000))


def pattern(name: str, whole: bool = False) -> Pattern:
    """The smallest repeating unit of the diagram `name`: the shortest start of it that, repeated, gives every frame the diagram
    shows; with `whole`, every frame of the diagram as it is. Raises ValueError for an unknown diagram and for a VRR one."""
    diagram = diagrams.DIAGRAMS_BY_NAME.get(name)
    if diagram is None:
        raise ValueError(f"no diagram named {name!r}: use one of {', '.join(replayable())}")
    if diagram.vrr:
        raise ValueError(f"the {name} diagram is VRR: its frames appear between refreshes, which a fixed rate video cannot show")
    timed = diagrams.simulate(diagram)
    shown = [_refreshes(frame.shown) for frame in timed]
    animation = [_refreshes(frame.animation) for frame in timed]
    render = [_refreshes(frame.end - frame.start) for frame in timed]
    # Without a cap a frame starts when the previous one is shown (the diagram's first somewhere inside the refresh before it)
    starts = [None if diagram.cpu_cap is None else _refreshes(frame.start) for frame in timed]
    if any(value.denominator != 1 for value in shown):
        raise ValueError(f"the {name} diagram shows a frame between refreshes")
    last = timed[-1]
    length = int(shown[-1]) + last.frame.interval
    frames = list(zip(shown, animation, render, starts, strict=True))
    if not whole:
        for period in range(1, length + 1):
            unit = [frame for frame in frames if frame[0] < period]
            tiled = [
                (at + copy * period, moment + copy * period, took, None if start is None else start + copy * period)
                for copy in range(length // period + 1)
                for at, moment, took, start in unit
            ]
            if [frame for frame in tiled if frame[0] < length] == frames:
                frames, length = unit, period
                break
        else:
            raise AssertionError("the whole diagram always repeats itself")
    clocked = tuple(start for _, _, _, start in frames if start is not None)
    return Pattern(
        tuple(int(at) for at, _, _, _ in frames),
        tuple(moment for _, moment, _, _ in frames),
        length,
        tuple(took for _, _, took, _ in frames),
        None if diagram.cpu_cap is None else clocked,
    )


def title(name: str) -> str:
    """The diagram's short title, lower case: "slow frames", "half rate, bad frame pacing"."""
    heading = diagrams.DIAGRAMS_BY_NAME[name].title.split(":")[0]
    return heading[0].lower() + heading[1:]


# The share of a period its copies are spread over, around its middle, with -Kx-every-Ns
SPREAD = Fraction(2, 5)


def schedule(name: str, every: Fraction | None, refreshes: int, interval: int, fps: Fraction, times: int = 1) -> Replay:
    """The frames of a clip of `refreshes` output refreshes replaying the diagram: the refresh each is flipped on, its animation
    time, when it starts and its render time (s). One diagram refresh is `interval` output refreshes. A frame starts when the
    previous one is flipped (the clip's first when the last one is, one clip earlier), or, in a diagram with a cap, when the
    diagram starts it; the on-time frames around the diagram's have no known render time (0). The unit repeats every `every` seconds, or, without, every
    whole number of refreshes that divides the clip, starting at its own length; on-time frames at full rate fill the rest. With
    `every`, `times` copies play per period, spread over its middle SPREAD. Raises ValueError when the unit does not fit, the
    copies overlap or the repetition does not divide the clip."""
    # Back to back the smallest unit repeats; once per period the whole diagram plays (slow frames: both late frames)
    unit = pattern(name, whole=every is not None)
    length = unit.length * interval
    if every is None:
        period = next(size for size in range(length, refreshes + 1) if refreshes % size == 0 and size % interval == 0)
    else:
        period_refreshes = every * fps
        if period_refreshes.denominator != 1:
            raise ValueError(f"every {every} s is not a whole number of refreshes at {fps} fps")
        period = int(period_refreshes)
        if period < length or refreshes % period or period % interval:
            raise ValueError(f"the {name} diagram ({length} refreshes) cannot repeat every {period} refreshes in a {refreshes}-refresh clip")
    # The unit sits in the middle of its period, on-time frames around it: a clip starts in the middle of a rest of the box's
    # motion, and a period that divides the clip ends in one too, so a unit at a period's start would fall where nothing moves
    centres = [Fraction(1, 2)] if times == 1 else [Fraction(1, 2) - SPREAD / 2 + SPREAD * copy / (times - 1) for copy in range(times)]
    offsets = [int(centre * period - Fraction(length, 2)) // interval * interval for centre in centres]
    if offsets[0] < 0 or offsets[-1] + length > period or any(b < a + length for a, b in zip(offsets, offsets[1:], strict=False)):
        raise ValueError(f"{times} copies of the {name} diagram ({length} refreshes) do not fit apart in {period} refreshes")
    flips: list[int] = []
    moments: list[Fraction] = []
    # Per frame, in output refreshes: when the diagram starts it (None: when the previous frame is flipped) and its render time
    clocked: list[Fraction | None] = []
    renders: list[Fraction] = []
    unit_starts = unit.starts or (None,) * len(unit.shown)
    for start in range(0, refreshes, period):
        at = start
        for offset in offsets:
            for filler in range(at, start + offset, interval):
                flips.append(filler)
                moments.append(Fraction(filler))
                clocked.append(None)
                renders.append(Fraction(0))
            for shown, moment, took, begin in zip(unit.shown, unit.animation, unit.render, unit_starts, strict=True):
                flips.append(start + offset + shown * interval)
                moments.append(start + offset + moment * interval)
                clocked.append(None if begin is None else start + offset + begin * interval)
                renders.append(took * interval)
            at = start + offset + length
        for filler in range(at, start + period, interval):
            flips.append(filler)
            moments.append(Fraction(filler))
            clocked.append(None)
            renders.append(Fraction(0))
    previous = [flips[-1] - refreshes, *flips[:-1]]
    starts = [Fraction(before) if begin is None else begin for before, begin in zip(previous, clocked, strict=True)]
    return Replay(flips, [moment / fps for moment in moments], [start / fps for start in starts], [took / fps for took in renders])
