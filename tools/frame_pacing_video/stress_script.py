# SPDX-FileCopyrightText: Copyright (C) 2026 Rene Thrane
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""The stress clips (the modes of CLIPS: 60-stress, 30-stress, 15-stress and the others), for how mb-framepacing's animation error handles
lost frames: fixed scripts of scenarios, with no noise and no random numbers, so every animation time is exact. Unlike a presentation
fault (presentation_faults), which keeps every frame's animation time and changes only what is on screen, a script says frame by
frame what was rendered and what was shown.

A scenario is a picture of what is on screen, one letter per target frame time (per `unit` refreshes). The letters are frames in the
order they were rendered: a letter that is not in the picture was rendered and never shown (a a c: b was dropped), one out of its
order was shown out of order (a c b e), and one that comes again after another was shown again (a b a c). Unless the scenario says
otherwise (`plan`, `clock`):
- a frame is rendered for one target after the frame before it, or after that frame's display when that was later (a late frame
  moves the plan with it, as a pacer plans from where a late present is shown);
- a frame's animation time is the moment it was rendered for: a late frame shows its own moment, and the frame after it catches up.
Where the script's clock loses time (a frame's step shorter than the plan's) it stays behind, and where it gains time it stays
ahead: the frames after it are on time, with their animation time off their display time by that much. A step is what is measured,
so this interacts with nothing.

Between two scenarios lie at least a clip's `gap` of frames on time, so they cannot interact. A scenario's frames start at its first
letter and go on to the last letter of its picture, the frame that is back on time.

The clip's motion is the fast speed's, in a clip of a whole number of its round trips. Only scenarios 12 and 40 flag frames static,
in rests of the box; the box rests at every whole second of animation time (at_rest, which generate_videos.at_rest's rests are tested
against) and no other frame is flagged, as the plain 60 and 30 clips flag none.

The run's edges are the seam of the loop the clips are made of (the lead-in shows the end of the clip and the lead-out its start, as in
every test clip). In the clips that lose a frame there, the clip's frame 0, rendered for the last target before the clip, is never
shown: the last frame before the clip stays on screen for its time, in the lead-in as the start marker's frame and at the clip's end
as its last frame, and the clip's first refresh shows frame 1. The same frame, in the next loop, is the one lost before the end
marker. An edge holds one thing, so the out of order frames at the edges of those clips have a short clip of their own (-edges).
"""

import bisect
import functools
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from math import ceil
from typing import TypedDict, Unpack

from frame_timing import Refreshes, SimulatedFrames, TimingParameters
from presentation_faults import Block

# On-time frames between two scenarios, at least, and in the clips of a longer target
GAP_FRAMES = 12
SHORT_GAP_FRAMES = 6
# The fast speed's round trip, which a clip fills a whole number of, and the rest at each end of it
ROUND_TRIP_SECONDS = 2
REST_SECONDS = Fraction(1, 10)
# How many frames long the stretches are: the scenarios that repeat a pattern
EVERY_OTHER_FRAMES = 30
STRETCH_FRAMES = 24
HITCH_TARGETS = 10
# Scenario 29: a run of dropped frames over 100, and a hold over 100 refreshes
LONG_DROP_FRAMES = 101
LONG_HOLD_REFRESHES = 120
# The other periods: 25 and 20 ms on a 60 Hz display, each stretch a whole number of refreshes long, a stretch every second
PERIOD_25_MS = Fraction(3, 2)
PERIOD_25_MS_FRAMES = 8
PERIOD_20_MS = Fraction(6, 5)
PERIOD_20_MS_FRAMES = 10
UNEVEN_SECONDS = 8
# The whole capture at 40 fps: as long as a test clip
WHOLE_CAPTURE_FRAMES = 320
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
    never), its target frame time and the frame time the game prefers."""

    intended: Fraction
    shown: int | None
    animation: Fraction
    interval: Fraction
    preferred: Fraction
    static: bool = False
    present_failed: bool = False


class _Options(TypedDict, total=False):
    """What a picture says beyond the letters. `unit`: refreshes per letter (one target). `plan`: when a frame was rendered for, and
    `clock`: the animation time it shows, in letters from the picture's first frame. `pace`: the target frame time of the frames
    after the first, and `then` of the frames after the picture (by default the same). `targets`: a frame's target frame time, for
    that frame alone. `failed`: frames whose marker says the present of the frame before them failed. `static`: the frames at a rest of
    the box are static."""

    unit: Fraction
    plan: Mapping[int, Fraction | int]
    clock: Mapping[int, Fraction | int]
    pace: Fraction
    then: Fraction
    targets: Mapping[int, Fraction]
    failed: Collection[int]
    static: bool


def letters(picture: str) -> list[int]:
    """A picture's frames, as offsets from its first frame: "a a c" is 0, 0, 2."""
    return [ord(letter) - ord("a") for letter in picture.split()]


def in_order(count: int) -> dict[int, int]:
    """The plan of `count` frames each one letter after the last, as they were rendered, however they are shown."""
    return {frame: frame for frame in range(count)}


def at_rest(seconds: Fraction, settle: Fraction) -> bool:
    """Whether the box stands at a rest of the fast speed's motion at this animation time: at each whole second, the rest around it."""
    within = seconds % 1
    return min(within, 1 - within) <= settle / 2


@dataclass
class _Script:
    """The clip so far: the next frame on time is rendered for `slot`, with an animation time `behind` its display time."""

    fps: Fraction
    base: Fraction
    interval: Fraction
    gap: int
    settle: Fraction
    frames: list[_Frame] = field(default_factory=list)
    scenarios: list[Scenario] = field(default_factory=list)
    # Refreshes that show a frame again: each refresh and frame
    again: list[tuple[int, int]] = field(default_factory=list)
    slot: Fraction = Fraction(0)
    behind: Fraction = Fraction(0)

    def on_time(self, count: int | None = None) -> None:
        """`count` frames on time (the clip's gap by default), each shown for one target, or from the next refresh after its moment
        where that falls between two."""
        for _ in range(self.gap if count is None else count):
            preferred = min(self.base, self.interval)
            self.frames.append(_Frame(self.slot, ceil(self.slot), self.slot - self.behind, self.interval, preferred))
            self.slot += self.interval

    def scenario(self, name: str, picture: str | Sequence[int], **options: Unpack[_Options]) -> None:
        """The frames on time between two scenarios, then a picture."""
        self.on_time()
        self.draw(name, letters(picture) if isinstance(picture, str) else picture, **options)

    def stretch(self, name: str, interval: Fraction, count: int) -> None:
        """`count` frames at another target, on time, after the frames between two scenarios."""
        self.on_time()
        first, before = len(self.frames), self.interval
        self.target(interval)
        self.on_time(count)
        self.target(before)
        self.scenarios.append(Scenario(name, first, count))

    def target(self, interval: Fraction) -> None:
        """A new target frame time: the interval between a frame and the one before it, so the next frame is due by it."""
        self.slot += interval - self.interval
        self.interval = interval

    def draw(self, name: str, picture: Sequence[int], **options: Unpack[_Options]) -> None:
        """The frames of a picture, from the next frame on time."""
        unit = options.get("unit", self.interval)
        pace = options.get("pace", self.interval)
        plan = options.get("plan", {})
        clock = options.get("clock", {})
        targets = options.get("targets", {})
        failed = options.get("failed", ())
        origin, start = self.slot, self.slot - self.behind
        first = len(self.frames)
        shown: dict[int, int] = {}
        for position, frame in enumerate(picture):
            refresh = int(origin + position * unit)
            if frame in shown and picture[position - 1] != frame:
                self.again.append((refresh, first + frame))
            _ = shown.setdefault(frame, refresh)
        for frame in range(max(picture) + 1):
            due = origin
            if frame:
                last = self.frames[-1]
                due = max(last.intended, last.intended if last.shown is None else Fraction(last.shown)) + pace
            intended = origin + plan[frame] * unit if frame in plan else due
            animation = start + clock[frame] * unit if frame in clock else intended - self.behind
            interval = targets.get(frame, pace if frame else self.interval)
            preferred = self.base if frame in targets else min(self.base, interval)
            static = options.get("static", False) and at_rest(animation / self.fps, self.settle)
            self.frames.append(_Frame(intended, shown.get(frame), animation, interval, preferred, static, frame in failed))
        last = self.frames[-1]
        assert last.shown is not None, name
        self.scenarios.append(Scenario(name, first, len(self.frames) - first))
        self.interval = options.get("then", pace)
        self.slot = max(last.intended, Fraction(last.shown)) + self.interval
        self.behind = last.intended - last.animation

    def _resting(self, slot: Fraction) -> bool:
        return at_rest((slot - self.behind) / self.fps, self.settle)

    def _before_a_rest(self) -> int:
        """On-time frames up to the frame before the last moving frame ahead of a rest; how many frames that rest holds."""
        self.on_time()
        while self._resting(self.slot) or not self._resting(self.slot + self.interval):
            self.on_time(1)
        resting = 0
        while self._resting(self.slot + (resting + 1) * self.interval):
            resting += 1
        return resting

    def rest(self, name: str, dropped_last: bool) -> None:
        """A rest of the box, its frames static after, with a frame dropped next to it: the first frame at rest, so the step into
        the rest crosses the drop; or the last, so the step out of it does."""
        moving = self._before_a_rest() + 1
        shown = [*range(moving - 1), moving - 2, moving] if dropped_last else [0, 0, *range(2, moving + 1)]
        self.draw(name, shown, static=True)

    def rest_out_of_order(self, name: str) -> None:
        """A rest of the box, its frames static after, with two of its frames shown the other way round, the later two when it can."""
        resting = self._before_a_rest()
        moving = resting + 1
        swapped = 2 if resting >= 3 else 1
        shown = list(range(moving + 1))
        shown[swapped], shown[swapped + 1] = shown[swapped + 1], shown[swapped]
        self.draw(name, shown, plan=in_order(moving + 1), static=True)

    def pad(self, targets_left: int = 0) -> None:
        """On-time frames, and as many more as leave `targets_left` targets to the end of a round trip. Raises ValueError when no
        number of them does (the script moved off its grid and did not move back)."""
        self.on_time()
        round_trip = ROUND_TRIP_SECONDS * self.fps
        count = -(self.slot + targets_left * self.interval) % round_trip / self.interval
        if count.denominator != 1:
            raise ValueError(f"the script stands at refresh {float(self.slot):g}, off the grid of its target of {float(self.interval):g} refreshes")
        self.on_time(int(count))

    def finish(self, parameters: TimingParameters, seam_dropped: bool) -> StressClip:
        """The clip; when frame 0 of the next loop is dropped, its last frame stays on screen until its end, one target longer."""
        refreshes = ceil(self.slot + (self.interval if seam_dropped else 0))
        rendered = self.frames
        by_refresh = sorted([*((frame.shown, index) for index, frame in enumerate(rendered) if frame.shown is not None), *self.again])
        moments = [refresh for refresh, _ in by_refresh]
        screen = tuple(by_refresh[bisect.bisect_right(moments, refresh) - 1][1] for refresh in range(refreshes))
        starts, cpu = _cpu_times(rendered, parameters.frame_cost)
        return StressClip(
            SimulatedFrames(
                tuple(ceil(frame.intended) if frame.shown is None else frame.shown for frame in rendered),
                tuple(frame.intended / self.fps for frame in rendered),
                tuple(frame.animation / self.fps for frame in rendered),
                tuple(_refreshes(frame.intended) for frame in rendered),
                tuple(_refreshes(frame.interval) for frame in rendered),
                tuple(moment / self.fps for moment in starts),
                tuple(busy / self.fps for busy in cpu),
            ),
            screen,
            tuple(_refreshes(frame.preferred) for frame in rendered),
            tuple(frame.static for frame in rendered),
            frozenset(index for index, frame in enumerate(rendered) if frame.present_failed),
            tuple(self.scenarios),
            _events(rendered, screen),
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
        if frame.shown is not None and start + took >= frame.shown:
            # Started late, after a frame that ran long: it took less, or it could not be on screen
            took = frame_cost * (frame.shown - start)
        starts.append(start)
        busy.append(took)
        done = start + took
    return starts, busy


def _events(frames: Sequence[_Frame], screen: Sequence[int]) -> tuple[Block, ...]:
    """The frames dropped, in runs, and the blocks shown out of order, as fault events: the frames from a block's lowest on, in the
    order they follow each other on screen (order: offsets from that frame, one per frame shown; a frame shown again counts again)."""
    events: list[Block] = []
    index = 0
    while index < len(frames):
        run = 0
        while index + run < len(frames) and frames[index + run].shown is None:
            run += 1
        if run:
            events.append(Block(index, run))
        index += max(run, 1)
    following = [frame for position, frame in enumerate(screen) if position == 0 or screen[position - 1] != frame]
    spans: list[tuple[int, int]] = []
    highest = -1
    for position, frame in enumerate(following):
        if frame < highest:
            start = next(index for index, earlier in enumerate(following) if earlier >= frame)
            while spans and spans[-1][1] >= start:
                start = min(start, spans.pop()[0])
            spans.append((start, position))
        highest = max(highest, frame)
    for start, end in spans:
        block = following[start : end + 1]
        low = min(block)
        events.append(Block(low, len(block), tuple(frame - low for frame in block)))
    return tuple(sorted(events, key=lambda event: event.first))


def _first_request(script: _Script, half: Fraction, rate: int) -> None:
    """The scenarios of mb-framepacing's first request, in its order. `half`: half a target, the refreshes per letter of those drawn
    in refreshes at a target of 2. After the first frame, so a clip without the run's first edge starts with the frames between."""
    full_rate = script.base == 1
    script.scenario("01-dropped", "a a c")
    script.scenario("02-dropped-run-2", "a a a d")
    script.scenario("02-dropped-run-3", "a a a a e")
    script.scenario("02-dropped-run-4", "a a a a a f")
    # b has the animation time one target after a, and c the same one: on screen two targets apart, in animation time one
    script.scenario("03-dropped-clock-lost", "a a c", clock={2: 1})
    script.scenario("04-late-step-stays", "a a b c", clock={2: 2})
    script.scenario("05-late-catches-up", "a a b c")
    script.scenario("06-two-late", "a a b b c d")
    script.scenario("07-dropped-then-refresh-lost", "a a a c d")
    script.scenario("08-every-other-dropped", [*(2 * (frame // 2) for frame in range(EVERY_OTHER_FRAMES)), EVERY_OTHER_FRAMES])
    # The game stalled before it started b, so b is on the plan either way: only the clock differs
    hitch = [*([0] * HITCH_TARGETS), 1]
    script.scenario("09-hitch-clock-running", hitch, plan={1: HITCH_TARGETS})
    script.scenario("09-hitch-clock-stopped", hitch, plan={1: HITCH_TARGETS}, clock={1: 1})
    # e comes a target before its time and stays until f is due
    script.scenario("10-out-of-order-next-to-drop", "a c b e e f", plan=in_order(6))
    script.scenario("11-present-failed", "a a c", failed=(2,))
    script.scenario("11-dropped-by-target", "a a c")
    script.rest("12-rest-first-frame-dropped", dropped_last=False)
    script.rest("12-rest-last-frame-dropped", dropped_last=True)
    # The first frame at the new rate is dropped: from the full rate it was due two of its refreshes after a, from half of it one
    slow, fast = rate, 2 * rate
    down_name, up_name = f"13-pacing-{fast}-to-{slow}", f"13-pacing-{slow}-to-{fast}"
    if full_rate:
        down_name, up_name = "13-pacing-60-to-30", "13-pacing-30-to-60"
        script.scenario(down_name, "a a a a c", unit=Fraction(1), pace=Fraction(2))
        script.scenario(up_name, "a a c", unit=Fraction(1), pace=Fraction(1))
    else:
        script.scenario(up_name, "a a c", unit=half, pace=half)
        # Back at the clip's target on its grid
        while (script.slot + script.gap * half) % script.base:
            script.on_time(1)
        script.scenario(down_name, "a a a a c", unit=half, pace=script.base)
    # The same loss, with the plan moving later by a target and with it staying (07 has this picture with c late on the plan instead)
    script.scenario("14-plan-moves", "a a a c d", plan={2: 3})
    script.scenario("14-plan-keeps-grid", "a a c d")
    if full_rate:
        # Twice the rate: every other frame overtaken before it reached the screen
        picture = [2 * frame for frame in range(STRETCH_FRAMES)]
        script.scenario("15-faster-than-display", picture, unit=Fraction(1), pace=Fraction(1, 2), then=Fraction(1))
    else:
        script.scenario("16-late-by-one", "a a a b c c", unit=half, plan={2: 4})
        # c stays until d is back on the plan
        script.scenario("17-early-then-back", "a b b c c c d d", unit=half)
        cadence = [frame for pair in range(0, STRETCH_FRAMES, 2) for frame in (pair, pair, pair, pair + 1)]
        script.scenario("18-uneven-cadence", [*cadence, STRETCH_FRAMES], unit=half, plan={frame: 2 * frame for frame in range(STRETCH_FRAMES + 1)})
        script.scenario("19-wrong-animation-rate", list(range(STRETCH_FRAMES)), clock={frame: Fraction(frame, 2) for frame in range(STRETCH_FRAMES)})
    script.scenario("20-two-drops-close", "a a c d d f")
    script.scenario("21-dropped-after-late", "a a b b d")
    # c is on time and d, the frame after it, late
    script.scenario("22-dropped-before-late", "a a c c d e")


def _recovery(script: _Script, name: str, form: str, late: int | None, target_of_one: bool = False, clock_stays: bool = False) -> None:
    """A late frame (`late` refreshes), or a frame dropped with the one after it in its place a refresh late (None), and the way back:
    the grid moves with it ("realign"); the next frame is held to the old grid ("grid"); or one frame is presented at a swap interval
    of 1, then the next is held to the old grid ("interval-1"), which it reaches at once from 3 refreshes late on a target of 4.
    `target_of_one`: the marker says so on that frame. `clock_stays`: the animation step stays one target, whatever the screen does.
    Letters are refreshes here."""
    target = int(script.base)
    first_frame = 2 if late is None else 1
    first = target + (1 if late is None else late)
    if form == "realign":
        second, third = first + target, first + 2 * target
    elif form == "grid":
        second, third = 2 * target, 3 * target
    else:
        second = first + 1
        third = 3 * target if second == 2 * target else 2 * target
    picture = [*([0] * first), *([first_frame] * (second - first)), *([first_frame + 1] * (third - second)), first_frame + 2]
    plan = {first_frame + 1: second, first_frame + 2: third}
    if late is None:
        plan[first_frame] = first
    else:
        plan[first_frame] = target
    clock = {first_frame + step: (step + 1) * target for step in range(3)} if clock_stays else {}
    targets = {first_frame + 1: Fraction(1)} if target_of_one else {}
    script.scenario(name, picture, unit=Fraction(1), plan=plan, clock=clock, targets=targets)


def _recoveries(script: _Script) -> None:
    """The three ways back after a late or dropped frame, each as far as it fits: a frame held to the old grid must come before the
    grid's next step, so at a target of 2 only from one refresh late. A frame presented at interval 1 is the only one that can say so:
    the other forms draw the same markers either way. The clock's variants move the grid by 8 refreshes in all with the rest, a whole
    number of targets, so the clip ends on its grid."""
    target = int(script.base)
    events: list[tuple[str, int | None]] = [("late-1", 1), ("late-2", 2), ("late-3", 3), ("dropped", None)]
    for event, late in events:
        _recovery(script, f"31-realign-{event}", "realign", late)
    for event, late in events:
        if (late or 1) < target:
            _recovery(script, f"32-back-on-grid-{event}", "grid", late)
    for event, late in events:
        if (late or 1) < target:
            _recovery(script, f"33-interval-1-{event}", "interval-1", late)
            _recovery(script, f"33-interval-1-{event}-target-1", "interval-1", late, target_of_one=True)
    _recovery(script, "34-realign-clock-stays", "realign", 1, clock_stays=True)
    _recovery(script, "34-interval-1-clock-stays", "interval-1", 1, clock_stays=True)


def _out_of_order(script: _Script) -> None:
    """Out of order, away from the run's edges: shown in the refreshes of the frames rendered for them, a pair and blocks where no
    frame keeps its place; older frames shown again; next to a late frame; inside a rest."""
    script.scenario("36-swapped-pair", "a c b d", plan=in_order(4))
    script.scenario("36-block-of-3", "a d b c e", plan=in_order(5))
    script.scenario("36-block-of-4", "a c e b d f", plan=in_order(6))
    script.scenario("37-older-frame-again", "a b a c", plan={2: 3})
    script.scenario("38-two-back-again", "a b c a d", plan={3: 4})
    # b late, then the frames after it, on the plan it moved, the other way round
    script.scenario("39-out-of-order-next-to-late", "a a b d c e", plan={1: 1, 2: 3, 3: 4, 4: 5})
    script.rest_out_of_order("40-out-of-order-in-rest")


def _second_request(script: _Script, half: Fraction | None) -> None:
    """The scenarios of mb-framepacing's second request that follow the first's. `half` as in _first_request; None at a target of
    1, which has no refresh to spare for scenario 26 and no room for the ways back."""
    script.scenario("24-dropped-overshoots", "a a c", clock={2: 3})
    script.scenario("25-animation-stands-still", list(range(STRETCH_FRAMES)), clock=dict.fromkeys(range(STRETCH_FRAMES), 0))
    # One frame shows a's moment again, and the next its own
    script.scenario("25-animation-goes-backwards", "a b c d", clock={2: 0})
    if half is not None:
        # An odd number of frames, so the frame after them is back on the clip's grid
        frames = STRETCH_FRAMES + 1
        script.scenario("26-frames-every-refresh", list(range(frames)), unit=half, plan=in_order(frames))
    script.scenario("29-dropped-run-long", [*([0] * (LONG_DROP_FRAMES + 1)), LONG_DROP_FRAMES + 1])
    held = int(LONG_HOLD_REFRESHES / script.base)
    script.scenario("29-hold-long", [*([0] * held), 1], plan={1: held})
    script.scenario("30-present-failed-in-run", "a a a a e", failed=(4,))
    if half is not None:
        _recoveries(script)
    _out_of_order(script)


def _lost_at_the_seam(script: _Script) -> None:
    """Scenario 23's first half: rendered for the target before the clip, so the clip's first refresh shows the frame after it."""
    script.draw("23-dropped-first-frame", [1], plan={0: -1, 1: 0})


def _lost_at_the_end(script: _Script) -> None:
    """Scenario 23's second half: the frame lost is frame 0 of the next loop, due one target before the clip's end."""
    script.pad(1)
    script.scenarios.append(Scenario("23-dropped-last-frame", len(script.frames) - 1, 1))


def _out_of_order_first(script: _Script) -> None:
    """The clip's first two frames the other way round, right after the start marker."""
    script.draw("41-out-of-order-first-frames", [1, 0, 2], plan=in_order(3))


def _out_of_order_last(script: _Script) -> None:
    """The clip's last two frames the other way round, right before the end marker."""
    script.pad(2)
    script.draw("41-out-of-order-last-frames", [1, 0], plan=in_order(2))


def _sixty(script: _Script) -> None:
    _lost_at_the_seam(script)
    _first_request(script, Fraction(1), 60)
    _second_request(script, None)
    _lost_at_the_end(script)


def _thirty(script: _Script) -> None:
    half = script.base / 2
    _lost_at_the_seam(script)
    _first_request(script, half, 30)
    _second_request(script, half)
    _lost_at_the_end(script)


def _fifteen(script: _Script) -> None:
    half = script.base / 2
    _lost_at_the_seam(script)
    _first_request(script, half, 15)
    script.stretch("35-target-3", Fraction(3), 8)
    _second_request(script, half)
    _lost_at_the_end(script)


def _edges(script: _Script) -> None:
    _out_of_order_first(script)
    _out_of_order_last(script)


def _whole_capture(script: _Script) -> None:
    """Start marker to end marker at a period of 1.5 refreshes, each frame shown from the next refresh after its moment."""
    script.on_time(WHOLE_CAPTURE_FRAMES)
    script.scenarios.append(Scenario("43-whole-capture", 0, WHOLE_CAPTURE_FRAMES))


def _uneven(script: _Script) -> None:
    """60 Hz pacing with a stretch at another period every second, 25 ms and 20 ms in turn."""
    _out_of_order_first(script)
    for second in range(1, UNEVEN_SECONDS + 1):
        while script.slot % script.fps:
            script.on_time(1)
        if second % 2:
            script.stretch(f"42-stretch-25-ms-{second // 2 + 1}", PERIOD_25_MS, PERIOD_25_MS_FRAMES)
        else:
            script.stretch(f"42-stretch-20-ms-{second // 2}", PERIOD_20_MS, PERIOD_20_MS_FRAMES)
    _out_of_order(script)
    _out_of_order_last(script)


def _display(script: _Script) -> None:
    """The scenarios every other display shows, at a target of 1 and again at a target of 2 in the same clip."""
    _out_of_order_first(script)
    for suffix, target in (("", Fraction(1)), ("-target-2", Fraction(2))):
        script.target(target)
        script.scenario(f"01-dropped{suffix}", "a a c")
        script.scenario(f"03-dropped-clock-lost{suffix}", "a a c", clock={2: 1})
        script.scenario(f"04-late-step-stays{suffix}", "a a b c", clock={2: 2})
        script.scenario(f"05-late-catches-up{suffix}", "a a b c")
        script.scenario(f"07-dropped-then-refresh-lost{suffix}", "a a a c d")
        script.scenario(f"10-out-of-order-next-to-drop{suffix}", "a c b e e f", plan=in_order(6))
    script.target(Fraction(1))
    _out_of_order(script)
    _out_of_order_last(script)


@dataclass(frozen=True)
class ClipSpec:
    """A stress clip: its display, its target in refreshes, its script, the frames on time between scenarios, how long the box rests
    at each end, and whether the clip's seam loses a frame."""

    fps: Fraction
    interval: Fraction
    script: Callable[[_Script], None]
    gap: int = GAP_FRAMES
    settle: Fraction = REST_SECONDS
    seam_dropped: bool = False
    # Where the first frame is rendered for: at a period of 1.5 refreshes the first frame's moment is half a refresh before the clip,
    # so frames are shown for 1, 2, 1, 2 refreshes
    first_slot: Fraction = Fraction(0)


SIXTY = Fraction(60)
# 15-stress keeps a rest of several of its long frames
FIFTEEN_REST_SECONDS = Fraction(3, 10)
CLIPS: dict[str, ClipSpec] = {
    "60-stress": ClipSpec(SIXTY, Fraction(1), _sixty, seam_dropped=True),
    "30-stress": ClipSpec(SIXTY, Fraction(2), _thirty, seam_dropped=True),
    "15-stress": ClipSpec(SIXTY, Fraction(4), _fifteen, SHORT_GAP_FRAMES, FIFTEEN_REST_SECONDS, seam_dropped=True),
    "60-stress-edges": ClipSpec(SIXTY, Fraction(1), _edges),
    "30-stress-edges": ClipSpec(SIXTY, Fraction(2), _edges),
    "15-stress-edges": ClipSpec(SIXTY, Fraction(4), _edges, SHORT_GAP_FRAMES),
    "40-stress": ClipSpec(SIXTY, PERIOD_25_MS, _whole_capture, first_slot=Fraction(-1, 2)),
    "60-stress-uneven": ClipSpec(SIXTY, Fraction(1), _uneven),
    "50-stress": ClipSpec(Fraction(50), Fraction(1), _display),
    "120-stress": ClipSpec(Fraction(120), Fraction(1), _display),
    "144-stress": ClipSpec(Fraction(144), Fraction(1), _display),
}


@functools.cache
def clip(name: str, parameters: TimingParameters) -> StressClip:
    """The stress clip `name`. Raises ValueError for a name that has no script and for another display than the script's."""
    spec = CLIPS.get(name)
    if spec is None:
        raise ValueError(f"no stress clip named {name!r}: use one of {', '.join(CLIPS)}")
    if parameters.fps != spec.fps:
        raise ValueError(f"{name} is scripted for a {float(spec.fps):g} Hz display, not {float(parameters.fps):g}")
    script = _Script(spec.fps, spec.interval, spec.interval, spec.gap, spec.settle, slot=spec.first_slot)
    spec.script(script)
    return script.finish(parameters, spec.seam_dropped)


def clip_seconds(name: str) -> Fraction:
    """How long the stress clip `name` is."""
    spec = CLIPS[name]
    return len(clip(name, TimingParameters(fps=spec.fps)).screen) / spec.fps
