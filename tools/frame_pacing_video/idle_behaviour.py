# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""What a game does while nothing moves (modes ending in -static-rests, -static-rests-paused-clock, -on-demand,
-on-demand-paused-clock, -on-demand-paused-clock-hindsight or -idle-1fps, e.g. 60-on-demand): the frames it renders while the box
rests, and what their markers say about them (mb-framepacing's marker format: the static flags, the target and preferred frame time).

A frame is at rest when the box it shows stands exactly at its rest position (the caller decides, from the scene). Static describes a
frame's time on screen: nothing animates from its display until the next frame's (the box's motion first appears with the next
frame). The frame that reaches the rest pose has moved itself, and still starts a static time on screen. The marker says so with two
flags: static after on the frame itself (the game knows while rendering it), or static before on the next frame (the game only knows
once it renders that one, having woken up on input); the latter speaks for frame index - 1 only, so after a frame never shown it
marks nothing. mb-framepacing does not judge the animation error of the step from a static frame to the next; the step into it is
judged as usual.
- static-rests: every frame is rendered as its mode simulates it; the ones at rest are flagged static after. A naive timer's jitter
  while the box rests cannot be seen, and is not judged.
- static-rests-paused-clock: every frame is rendered, and the animation clock stops while nothing animates (see
  on-demand-paused-clock): the frames of a rest show one animation time. The frame that reaches the rest pose is flagged static
  after, the frames after it in the rest static after and static before (inside a static stretch, both).
- on-demand: a renderer that presents only when something changes: at rest only the first frame (static after), then nothing until
  the box moves again, while the display keeps showing it. Its target and preferred frame time are "on demand" (no interval to aim
  for), so no wait for the next frame is late. Its animation clock runs on, so the first moving frame is exactly where it should be.
- on-demand-paused-clock: the same, but the animation clock stops while nothing animates and resumes with one frame's step: the
  first moving frame after a rest shows the moment one frame after the rest began, however long the rest was. The box is still
  drawn where it belongs (the scene); only the animation time in the marker is behind, so the step to it is off by the rest, and
  only the static flag of the frame before keeps that from being judged. The flag is set in advance: static after on the rest's
  frame.
- on-demand-paused-clock-hindsight: the same frames and clock, flagged in hindsight: the rest's frame has no flag, the first
  moving frame after it has static before (the game only knows the rest was static once it wakes up). It analyses exactly like
  on-demand-paused-clock.
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
STATIC_RESTS_PAUSED_CLOCK = "static-rests-paused-clock"
ON_DEMAND = "on-demand"
ON_DEMAND_PAUSED_CLOCK = "on-demand-paused-clock"
ON_DEMAND_PAUSED_CLOCK_HINDSIGHT = "on-demand-paused-clock-hindsight"
IDLE_1FPS = "idle-1fps"
IDLES = (STATIC_RESTS, STATIC_RESTS_PAUSED_CLOCK, ON_DEMAND, ON_DEMAND_PAUSED_CLOCK, ON_DEMAND_PAUSED_CLOCK_HINDSIGHT, IDLE_1FPS)
# The behaviours that render every frame, that present only when something changes, and whose clock stops at rest
EVERY_FRAME = (STATIC_RESTS, STATIC_RESTS_PAUSED_CLOCK)
ON_DEMANDS = (ON_DEMAND, ON_DEMAND_PAUSED_CLOCK, ON_DEMAND_PAUSED_CLOCK_HINDSIGHT)
PAUSED_CLOCKS = (STATIC_RESTS_PAUSED_CLOCK, ON_DEMAND_PAUSED_CLOCK, ON_DEMAND_PAUSED_CLOCK_HINDSIGHT)
# How long an idle-1fps frame stays on screen while the box rests
IDLE_SECONDS = Fraction(1)


@dataclass(frozen=True)
class IdleFrames:
    """The frames the game renders (their swap intervals, for idle-1fps, the idle frames' IDLE_SECONDS), the moment each shows (the
    scene: what is drawn; the frames' animation time is what their clock says, behind it with a paused clock), whether each is at
    rest, its marker's static flags (static after: nothing animates while it is on screen; static before: nothing animated while
    the frame before it was) and whether the game presents on demand (no target or preferred frame time)."""

    frames: SimulatedFrames
    scene: tuple[Fraction, ...]
    resting: tuple[bool, ...]
    static_after: tuple[bool, ...]
    static_before: tuple[bool, ...]
    on_demand: bool


def _kept(mode: FrameMode, flips: tuple[int, ...], resting: list[bool], idle_refreshes: int) -> list[int]:
    """The frames the game renders: all, or at rest only the first (on demand) or one every idle_refreshes (idle-1fps)."""
    if mode.idle in EVERY_FRAME:
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
    if mode.idle in PAUSED_CLOCKS:
        # The clock stands still while nothing animates, and resumes with one frame's step
        for position in range(1, len(kept)):
            index, previous = kept[position], kept[position - 1]
            if resting[previous]:
                step = Fraction(0) if resting[index] else Fraction(frames.intervals[index]) / fps
            else:
                step = scene[position] - scene[position - 1]
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
    at_rest_kept = tuple(resting[index] for index in kept)
    static_after, static_before = static_flags(mode, at_rest_kept)
    return IdleFrames(rendered, scene, at_rest_kept, static_after, static_before, mode.idle in ON_DEMANDS)


def static_flags(mode: FrameMode, resting: tuple[bool, ...]) -> tuple[tuple[bool, ...], tuple[bool, ...]]:
    """The static after and static before flags of the rendered frames, from whether each is at rest. A rendered frame at rest shows
    the rest pose, and the next rendered frame is the next one shown, so nothing animates while it is on screen: static after, or in
    hindsight static before on the next frame. The clip's first frame follows its last one (the previous loop's, frame index - 1)."""
    none = (False,) * len(resting)
    # Whether the rendered frame before each is at rest (for the first, the clip's last)
    after_rest = tuple(resting[position - 1] for position in range(len(resting)))
    if mode.idle == ON_DEMAND_PAUSED_CLOCK_HINDSIGHT:
        return none, after_rest
    if mode.idle == STATIC_RESTS_PAUSED_CLOCK:
        return resting, tuple(now and before for now, before in zip(resting, after_rest, strict=True))
    return resting, none
