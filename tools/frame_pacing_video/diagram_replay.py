"""Replay a timing diagram in the videos (modes like 60-diagram-slow-frames): the frames of one of tools/timing_diagrams' diagrams,
when each is shown and which animation time it shows, with one diagram refresh per frame of the mode's rate, repeated to fill the
clip. So a video shows exactly what its diagram shows: the same frames held or late, the same pattern of animation error, at real
speed.

The diagram is reduced to its smallest repeating unit (slow frames: a frame on time, one a refresh late, the one that catches up;
bad half rate: a frame held for one refresh, the next for three), which is repeated back to back. When the unit does not divide
the clip, or with -every-Ns (e.g. 60-diagram-slow-frames-every-1s), on-time frames at full rate fill each repetition up to the
next one. A VRR diagram cannot be replayed: its frames appear between the refreshes of a fixed rate video.
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
    and the unit's length (the next unit's first frame is shown then)."""

    shown: tuple[int, ...]
    animation: tuple[Fraction, ...]
    length: int


def replayable() -> tuple[str, ...]:
    """The diagrams a video can replay: every one at a fixed refresh rate."""
    return tuple(diagram.name for diagram in diagrams.DIAGRAMS if not diagram.vrr)


def _refreshes(value_ms: float) -> Fraction:
    """A diagram time (ms) in diagram refreshes, exact to a microsecond of the diagram."""
    return Fraction(round(value_ms * 1000), round(diagrams.PERIOD * 1000))


def pattern(name: str) -> Pattern:
    """The smallest repeating unit of the diagram `name`: the shortest start of it that, repeated, gives every frame the diagram
    shows. Raises ValueError for an unknown diagram and for a VRR one."""
    diagram = diagrams.DIAGRAMS_BY_NAME.get(name)
    if diagram is None:
        raise ValueError(f"no diagram named {name!r}: use one of {', '.join(replayable())}")
    if diagram.vrr:
        raise ValueError(f"the {name} diagram is VRR: its frames appear between refreshes, which a fixed rate video cannot show")
    timed = diagrams.simulate(diagram)
    shown = [_refreshes(frame.shown) for frame in timed]
    animation = [_refreshes(frame.animation) for frame in timed]
    if any(value.denominator != 1 for value in shown):
        raise ValueError(f"the {name} diagram shows a frame between refreshes")
    last = timed[-1]
    length = int(shown[-1]) + last.frame.interval
    frames = list(zip(shown, animation, strict=True))
    for period in range(1, length + 1):
        unit = [(at, moment) for at, moment in frames if at < period]
        tiled = [(at + copy * period, moment + copy * period) for copy in range(length // period + 1) for at, moment in unit]
        if [frame for frame in tiled if frame[0] < length] == frames:
            return Pattern(tuple(int(at) for at, _ in unit), tuple(moment for _, moment in unit), period)
    raise AssertionError("the whole diagram always repeats itself")


def title(name: str) -> str:
    """The diagram's short title, lower case: "slow frames", "half rate, bad frame pacing"."""
    heading = diagrams.DIAGRAMS_BY_NAME[name].title.split(":")[0]
    return heading[0].lower() + heading[1:]


def schedule(name: str, every: Fraction | None, refreshes: int, interval: int, fps: Fraction) -> tuple[list[int], list[Fraction]]:
    """The frames of a clip of `refreshes` output refreshes replaying the diagram: the refresh each is flipped on and its animation
    time (s). One diagram refresh is `interval` output refreshes. The unit repeats every `every` seconds, or, without, every
    whole number of refreshes that divides the clip, starting at its own length; on-time frames at full rate fill the rest.
    Raises ValueError when the unit does not fit or the repetition does not divide the clip."""
    unit = pattern(name)
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
    flips: list[int] = []
    moments: list[Fraction] = []
    for start in range(0, refreshes, period):
        for at, moment in zip(unit.shown, unit.animation, strict=True):
            flips.append(start + at * interval)
            moments.append(start + moment * interval)
        for at in range(start + length, start + period, interval):
            flips.append(at)
            moments.append(Fraction(at))
    return flips, [moment / fps for moment in moments]
