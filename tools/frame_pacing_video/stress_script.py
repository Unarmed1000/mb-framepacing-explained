# SPDX-FileCopyrightText: Copyright (C) 2026 Rene Thrane
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""The stress clips (modes 60-stress and 30-stress), for how mb-framepacing's animation error handles lost frames: a fixed script of
scenarios on a 60 Hz display, paced at 60 or 30 Hz, with no noise and no random numbers, so every animation time is exact. Unlike a
presentation fault (presentation_faults), which keeps every frame's animation time and changes only what is on screen, a script
says frame by frame what was rendered and what was shown.

A scenario is a picture of what is on screen, one letter per target frame time (per refresh with `unit=1`). The letters are frames
in the order they were rendered: a letter that is not in the picture was rendered and never shown (a a c: b was dropped), and one
out of its order was shown out of order (a c b e). Unless the scenario says otherwise (`plan`, `clock`):
- a frame is rendered for one target after the frame before it, or after that frame's display when that was later (a late frame
  moves the plan with it, as a pacer plans from where a late present is shown);
- a frame's animation time is the moment it was rendered for: a late frame shows its own moment, and the frame after it catches up.
Where the script's clock loses time (a frame's step shorter than the plan's) it stays behind: the frames after it are on time, with
their animation time behind their display time by what was lost. A step is what is measured, so this interacts with nothing.

Between two scenarios lie at least GAP_FRAMES frames on time, so they cannot interact. A scenario's frames start at its first letter
and go on to the last letter of its picture, the frame that is back on time.

The clip's motion is the fast speed's, in a clip of a whole number of its round trips. Only scenario 12 flags frames static, in rests
of the box; the box rests at every whole second of animation time (at_rest, which generate_videos.at_rest's rests are tested against)
and no other frame is flagged, as the plain 60 and 30 clips flag none.

The run's edges are the seam of the loop the clips are made of (the lead-in shows the end of the clip and the lead-out its start, as in
every test clip): the clip's frame 0, rendered for the last target before the clip, is never shown. So the last frame before the
clip stays on screen for its time, in the lead-in as the start marker's frame and at the clip's end as its last frame, and the clip's
first refresh shows frame 1. The same frame, in the next loop, is the one lost before the end marker.
"""

import bisect
import functools
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from math import ceil

from frame_timing import Refreshes, SimulatedFrames, TimingParameters
from presentation_faults import Block

# The display the script is written for, and the refreshes in a round trip of the fast speed, which the clip fills a whole number of
FPS = Fraction(60)
ROUND_TRIP_REFRESHES = 120
# The rests of the fast speed's motion: at every whole second of animation time, this many refreshes to either side
REST_EVERY_REFRESHES = 60
REST_REFRESHES = 3
# On-time frames between two scenarios, at least
GAP_FRAMES = 12
# How many frames long the stretches are: the scenarios that repeat a pattern
EVERY_OTHER_FRAMES = 30
STRETCH_FRAMES = 24
HITCH_TARGETS = 10
# The fault kind in the manifest
SCRIPTED = "scripted"


@dataclass(frozen=True)
class Scenario:
    """A stretch of the clip: its name, and its frames (the rendered frames from `first`, `count` of them)."""

    name: str
    first: int
    count: int


@dataclass(frozen=True)
class StressClip:
    """A script's frames, as the generator's other modes give them, and the rest of what its markers say: the frame on screen in
    every refresh, the preferred frame time and the static flag of each frame, the frames whose marker says the present of the frame
    before failed, the scenarios, and the frames dropped and shown out of order as fault events."""

    frames: SimulatedFrames
    screen: tuple[int, ...]
    preferred: tuple[Refreshes, ...]
    static_after: tuple[bool, ...]
    present_failed: frozenset[int]
    scenarios: tuple[Scenario, ...]
    events: tuple[Block, ...]


@dataclass(frozen=True)
class _Frame:
    """A rendered frame, in refreshes: the refresh it was rendered for and its animation time, the refresh it first appears on (None:
    never), and its target frame time."""

    intended: Fraction
    shown: int | None
    animation: Fraction
    interval: Fraction
    static: bool = False
    present_failed: bool = False


def letters(picture: str) -> list[int]:
    """A picture's frames, as offsets from its first frame: "a a c" is 0, 0, 2."""
    return [ord(letter) - ord("a") for letter in picture.split()]


def at_rest(animation: Fraction) -> bool:
    """Whether the box stands at a rest of the fast speed's motion at this animation time, in refreshes."""
    within = animation % REST_EVERY_REFRESHES
    return min(within, REST_EVERY_REFRESHES - within) <= REST_REFRESHES


@dataclass
class _Script:
    """The clip so far: the next frame on time is rendered for `slot`, with an animation time `behind` its display time."""

    base: Fraction
    interval: Fraction
    frames: list[_Frame] = field(default_factory=list)
    scenarios: list[Scenario] = field(default_factory=list)
    slot: Fraction = Fraction(0)
    behind: Fraction = Fraction(0)

    def on_time(self, count: int = GAP_FRAMES) -> None:
        """`count` frames on time, each shown for one target."""
        for _ in range(count):
            self.frames.append(_Frame(self.slot, int(self.slot), self.slot - self.behind, self.interval))
            self.slot += self.interval

    def draw(
        self,
        name: str,
        picture: Sequence[int],
        unit: Fraction | None = None,
        plan: Mapping[int, Fraction | int] | None = None,
        clock: Mapping[int, Fraction | int] | None = None,
        pace: Fraction | None = None,
        then: Fraction | None = None,
        failed: Collection[int] = (),
        static: bool = False,
    ) -> None:
        """The frames of a picture, from the next frame on time. `unit`: refreshes per letter (one target). `plan`: when a frame was
        rendered for, and `clock`: the animation time it shows, in letters from the picture's first frame. `pace`: the target frame
        time of the frames after the first, and `then` of the frames after the picture (by default the same). `failed`: frames
        whose marker says the present of the frame before them failed. `static`: the frames at a rest of the box are static."""
        unit = self.interval if unit is None else unit
        pace = self.interval if pace is None else pace
        origin, start = self.slot, self.slot - self.behind
        first = len(self.frames)
        shown: dict[int, int] = {}
        for position, frame in enumerate(picture):
            _ = shown.setdefault(frame, int(origin + position * unit))
        for frame in range(max(picture) + 1):
            due = origin
            if frame:
                last = self.frames[-1]
                due = max(last.intended, last.intended if last.shown is None else Fraction(last.shown)) + pace
            intended = origin + plan[frame] * unit if plan and frame in plan else due
            animation = start + clock[frame] * unit if clock and frame in clock else intended - self.behind
            interval = pace if frame else self.interval
            self.frames.append(_Frame(intended, shown.get(frame), animation, interval, static and at_rest(animation), frame in failed))
        last = self.frames[-1]
        assert last.shown is not None, name
        self.scenarios.append(Scenario(name, first, len(self.frames) - first))
        self.interval = pace if then is None else then
        self.slot = max(last.intended, Fraction(last.shown)) + self.interval
        self.behind = last.intended - last.animation

    def rest(self, name: str, dropped_last: bool) -> None:
        """A rest of the box, its frames static after, with a frame dropped next to it: the first frame at rest, so the step into
        the rest crosses the drop; or the last, so the step out of it does."""
        self.on_time()
        while at_rest(self.slot - self.behind) or not at_rest(self.slot + self.interval - self.behind):
            self.on_time(1)
        resting = 0
        while at_rest(self.slot + (resting + 1) * self.interval - self.behind):
            resting += 1
        moving = resting + 1
        shown = [*range(moving - 1), moving - 2, moving] if dropped_last else [0, 0, *range(2, moving + 1)]
        self.draw(name, shown, static=True)

    def finish(self, parameters: TimingParameters) -> StressClip:
        """The clip, its last frame on screen until its end: frame 0 of the next loop is due one target before it."""
        refreshes = int(self.slot + self.interval)
        rendered = self.frames
        by_refresh = sorted((frame.shown, index) for index, frame in enumerate(rendered) if frame.shown is not None)
        moments = [refresh for refresh, _ in by_refresh]
        screen = tuple(by_refresh[bisect.bisect_right(moments, refresh) - 1][1] for refresh in range(refreshes))
        starts, cpu = _cpu_times(rendered, parameters.frame_cost)
        seconds = [moment / FPS for moment in starts]
        return StressClip(
            SimulatedFrames(
                tuple(ceil(frame.intended) if frame.shown is None else frame.shown for frame in rendered),
                tuple(frame.intended / FPS for frame in rendered),
                tuple(frame.animation / FPS for frame in rendered),
                tuple(_refreshes(frame.intended) for frame in rendered),
                tuple(_refreshes(frame.interval) for frame in rendered),
                tuple(seconds),
                tuple(busy / FPS for busy in cpu),
            ),
            screen,
            tuple(_refreshes(min(self.base, frame.interval)) for frame in rendered),
            tuple(frame.static for frame in rendered),
            frozenset(index for index, frame in enumerate(rendered) if frame.present_failed),
            tuple(self.scenarios),
            _events(rendered),
        )


def _refreshes(value: Fraction) -> Refreshes:
    """A whole number of refreshes as an int, so a manifest's numbers stay whole."""
    return value.numerator if value.denominator == 1 else value


def _cpu_times(frames: Sequence[_Frame], frame_cost: Fraction) -> tuple[list[Fraction], list[Fraction]]:
    """Each frame's CPU start and CPU busy, in refreshes. It starts one target before the refresh it was rendered for, or when the
    frame before is done, and is busy for the frame cost's share of the target. A frame that misses its refresh (late, or dropped
    because it was overtaken) was busy until after that refresh; a frame shown early started in time for that, whatever ran
    beside it; a frame faster than the display misses nothing, and neither does one whose present failed."""
    starts: list[Fraction] = []
    busy: list[Fraction] = []
    done: Fraction | None = None
    for index, frame in enumerate(frames):
        shown = frame.intended if frame.shown is None else Fraction(frame.shown)
        early = shown < frame.intended
        start = min(shown, frame.intended) - frame.interval
        if done is not None and not early:
            start = max(start, done)
        lost = frame.shown is None and frame.interval >= 1 and not (index + 1 < len(frames) and frames[index + 1].present_failed)
        over = 1 if lost else shown - frame.intended
        took = frame_cost * frame.interval
        if over > 0:
            took = max(took, frame.intended + over - (1 - frame_cost) - start)
        starts.append(start)
        busy.append(took)
        done = start + took
    return starts, busy


def _events(frames: Sequence[_Frame]) -> tuple[Block, ...]:
    """The frames dropped, in runs, and the pairs shown out of order, as fault events."""
    events: list[Block] = []
    index = 0
    while index < len(frames):
        run = 0
        while index + run < len(frames) and frames[index + run].shown is None:
            run += 1
        following, here = frames[index + 1].shown if index + 1 < len(frames) else None, frames[index].shown
        if run:
            events.append(Block(index, run))
        elif here is not None and following is not None and following < here:
            events.append(Block(index, 2, (1, 0)))
        index += max(run, 1)
    return tuple(events)


def _script(rate: int) -> _Script:
    """The scenarios of the clip paced at `rate` Hz, in the order of mb-framepacing's request, between the two edges of the run."""
    interval = FPS / rate
    if interval not in (1, 2):
        raise ValueError(f"the stress clips are paced at 60 or 30 Hz on a 60 Hz display, not at {rate} Hz")
    script = _Script(interval, interval)
    full_rate = interval == 1

    def scenario(name: str, picture: str | Sequence[int], **options: object) -> None:
        script.on_time()
        frames = letters(picture) if isinstance(picture, str) else picture
        script.draw(name, frames, **options)  # pyright: ignore[reportArgumentType]

    # Rendered for the target before the clip, so the clip's first refresh shows the frame after it
    script.draw("23-dropped-first-frame", [1], plan={0: -1, 1: 0})
    scenario("01-dropped", "a a c")
    scenario("02-dropped-run-2", "a a a d")
    scenario("02-dropped-run-3", "a a a a e")
    scenario("02-dropped-run-4", "a a a a a f")
    # b has the animation time one target after a, and c the same one: on screen two targets apart, in animation time one
    scenario("03-dropped-clock-lost", "a a c", clock={2: 1})
    scenario("04-late-step-stays", "a a b c", clock={2: 2})
    scenario("05-late-catches-up", "a a b c")
    scenario("06-two-late", "a a b b c d")
    scenario("07-dropped-then-refresh-lost", "a a a c d")
    scenario("08-every-other-dropped", [*(2 * (frame // 2) for frame in range(EVERY_OTHER_FRAMES)), EVERY_OTHER_FRAMES])
    # The game stalled before it started b, so b is on the plan either way: only the clock differs
    hitch = [*([0] * HITCH_TARGETS), 1]
    scenario("09-hitch-clock-running", hitch, plan={1: HITCH_TARGETS})
    scenario("09-hitch-clock-stopped", hitch, plan={1: HITCH_TARGETS}, clock={1: 1})
    # e comes a refresh before its time and stays until f is due
    scenario("10-out-of-order-next-to-drop", "a c b e e f", plan={1: 1, 2: 2, 3: 3, 4: 4, 5: 5})
    scenario("11-present-failed", "a a c", failed=(2,))
    scenario("11-dropped-by-target", "a a c")
    script.rest("12-rest-first-frame-dropped", dropped_last=False)
    script.rest("12-rest-last-frame-dropped", dropped_last=True)
    # The first frame at the new rate is dropped: from 60 Hz it was due two refreshes after a, from 30 Hz one
    down, up = {"unit": Fraction(1), "pace": Fraction(2)}, {"unit": Fraction(1), "pace": Fraction(1)}
    if full_rate:
        scenario("13-pacing-60-to-30", "a a a a c", **down)
        scenario("13-pacing-30-to-60", "a a c", **up)
    else:
        scenario("13-pacing-30-to-60", "a a c", **up)
        # Back at 30 Hz on the clip's even refreshes
        if (script.slot + GAP_FRAMES) % 2:
            script.on_time(1)
        scenario("13-pacing-60-to-30", "a a a a c", **down)
    # The same loss, with the plan moving later by a target and with it staying (07 has this picture with c late on the plan instead)
    scenario("14-plan-moves", "a a a c d", plan={2: 3})
    scenario("14-plan-keeps-grid", "a a c d")
    if full_rate:
        # 120 fps: every other frame overtaken before it reached the screen
        scenario("15-faster-than-display", [2 * frame for frame in range(STRETCH_FRAMES)], unit=Fraction(1), pace=Fraction(1, 2), then=Fraction(1))
    else:
        scenario("16-late-by-one", "a a a b c c", unit=Fraction(1), plan={2: 4})
        # c stays until d is back on the plan
        scenario("17-early-then-back", "a b b c c c d d", unit=Fraction(1))
        cadence = [frame for pair in range(0, STRETCH_FRAMES, 2) for frame in (pair, pair, pair, pair + 1)]
        scenario("18-uneven-cadence", [*cadence, STRETCH_FRAMES], unit=Fraction(1), plan={frame: 2 * frame for frame in range(STRETCH_FRAMES + 1)})
        scenario("19-wrong-animation-rate", list(range(STRETCH_FRAMES)), clock={frame: Fraction(frame, 2) for frame in range(STRETCH_FRAMES)})
    scenario("20-two-drops-close", "a a c d d f")
    scenario("21-dropped-after-late", "a a b b d")
    # c is on time and d, the frame after it, late
    scenario("22-dropped-before-late", "a a c c d e")
    script.on_time()
    while (script.slot + script.interval) % ROUND_TRIP_REFRESHES:
        script.on_time(1)
    # The frame lost is frame 0 of the next loop, due one target before the clip's end
    script.scenarios.append(Scenario("23-dropped-last-frame", len(script.frames) - 1, 1))
    return script


@functools.cache
def clip(rate: int, parameters: TimingParameters) -> StressClip:
    """The stress clip paced at `rate` Hz (60 or 30). Raises ValueError for another rate or another display."""
    if parameters.fps != FPS:
        raise ValueError(f"the stress clips are scripted for a {float(FPS):g} Hz display, not {float(parameters.fps):g}")
    return _script(rate).finish(parameters)


def clip_seconds(rate: int) -> Fraction:
    """How long the stress clip paced at `rate` Hz is."""
    return len(clip(rate, TimingParameters()).screen) / FPS
