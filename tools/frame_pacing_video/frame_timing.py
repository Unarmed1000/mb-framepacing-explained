"""Simulate a game's frame loop on a plain vsync display: when each frame is shown, and which animation time it shows.

Back to basics: the game only has vsync. It has no presentation timestamps and cannot ask when a frame was shown; it only blocks
in Present and reads its own clock. Its loop, per frame:

    Present(previous frame)  blocks until that frame is flipped on screen at a vsync (double buffering)
    now = wall clock         a high-precision timer (QueryPerformanceCounter, steady_clock), read when the thread runs again:
                             after the scheduler wakes it up and after any work that comes first, so a little after the flip
    dt = now - last          the naive timer: x += speed * dt
    render                   always fits in the frame time here, so every frame makes its vsync (no frame is late)
    Present(frame)           shown at the next allowed vsync, one swap interval after the previous frame

Timers (how the animation time is found):
- ideal: exactly the frame's display time, what a perfect, display-matched timer would give; the reference.
- naive: the wall clock reading, dt = now - last summed from the first frame. Each frame's animation time is off by how late its
  clock was read, compared to the first frame.

Wake-up noise (how long after the flip the clock is read), in the naive loop:
- a +-N ms window (1ms, 4ms, ...): read at a random point of a window 2 x N ms wide, so each frame's animation time is up to N ms
  off the average and dt varies by up to +-2 x N ms: 1ms is small but visible, 4ms a bad case. With -every-Ns (e.g.
  60-naive-5ms-every-1s) only a burst of frames in the middle of every N seconds reads the clock off its average (JITTER_BURST_FRAMES,
  or as many as -Kf says: 60-naive-5ms-24f-every-1s), and every other frame exactly at it: the jitter in the middle of each move of the box, where it shows most
- system load (light, typical, heavy): how late the thread wakes depends on what else runs (background work, driver interrupts,
  power states). Usually a short wake-up (0 to 0.3 ms), and in some frames a longer one. By default a demonstration profile: a
  timing error in most frames (TimingParameters.demo_load_share, 95 %), the loads differing in how bad the errors are
  (DEMO_LOAD_MIX):
    light    all about 1 ms
    typical  half about 1 ms, half up to 2 ms
    heavy    90 % up to 2 ms, 10 % spikes of 4-8 ms (none about 1 ms)
  and the realistic profile (light-realistic, typical-realistic, heavy-realistic; LOAD_RANGES), where the errors are rare:
    light    3 % about 1 ms, 1 % up to 2 ms                          an idle system, only the game
    typical  7 % about 1 ms, 2 % up to 2 ms                          a normal gaming PC
    heavy    12 % about 1 ms, 6 % up to 2 ms, 2 % spikes of 4-8 ms   background load
  (Unity measured 6.854, 7.423 and 6.691 ms at a steady 144 Hz, whose frames are 6.944 ms)
- synthetic: a made-up pattern for teaching the metric: alternating, random or mixed within +-amount

Everything is exact (Fraction seconds, noise drawn in whole microseconds) and deterministic: the random draws come from our own PCG32
generator (pcg32.py), seeded from the SHA-256 of a text naming the mode and clip length, so the same clip always gets the same timing, in
any Python version, and the draws can be reproduced in any language.
"""

import functools
import re
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

from pcg32 import Pcg32

MICROSECOND = Fraction(1, 1_000_000)

# Synthetic noise: consecutive errors differ by at least this share of the amount, so no animation time step is exactly the frame
# time; the patterns: mixed (the clip's quarters alternate between the two others), alternating +1, -1, ... (the largest animation
# error), or random
JITTER_MIN_CHANGE = Fraction(1, 5)
JITTER_PATTERNS = ("mixed", "alternating", "runs", "random")
MIXED_PATTERNS = ("alternating", "runs", "random", "runs")
# Runs: how many frames the error stays on one side before it moves to the other
RUN_FRAMES = (4, 10)
# Realistic system load, second half of a clip: how many frames in a row a late wake-up lasts while something else keeps using the
# CPU (the first half has single late frames; the demo profile has single frames all through)
LOAD_SPELL_FRAMES = (3, 10)
# The demo profile shows its largest range (heavy load: a spike) within this many seconds from the start, where a viewer looks first
DEMO_LARGEST_WITHIN = 2
# A window's -every-Ns burst, unless its name gives the length: as many frames as the delta time jitter diagram shows (A to H)
JITTER_BURST_FRAMES = 8


class Timer(StrEnum):
    """How the animation time is found: the frame's display time (ideal), or the wall clock read after Present (naive)."""

    IDEAL = "ideal"
    NAIVE = "naive"


class Noise(StrEnum):
    """How late the naive loop reads the wall clock after a flip."""

    WINDOW = "window"
    LIGHT = "light"
    TYPICAL = "typical"
    HEAVY = "heavy"
    SYNTHETIC = "synthetic"


# System load, realistic profile: the longer wake-ups after the usual short one, as (share of frames, from, to) in seconds
LOAD_RANGES: dict[Noise, tuple[tuple[Fraction, Fraction, Fraction], ...]] = {
    Noise.LIGHT: ((Fraction(3, 100), Fraction(8, 10_000), Fraction(12, 10_000)), (Fraction(1, 100), Fraction(17, 10_000), Fraction(2, 1000))),
    Noise.TYPICAL: ((Fraction(7, 100), Fraction(8, 10_000), Fraction(12, 10_000)), (Fraction(2, 100), Fraction(17, 10_000), Fraction(2, 1000))),
    Noise.HEAVY: (
        (Fraction(12, 100), Fraction(8, 10_000), Fraction(12, 10_000)),
        (Fraction(6, 100), Fraction(17, 10_000), Fraction(2, 1000)),
        (Fraction(2, 100), Fraction(4, 1000), Fraction(8, 1000)),
    ),
}
# System load, demo profile (the default): how its late and early frames are split over the ranges of LOAD_RANGES, so the loads differ in how bad the errors
# are rather than how often (the realistic light and typical mixes are nearly the same)
DEMO_LOAD_MIX: dict[Noise, tuple[Fraction, ...]] = {
    Noise.LIGHT: (Fraction(1), Fraction(0)),
    Noise.TYPICAL: (Fraction(1, 2), Fraction(1, 2)),
    Noise.HEAVY: (Fraction(0), Fraction(9, 10), Fraction(1, 10)),
}


@dataclass(frozen=True)
class FrameMode:
    """How a box is updated: its rate (frames per second on the display), its timer and, for the naive timer, its wake-up noise."""

    name: str
    rate: int
    timer: Timer = Timer.IDEAL
    noise: Noise | None = None
    # A window noise's half width (seconds): the clock is read up to this much off its average moment
    window: Fraction | None = None
    # A system load at its realistic rates (LOAD_RANGES) instead of the demo profile (errors in most frames)
    realistic: bool = False
    # A replayed timing diagram (diagram_replay): its frames, late or held exactly as the diagram shows them, repeated to fill the
    # clip, every `every` seconds when set
    diagram: str | None = None
    # Diagram: how often it plays; window: how often a burst of jittered frames comes, the frames between them exact
    every: Fraction | None = None
    # Diagram: how many times it plays per `every` period
    times: int = 1
    # A window's burst: how many frames in a row jitter, every `every` seconds
    burst: int | None = None
    # A busy stretch (adaptive_rate): the policy, full-rate or swappy
    busy: str | None = None


MODE_PATTERN = re.compile(
    r"(?P<rate>[1-9][0-9]*)(?:-naive-(?:(?P<load>light|typical|heavy)(?P<realistic>-realistic)?|(?P<synthetic>synthetic)|(?P<ms>[0-9]+(?:\.[0-9]+)?)ms(?:(?:-(?P<burst>[1-9][0-9]*)f)?-every-(?P<burst_every>[0-9]+(?:\.[0-9]+)?)s)?)"
    + r"|-diagram-(?P<diagram>[a-z]+(?:-[a-z]+)*?)(?:(?:-(?P<times>[1-9])x)?-every-(?P<every>[0-9]+(?:\.[0-9]+)?)s)?"
    + r"|-busy-(?P<busy>full-rate|swappy))?"
)
NOISE_NAMES = "a system load (light, typical, heavy: errors in most frames; -realistic, e.g. typical-realistic: rare), a window like 1ms or 4ms, or synthetic"


def parse_mode(name: str) -> FrameMode:
    """A mode from its name: RATE (the ideal timer, e.g. 60), RATE-naive-NOISE (e.g. 60-naive-1ms, 60-naive-typical; a window in
    bursts: 60-naive-5ms-every-1s, 60-naive-5ms-24f-every-1s), RATE-diagram-NAME[[-Kx]-every-Ns] (a replayed timing diagram, e.g.
    60-diagram-slow-frames) or RATE-busy-POLICY (a busy stretch at full rate or adapting like Swappy: 60-busy-full-rate,
    60-busy-swappy)."""
    match = MODE_PATTERN.fullmatch(name)
    if match is None or any(match[group] is not None and Fraction(match[group]) <= 0 for group in ("ms", "every", "burst_every")):
        raise ValueError(
            f"'{name}' is not a mode: use RATE (ideal timer, e.g. 60), RATE-naive-NOISE with NOISE {NOISE_NAMES} (a window in "
            + "bursts: 5ms-every-1s or 5ms-24f-every-1s), RATE-diagram-NAME[[-Kx]-every-Ns] (a timing diagram, e.g. 60-diagram-slow-frames) "
            + "or RATE-busy-POLICY (60-busy-full-rate, 60-busy-swappy)"
        )
    rate = int(match["rate"])
    if match["busy"] is not None:
        return FrameMode(name, rate, busy=match["busy"])
    if match["diagram"] is not None:
        every = None if match["every"] is None else Fraction(match["every"])
        return FrameMode(name, rate, diagram=match["diagram"], every=every, times=1 if match["times"] is None else int(match["times"]))
    if match["ms"] is not None:
        if match["burst_every"] is None:
            return FrameMode(name, rate, Timer.NAIVE, Noise.WINDOW, Fraction(match["ms"]) / 1000)
        burst = JITTER_BURST_FRAMES if match["burst"] is None else int(match["burst"])
        return FrameMode(name, rate, Timer.NAIVE, Noise.WINDOW, Fraction(match["ms"]) / 1000, every=Fraction(match["burst_every"]), burst=burst)
    noise = match["load"] or match["synthetic"]
    return FrameMode(name, rate, Timer.NAIVE if noise else Timer.IDEAL, Noise(noise) if noise else None, realistic=match["realistic"] is not None)


@dataclass(frozen=True)
class TimingParameters:
    """The loop's parameters, in seconds."""

    fps: Fraction = Fraction(60)
    # System load: the work before the clock is read (input, OS messages), a constant latency, plus the usual noise on top, from, to;
    # the loads' longer ranges (LOAD_RANGES) make the read that much later, or up to 2 ms that much earlier when the work is shorter
    base: Fraction = Fraction(2, 1000)
    noise: tuple[Fraction, Fraction] = (Fraction(0), Fraction(3, 10_000))
    # Rendering work as a share of the frame time; with the largest wake-up it must fit, so every frame makes its vsync
    frame_cost: Fraction = Fraction(3, 10)
    # The loads' demo profile (light, typical, heavy): the share of frames that read the clock late or early, split over the ranges
    # by DEMO_LOAD_MIX; the realistic profile (-realistic) keeps the shares of LOAD_RANGES (4, 9 and 20 %)
    demo_load_share: Fraction = Fraction(19, 20)
    # Synthetic noise: its amount (+-) and pattern
    synthetic: Fraction = Fraction(1, 1000)
    synthetic_pattern: str = "mixed"

    def largest_wake(self, mode: FrameMode) -> Fraction:
        """The latest a frame of this mode can read the clock after its flip."""
        match mode.noise:
            case None:
                return Fraction(0)
            case Noise.WINDOW:
                return 2 * (mode.window or Fraction(0))
            case Noise.LIGHT | Noise.TYPICAL | Noise.HEAVY:
                return self.base + max([self.noise[1], *(high for _, _, high in LOAD_RANGES[mode.noise])])
            case Noise.SYNTHETIC:
                return 2 * self.synthetic

    def load_ranges(self, mode: FrameMode) -> list[tuple[Fraction, Fraction, Fraction]]:
        """A load mode's longer wake-ups as (share of frames, from, to): the demo profile's demo_load_share split by DEMO_LOAD_MIX, or realistic."""
        load = mode.noise
        assert load is not None and load in LOAD_RANGES, mode.name
        if mode.realistic:
            return list(LOAD_RANGES[load])
        return [(self.demo_load_share * mix, low, high) for mix, (_, low, high) in zip(DEMO_LOAD_MIX[load], LOAD_RANGES[load], strict=True)]


@dataclass(frozen=True)
class SimulatedFrames:
    """The frames of one clip, in order: the output refresh each is flipped on, the wall clock reading of the naive loop (seconds;
    the first frame is shown at 0), and the animation time each shows."""

    flips: tuple[int, ...]
    samples: tuple[Fraction, ...]
    animation: tuple[Fraction, ...]


def swap_interval(mode: FrameMode, fps: Fraction) -> int:
    """Refreshes per frame (1, 2, 3 for 60, 30, 20 Hz at 60 fps). Raises ValueError unless it is whole."""
    interval = fps / mode.rate
    if interval.denominator != 1:
        raise ValueError(f"{float(fps):g} fps is not a whole multiple of {mode.rate} Hz, so {mode.name} would not be evenly paced")
    return interval.numerator


def validate(mode: FrameMode, parameters: TimingParameters) -> None:
    """Raise ValueError unless every frame of this mode makes its vsync and its animation time never runs backwards."""
    frame_time = Fraction(swap_interval(mode, parameters.fps)) / parameters.fps
    low, high = parameters.noise
    if not 0 <= low <= high:
        raise ValueError("the noise range must be from a smaller to a larger delay, not below 0")
    if not 0 <= parameters.frame_cost < 1:
        raise ValueError(f"the frame cost must be at least 0 and less than 1 (a share of the frame time), got {float(parameters.frame_cost):g}")
    if not 0 <= parameters.demo_load_share < 1:
        raise ValueError(f"the demo load share must be at least 0 and less than 1 (some frames on time), got {float(parameters.demo_load_share):g}")
    if mode.noise is Noise.SYNTHETIC:
        if parameters.synthetic_pattern not in JITTER_PATTERNS:
            raise ValueError(f"unknown jitter pattern {parameters.synthetic_pattern!r}: use {' or '.join(JITTER_PATTERNS)}")
        if not 0 <= 2 * parameters.synthetic < 1 / Fraction(mode.rate):
            raise ValueError(f"the synthetic jitter of {format_ms(parameters.synthetic)} must be less than half the {mode.rate} Hz frame time")
    if mode.diagram is not None:
        from diagram_replay import pattern  # noqa: PLC0415  (only diagram modes need the diagrams)

        _ = pattern(mode.diagram)
    busy = parameters.largest_wake(mode) + parameters.frame_cost * frame_time
    if busy >= frame_time:
        raise ValueError(
            f"{mode.name} would miss a vsync: a wake-up of up to {format_ms(parameters.largest_wake(mode))} plus rendering "
            + f"({format_ms(parameters.frame_cost * frame_time)}) does not fit in the {format_ms(frame_time)} frame time"
        )


def format_ms(seconds: Fraction) -> str:
    return f"{float(seconds * 1000):g} ms"


def jitter_kinds(count: int, pattern: str) -> list[str]:
    """The synthetic pattern of each of `count` frames: one for the whole clip, or for mixed, MIXED_PATTERNS over equal parts of it."""
    if pattern != "mixed":
        return [pattern] * count
    return [MIXED_PATTERNS[index * len(MIXED_PATTERNS) // count] for index in range(count)]


@functools.cache
def jitter_offsets(rate: int, count: int, pattern: str = "mixed") -> tuple[Fraction, ...]:
    """Synthetic errors of `count` frames, in units of the amount: between -1 and 1, the largest exactly +-1, and each at least
    JITTER_MIN_CHANGE from the one before (also from the last to the first, as the clip loops). Alternating frames flip between +1
    and -1 (starting opposite to the error before them), so their animation error is twice the amount; runs stay on one side (half
    to the full amount) for RUN_FRAMES frames, then on the other side; random frames are anywhere. The draws come from a sequence that
    is deterministic per rate and count."""
    kinds = jitter_kinds(count, pattern)
    generator = Pcg32.from_text(f"animation jitter {rate} Hz, {count} frames")
    offsets: list[Fraction] = []
    side, run_left = 1, 0
    for index, kind in enumerate(kinds):
        previous = offsets[-1] if offsets else None
        if kind == "alternating":
            offsets.append(Fraction(1) if previous is None or previous < 0 else Fraction(-1))
            continue
        low, high = -100, 100
        if kind == "runs":
            if run_left == 0 or index == 0 or kinds[index - 1] != "runs":
                # A new run, on the other side than the error before it
                side = -1 if previous is not None and previous > 0 else 1
                run_left = generator.randint(*RUN_FRAMES)
            run_left -= 1
            low, high = (50, 100) if side > 0 else (-100, -50)
        tries = 0
        while True:
            offset = Fraction(generator.randint(low, high), 100)
            tries += 1
            if tries == 100:
                # A run's range can hold no value far enough from both the previous and (at the loop point) the first error: the
                # whole range always does
                low, high = -100, 100
            if previous is not None and abs(offset - previous) < JITTER_MIN_CHANGE:
                continue
            if index == count - 1 and count > 1 and abs(offset - offsets[0]) < JITTER_MIN_CHANGE:
                continue
            break
        offsets.append(offset)
    if count > 1 and abs(offsets[-1] - offsets[0]) < JITTER_MIN_CHANGE:
        # An alternating end meets an equal start as the clip loops: 0 is a full amount away from both of its +-1 neighbours
        offsets[-1] = Fraction(0)
    if pattern in ("random", "runs"):
        # Moving the largest error out to exactly +-1 only moves it further from its neighbours (the others always reach +-1)
        largest = max(range(count), key=lambda index: abs(offsets[index]))
        offsets[largest] = Fraction(1 if offsets[largest] >= 0 else -1)
    return tuple(offsets)


def burst_frames(mode: FrameMode, count: int) -> list[int]:
    """The frames of a window's -every-Ns bursts among `count` frames: its burst length in the middle of every period, where the
    box is in the middle of a move (a clip starts in the middle of a rest). Raises ValueError when they do not fit the clip."""
    assert mode.every is not None and mode.burst is not None, mode.name
    burst = mode.burst
    period = mode.every * mode.rate
    if period.denominator != 1 or period < burst or count % period:
        raise ValueError(f"{mode.name}: a burst of {burst} frames every {float(mode.every):g} s does not fit a clip of {count} frames")
    offset = (int(period) - burst) // 2
    return [start + offset + index for start in range(0, count, int(period)) for index in range(burst)]


def _microseconds(generator: Pcg32, low: Fraction, high: Fraction) -> Fraction:
    """A delay between `low` and `high` in whole microseconds, evenly."""
    return Fraction(generator.randint(round(low / MICROSECOND), round(high / MICROSECOND)), 1_000_000)


def wake_delays(mode: FrameMode, parameters: TimingParameters, count: int) -> list[Fraction]:
    """How long after its flip each of `count` frames reads the clock (the frame before the first one is flipped at -frame time)."""
    if mode.noise is None:
        return [Fraction(0)] * count
    if mode.noise is Noise.SYNTHETIC:
        # The amount itself is a constant latency; only the pattern around it shows
        amount = parameters.synthetic
        return [amount * (1 + offset) for offset in jitter_offsets(mode.rate, count, parameters.synthetic_pattern)]
    if mode.noise is Noise.WINDOW:
        # Within +-window of the window's middle, following the jitter pattern (mixed: alternating and random quarters); in bursts,
        # the pattern runs through the bursts' frames only, and every other frame reads the clock at the middle
        window = mode.window or Fraction(0)
        jittered = range(count) if mode.every is None else burst_frames(mode, count)
        offsets = dict(zip(jittered, jitter_offsets(mode.rate, len(jittered), parameters.synthetic_pattern), strict=True))
        return [window * (1 + offsets.get(index, Fraction(0))) for index in range(count)]
    generator = Pcg32.from_text(f"wake-up {mode.noise.value}{'' if mode.realistic else ' demo'}, {mode.rate} Hz, {count} frames")
    delays: list[Fraction] = []
    # Realistic: the first half of the clip has single late frames, each drawn on its own; the second half has spells, several
    # frames in a row while something else uses the CPU (LOAD_SPELL_FRAMES). A spell starts with its range's share of frames divided
    # by the average spell length, so both halves have the same share of late frames. The demo profile draws every frame on its own
    # for the whole clip: within a spell the error only shows at its ends, so its second half would look much lighter
    # Each event goes either way (sign), except the ranges beyond the base, which can only be late (CPU contention only delays)
    average_spell = sum(LOAD_SPELL_FRAMES) / 2
    ranges = parameters.load_ranges(mode)
    # A new spell cannot start during one, so a range's chance per free frame is its share / (length x (1 - total share) + total)
    total = float(sum(share for share, _, _ in ranges))
    spread = average_spell * (1 - total) + total
    spells_from = count // 2 if mode.realistic else count
    spell: tuple[Fraction, Fraction] | None = None
    spell_left, sign = 0, 1
    for index in range(count):
        if spell is None:
            spells = index >= spells_from
            chance = spread if spells else 1
            draw = generator.random()
            for share, low, high in ranges:
                if draw < float(share) / chance:
                    spell, spell_left = (low, high), generator.randint(*LOAD_SPELL_FRAMES) if spells else 1
                    sign = generator.choice((1, -1)) if high <= parameters.base else 1
                    break
                draw -= float(share) / chance
        if spell is None:
            delays.append(parameters.base + _microseconds(generator, *parameters.noise))
            continue
        delays.append(parameters.base + sign * _microseconds(generator, *spell))
        spell_left -= 1
        if spell_left == 0:
            spell = None
    if not mode.realistic:
        _largest_early(
            delays, [(low, high) for share, low, high in ranges if share > 0], min(count, DEMO_LARGEST_WITHIN * mode.rate), parameters.base, generator
        )
    return delays


def _largest_early(delays: list[Fraction], ranges: list[tuple[Fraction, Fraction]], early: int, base: Fraction, generator: Pcg32) -> None:
    """Make sure the largest of the ranges occurs in the first `early` frames: if the draws put none there, one frame there gets it
    (going either way when it is within the base, like the draws, else late)."""
    if not ranges or early <= 0:
        return
    low, high = ranges[-1]
    if any(low <= abs(delay - base) <= high for delay in delays[:early]):
        return
    index = generator.randint(0, early - 1)
    sign = generator.choice((1, -1)) if high <= base else 1
    delays[index] = base + sign * _microseconds(generator, low, high)


@functools.cache
def simulate(mode: FrameMode, parameters: TimingParameters, refreshes: int) -> SimulatedFrames:
    """The loop over a clip of `refreshes` output refreshes. Every frame makes its vsync, so frame n is flipped on refresh n x the
    swap interval; it reads the clock the wake-up delay after the previous flip. The naive timer's animation time is that reading
    minus the average delay: a constant delay is only latency and cannot be seen, so each frame is off by how much its delay
    differs from the average, ahead or behind. The clip loops: the frame after the last is the first frame of the next loop, one
    clip later."""
    validate(mode, parameters)
    interval = swap_interval(mode, parameters.fps)
    if refreshes % interval:
        raise ValueError(f"{refreshes} refreshes are not a whole number of {mode.rate} Hz frames")
    if mode.busy is not None:
        from adaptive_rate import schedule as busy_schedule  # noqa: PLC0415

        flips, animation = busy_schedule(mode.busy, refreshes, parameters.fps)
        return SimulatedFrames(tuple(flips), tuple(Fraction(flip) / parameters.fps for flip in flips), tuple(animation))
    if mode.diagram is not None:
        from diagram_replay import schedule  # noqa: PLC0415

        flips, animation = schedule(mode.diagram, mode.every, refreshes, interval, parameters.fps, mode.times)
        # The perfect timer reads no clock: each frame's sample is its own flip
        return SimulatedFrames(tuple(flips), tuple(Fraction(flip) / parameters.fps for flip in flips), tuple(animation))
    count = refreshes // interval
    frame_time = Fraction(interval) / parameters.fps
    wakes = wake_delays(mode, parameters, count)
    flips = tuple(index * interval for index in range(count))
    samples = tuple((index - 1) * frame_time + wake for index, wake in enumerate(wakes))
    if mode.timer is Timer.IDEAL:
        animation = tuple(index * frame_time for index in range(count))
    else:
        # dt = now - last, from a clock whose constant latency (the average delay, one frame before the flip) is taken out; in
        # bursts, the delay of the exact frames between them, so only the bursts are off
        average = (mode.window or Fraction(0)) if mode.every is not None else sum(wakes, Fraction(0)) / count
        latency = average - frame_time
        animation = tuple(sample - latency for sample in samples)
    return SimulatedFrames(flips, samples, animation)


def delta_times(frames: SimulatedFrames, duration: Fraction) -> list[Fraction]:
    """The dt each frame's animation advanced by (the first frame follows the last one of the previous loop)."""
    animation = frames.animation
    return [animation[0] - (animation[-1] - duration)] + [b - a for a, b in zip(animation, animation[1:], strict=False)]


def describe(mode: FrameMode, parameters: TimingParameters) -> str:
    """The text written next to a box, for example "60 Hz naive timer, heavy load"."""
    if mode.busy is not None:
        from adaptive_rate import title as busy_title  # noqa: PLC0415

        return f"{mode.rate} Hz, {busy_title(mode.busy)}"
    if mode.diagram is not None:
        from diagram_replay import title  # noqa: PLC0415

        if mode.every is None:
            every = ""
        elif mode.times == 1:
            every = f", every {float(mode.every):g} s"
        else:
            every = f", {mode.times} times {'a second' if mode.every == 1 else f'every {float(mode.every):g} s'}"
        return f"{mode.rate} Hz, {title(mode.diagram)} (as the diagram{every})"
    if mode.timer is Timer.IDEAL:
        return f"{mode.rate} Hz ideal timer"
    if mode.noise is Noise.SYNTHETIC:
        return f"{mode.rate} Hz naive timer, synthetic ±{format_ms(parameters.synthetic)} {parameters.synthetic_pattern}"
    if mode.noise is Noise.WINDOW:
        bursts = "" if mode.every is None else f", {mode.burst} frames every {float(mode.every):g} s"
        return f"{mode.rate} Hz naive timer, ±{format_ms(mode.window or Fraction(0))} {parameters.synthetic_pattern}{bursts}"
    return f"{mode.rate} Hz naive timer, {mode.noise} load{' (realistic)' if mode.realistic else ''}"
