"""Simulate a busy stretch in the videos (modes 60-busy-full-rate and 60-busy-swappy): a few seconds in which the frames take longer
than a refresh about half the time, with calm stretches before and after, and a game that either stays at full rate or adapts its
swap interval the way Android's Frame Pacing library (Swappy) does.

Every frame starts when the previous one is shown and takes its render time; it targets the refresh its swap interval after the
previous one, and is shown there, or at the first refresh after it is done when it is done too late (a missed frame). Its animation
time is the refresh it targets, the moment it is meant for, as with the vsync timer: a frame that is shown later shows a moment
already past.

Swappy's rule (games-frame-pacing/common/SwappyCommon.cpp, SwappyCommon::updateSwapInterval): it keeps the frames of the last 2 s;
with more than 2 s of them, when more than 10 % missed their deadline it slows down, to the swap interval the average frame time
plus 1 ms needs (at least one more), and when none missed and the average frame time plus 1 ms fits one interval shorter with
1 ms to spare, it speeds up again. After every change it starts a new 2 s window. It slows down only while its interval is within
its slowest (50 ms, SwappyCommon.h: "20FPS"). Its pipelining is left out.

The load comes in stages: the video's is one busy stretch at 60 Hz; the adaptive rate chart also shows one at 100 Hz that rises
and falls in steps, each needing one more refresh.

A clip is simulated twice and the second pass kept, so it starts in the state it ends in and loops.
"""

import math
from collections import deque
from dataclasses import dataclass
from fractions import Fraction

from pcg32 import Pcg32

POLICIES = ("full-rate", "swappy")
# The busy stretch, as a share of the clip, and the render times (ms) in and outside it
BUSY = (Fraction(3, 16), Fraction(11, 16))  # 1.5 to 5.5 s of an 8 s clip
CALM_MS = (9.0, 13.0)
BUSY_MS = (12.0, 24.0)
# A stage of the load: from, to (shares of the clip) and its render times (ms)
type Stage = tuple[Fraction, Fraction, tuple[float, float]]
STAGES: tuple[Stage, ...] = ((BUSY[0], BUSY[1], BUSY_MS),)
# Swappy's constants (SwappyCommon.h)
WINDOW_S = 2.0
DROP_THRESHOLD = 10  # %
FRAME_MARGIN_MS = 1.0
SLOWEST_MS = 50.0  # mAutoSwapIntervalThreshold: it slows down no further once its interval is longer (plus the margin)


@dataclass
class _Window:
    """Swappy's FrameDurations: the frames of the last 2 s, as (when shown, render time in ms, missed)."""

    frames: deque[tuple[float, float, bool]]

    def add(self, now: float, render_ms: float, missed: bool) -> None:
        self.frames.append((now, render_ms, missed))
        while len(self.frames) >= 2 and now - self.frames[1][0] > WINDOW_S:
            _ = self.frames.popleft()

    def enough(self) -> bool:
        return bool(self.frames) and self.frames[-1][0] - self.frames[0][0] > WINDOW_S

    def average_ms(self) -> float:
        return sum(render for _, render, _ in self.frames) / len(self.frames)

    def missed_percent(self) -> int:
        return round(sum(missed for _, _, missed in self.frames) * 100 / len(self.frames))


def _intervals_needed(frame_ms: float, refresh_ms: float) -> int:
    """Swappy's calculateSwapInterval: the refreshes a frame of this length needs."""
    return max(1, math.ceil(frame_ms / refresh_ms - 1e-6))


def title(policy: str) -> str:
    return "a busy stretch at full rate" if policy == "full-rate" else "a busy stretch, adapting like Swappy"


@dataclass(frozen=True)
class Record:
    """One frame of the clip: the refresh it targets and the one it is shown on, its render time, whether it missed, the swap
    interval it was paced at, and what the rule saw in its 2 s window after it (None until the window holds 2 s): the share of
    frames that missed and their average render time, and the change it made, if any ("slower" or "faster")."""

    target: int
    shown: int
    render_ms: float
    missed: bool
    interval: int
    missed_percent: int | None = None
    average_ms: float | None = None
    change: str | None = None


def records(policy: str, refreshes: int, fps: Fraction, stages: tuple[Stage, ...] = STAGES, calm: tuple[float, float] = CALM_MS) -> list[Record]:
    """The frames of a clip of `refreshes` refreshes through the load's `stages` (`calm` outside them), for a game at full rate
    or adapting like Swappy."""
    return [frame for frame in with_lead(policy, refreshes, fps, stages, calm) if frame.shown >= 0]


def with_lead(policy: str, refreshes: int, fps: Fraction, stages: tuple[Stage, ...] = STAGES, calm: tuple[float, float] = CALM_MS) -> list[Record]:
    """The clip's frames with the ones of the pass before it in front (shown on refreshes below 0): what the rule's window held
    when the clip starts, for drawing it."""
    if policy not in POLICIES:
        raise ValueError(f"no busy stretch policy named {policy!r}: use {' or '.join(POLICIES)}")
    refresh_ms = 1000 / float(fps)
    generator = Pcg32.from_text("busy stretch")
    interval, window = 1, _Window(deque())
    shown = 0
    kept: list[Record] = []
    while shown < 2 * refreshes:
        phase = Fraction(shown % refreshes, refreshes)
        low, high = next((times for start, end, times in stages if start <= phase < end), calm)
        render_ms = low + (high - low) * generator.random()
        # Started when the previous frame was shown; shown at its target, or at the first refresh after it is done
        target = shown + interval
        done = shown + render_ms / refresh_ms
        at = max(target, math.ceil(done - 1e-9))
        missed = at > target
        shown = at
        paced, seen, average, change = interval, None, None, None
        if policy == "swappy":
            window.add(at / float(fps), render_ms, missed)
            if window.enough():
                seen, average = window.missed_percent(), window.average_ms()
                frame_ms = average + FRAME_MARGIN_MS
                if seen > DROP_THRESHOLD and refresh_ms * interval <= SLOWEST_MS + FRAME_MARGIN_MS:
                    interval, change = max(interval + 1, _intervals_needed(frame_ms, refresh_ms)), "slower"
                elif seen == 0 and interval > 1 and frame_ms < refresh_ms * (interval - 1) - FRAME_MARGIN_MS:
                    interval, change = max(1, _intervals_needed(frame_ms, refresh_ms)), "faster"
                if change:
                    window = _Window(deque())
        if at < 2 * refreshes:
            kept.append(Record(target - refreshes, at - refreshes, render_ms, missed, paced, seen, average, change))
    return kept


def intervals(policy: str, refreshes: int, fps: Fraction) -> list[int]:
    """The swap interval each frame of the clip is paced at, in refreshes: the rate the game aims for is the refresh rate divided by
    it (full rate, then half rate through the busy stretch when it adapts)."""
    return [frame.interval for frame in records(policy, refreshes, fps)]


def schedule(policy: str, refreshes: int, fps: Fraction) -> tuple[list[int], list[Fraction]]:
    """The frames of a clip of `refreshes` refreshes through the busy stretch: the refresh each is shown on and its animation time
    (s), the refresh it targets."""
    frames = records(policy, refreshes, fps)
    return [frame.shown for frame in frames], [Fraction(frame.target) / fps for frame in frames]
