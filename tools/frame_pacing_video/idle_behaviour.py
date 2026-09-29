# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""What a game does while nothing moves (modes ending in -static-rests, -on-demand, -on-demand-paused-clock or -idle-1fps, e.g.
60-on-demand): the frames it renders while the box rests, and what their markers say about them (mb-framepacing's marker format:
the static flag, the target and preferred frame time).

A frame is at rest when the box it shows stands exactly at its rest position (the caller decides, from the scene); nothing animates
in it, so it looks the same whatever time it is shown at, and its marker is flagged static: mb-framepacing does not judge the
animation error of a step from or to it.
- static-rests: every frame is rendered as its mode simulates it; the ones at rest are flagged static. A naive timer's jitter while
  the box rests cannot be seen, and is not judged.
- on-demand: a renderer that presents only when something changes: at rest only the first frame (static), then nothing until the
  box moves again, while the display keeps showing it. Its target and preferred frame time are "on demand" (no interval to aim for),
  so no wait for the next frame is late. Its animation clock runs on, so the first moving frame is exactly where it should be.
- on-demand-paused-clock: the same, but the animation clock stops while nothing animates and resumes with one frame's step: the
  first moving frame after a rest shows the moment one frame after the rest began, however long the rest was. The box is still
  drawn where it belongs (the scene); only the animation time in the marker is behind, so the step to it is off by the rest, and
  only the static flag of the frame before keeps that from being judged.
- idle-1fps: a device that saves power while idle: at rest the first frame, then one frame every IDLE_SECONDS, each with target and
  preferred frame time IDLE_SECONDS (idle at the rate it wants: not late, not below its preferred rate). Needs rests of at least
  IDLE_SECONDS (the idle speed).

The game renders only the frames it keeps, so their frame indices stay consecutive. The clip's first frame is always rendered, so
every clip starts with a presented frame.
"""

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction

from frame_timing import FrameMode, SimulatedFrames

STATIC_RESTS = "static-rests"
ON_DEMAND = "on-demand"
ON_DEMAND_PAUSED_CLOCK = "on-demand-paused-clock"
IDLE_1FPS = "idle-1fps"
IDLES = (STATIC_RESTS, ON_DEMAND, ON_DEMAND_PAUSED_CLOCK, IDLE_1FPS)
# How long an idle-1fps frame stays on screen while the box rests
IDLE_SECONDS = Fraction(1)


@dataclass(frozen=True)
class IdleFrames:
    """The frames the game renders (their swap intervals, for idle-1fps, the idle frames' IDLE_SECONDS), the moment each shows (the
    scene: what is drawn; the frames' animation time is what their clock says, behind it with a paused clock), whether each is at
    rest (static) and whether the game presents on demand (no target or preferred frame time)."""

    frames: SimulatedFrames
    scene: tuple[Fraction, ...]
    static: tuple[bool, ...]
    on_demand: bool


def _kept(mode: FrameMode, flips: tuple[int, ...], resting: list[bool], idle_refreshes: int) -> list[int]:
    """The frames the game renders: all, or at rest only the first (on demand) or one every idle_refreshes (idle-1fps)."""
    if mode.idle == STATIC_RESTS:
        return list(range(len(flips)))
    kept: list[int] = []
    for index, flip in enumerate(flips):
        # The first frame always, every frame that moves, and the first frame at rest; idling, one every idle_refreshes
        changes = index == 0 or not resting[index] or not resting[index - 1]
        if changes or (mode.idle == IDLE_1FPS and flip - flips[kept[-1]] >= idle_refreshes):
            kept.append(index)
    return kept


def apply(mode: FrameMode, frames: SimulatedFrames, at_rest: Callable[[Fraction], bool], fps: Fraction) -> IdleFrames:
    """The mode's idle behaviour over the simulated frames: `at_rest` says whether the box stands still at an animation time. Raises
    ValueError when the box never rests (a scroll), or, for idle-1fps, never rests long enough to show an idle frame."""
    assert mode.idle in IDLES, mode.name
    resting = [at_rest(moment) for moment in frames.animation]
    if not any(resting):
        raise ValueError(f"{mode.name}: the box never rests at this speed, so there is nothing idle to show")
    idle_refreshes = IDLE_SECONDS * fps
    if idle_refreshes.denominator != 1:
        raise ValueError(f"{mode.name}: {float(IDLE_SECONDS):g} s is not a whole number of refreshes at {float(fps):g} fps")
    kept = _kept(mode, frames.flips, resting, int(idle_refreshes))
    intervals = list(frames.intervals)
    if mode.idle == IDLE_1FPS:
        # A frame after another frame at rest is paced at the idle rate (the clip's first follows the previous loop's last); the
        # first at rest still comes at the full rate
        idle = [resting[index] and resting[kept[position - 1]] for position, index in enumerate(kept)]
        # Beyond the clip's first frame, which follows the previous loop's rest: a rest long enough to idle in
        if not any(idle[1:]):
            raise ValueError(f"{mode.name}: the box never rests {float(IDLE_SECONDS):g} s at this speed (use --speed idle)")
        intervals = [int(idle_refreshes) if idle[position] else frames.intervals[index] for position, index in enumerate(kept)]
    else:
        intervals = [frames.intervals[index] for index in kept]
    scene = tuple(frames.animation[index] for index in kept)
    animation = list(scene)
    if mode.idle == ON_DEMAND_PAUSED_CLOCK:
        # The clock stands still while nothing animates, and resumes with one frame's step
        for position in range(1, len(kept)):
            index, previous = kept[position], kept[position - 1]
            step = Fraction(frames.intervals[index]) / fps if resting[previous] else scene[position] - scene[position - 1]
            animation[position] = animation[position - 1] + step
    rendered = SimulatedFrames(
        tuple(frames.flips[index] for index in kept),
        tuple(frames.samples[index] for index in kept),
        tuple(animation),
        tuple(frames.targets[index] for index in kept),
        tuple(intervals),
        tuple(frames.starts[index] for index in kept),
        tuple(frames.cpu[index] for index in kept),
    )
    return IdleFrames(rendered, scene, tuple(resting[index] for index in kept), mode.idle in (ON_DEMAND, ON_DEMAND_PAUSED_CLOCK))
