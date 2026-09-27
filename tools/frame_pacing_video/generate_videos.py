#!/usr/bin/env python3
"""Generate the frame pacing comparison videos.

Every 1280x720 video has two halves: at the normal and fast speeds a box moving side to side along the same eased (sine in-out)
path, resting briefly at both ends; at the ui speeds a row of identical boxes, like a list in an interface, scrolling right to
left at constant speed and fading in and out at the edges. The top half is updated with one pacing mode and the bottom half with
another, so a viewer can compare them. With --scene row the normal and fast clips show a row too, paging one page (4 boxes) to the
left and back.

--scene follow is a different setup, after Unity's Time.deltaTime demo: stacks of boxes in the middle between two fixed lines, each
box with its own mode, and a camera that follows the ideal motion, so an ideal box stands still and a timing error is the only thing
that moves a box. By default three videos: the ideal timer with the naive timer under light, typical and heavy system load,
as a demo (errors in most frames) and realistic, and an extreme cases video with the naive timer in +-1, 2, 3 and 4 ms windows. The boxes move an eighth of the width per frame, an
illustration speed that makes a 1 ms error about 10 px. --slow-motion N [N ...] shows every refresh for N video frames, one video
per factor, in every scene (e.g. --slow-motion 1 10: real speed and 10 times slower).

The moving scene is laid out and drawn in virtual pixels (--pixel-size N: blocks of N x N video pixels on a fixed grid). Its canvas
is the video size divided by N, and the default layout follows the canvas, so the scene keeps its proportions at every grid size,
while the ui scroll speeds are in virtual pixels per second: on a coarser grid a timing error moves N times as many video pixels.
The divider and the labels are drawn at native 1:1 video pixels.

The timing comes from frame_timing.py, which simulates the game's loop on a plain vsync display (no presentation timestamps): after
Present returns, the loop reads a high-precision wall clock, moves the animation by dt = now - last, renders (always in time for the
next vsync) and presents. A mode is a rate and a timer (see the repository README for the terms, after Intel PresentMon):

- Ideal timer (60, 30, 20 Hz): every frame shows exactly its display time; the reference.
- Naive timer: the animation time is the wall clock reading minus its average delay, so every frame is off by how much later or
  sooner than usual the loop read the clock after the flip. Under system load (60-naive-light, -typical, -heavy) it is usually on
  time, and in some frames about 1 ms or up to 2 ms sooner or later or, under heavy load, 4-8 ms later. By default the loads are a
  demo profile: a timing error in 95 % of the frames (--demo-load-share), each drawn on its own, the loads differing in how bad:
  light about 1 ms, typical also 2 ms, heavy up to 2 ms and the spikes, the largest always within the first 2 s;
  60-naive-light-realistic, -typical-realistic, -heavy-realistic have the realistic rates, a few percent of the frames, single
  frames in the first half of the clip and spells of several frames in the second.
  In a +-N ms window (60-naive-1ms, 60-naive-4ms, ...) it follows the
  jitter pattern (--jitter-pattern: mixed goes through alternating, runs, random and runs over the clip); 60-naive-synthetic is the
  same pattern within +-1 ms (--jitter-ms) for teaching the metric. The random draws come from pcg32.py, so they never change.

Every clip is 8 s (--seconds), so every video shows the jitter profiles the same way. Boxes are drawn at sub-pixel positions (per
virtual pixel), so even small errors are not lost to rounding. Speeds: normal (2 round trips per clip, 1.9 s per move) and fast
(4, 0.9 s per move) show subtle effects on a slow object, starting and ending in the middle of a rest; the ui speeds show them in
real interface motion: a row scrolling at a constant 192, 288, 384 or 768 virtual px/s, which loops seamlessly because the row repeats
every box spacing. The default run makes every top/bottom pair of the ideal 60, 30 and 20 Hz modes and the light, typical and heavy load
naive modes at 60 and 30 Hz, at all six speeds (486 videos). Frames are streamed to FFmpeg and encoded as lossless H.264 (libx264 -qp 0, YUV 4:4:4, BT.709); there is no
lossy fallback. Videos are grouped in folders by scene (with -labels when labelled, -px4 on a 4 x 4 grid, -slow10 slowed down) and
speed, e.g. box/fast; each folder's manifest.json lists its clips with the animation error of each frame, as PresentMon computes
it.

Run from the repository's .venv (setup.cmd or ./setup.sh):
  python tools/frame_pacing_video/generate_videos.py [options]
README.md next to this file describes the options, the FFmpeg setup and the output.
"""

# argparse sets the attributes of Arguments (the typed command line) after construction
# pyright: reportUninitializedInstanceVariable=false

import argparse
import bisect
import contextlib
import functools
import itertools
import json
import os
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from math import ceil, cos, floor, pi
from pathlib import Path
from typing import IO, Protocol, cast

from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageFont

from frame_timing import JITTER_PATTERNS, FrameMode, SimulatedFrames, TimingParameters, describe, parse_mode, simulate
from frame_timing import validate as validate_timing

type Rgb = tuple[int, int, int]

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "out" / "frame_pacing_video"
DEFAULT_CONFIG = REPO_ROOT / "local.toml"
FFMPEG_ENVIRONMENT_VARIABLE = "MB_FFMPEG"
ENCODER = "libx264"
# Standard YUV rather than libx264rgb: players that ignore the RGB tag of an RGB stream show it in false colours (white as purple)
PIXEL_FORMAT = "yuv444p"
# --web: what browsers play, H.264 High with 4:2:0 chroma, near-lossless. The neutral grays have no colour, so 4:2:0 leaves them
# exact; only the anti-aliased edges and the labels lose a little chroma detail
WEB_PIXEL_FORMAT = "yuv420p"
WEB_CRF = 12
MANIFEST_NAME = "manifest.json"

# The modes of the default run: 60, 30 and 20 Hz with the ideal timer, then 60 and 30 Hz with the naive timer under light, typical
# and heavy system load (the demo profile: errors in most frames; 20 Hz only as the ideal reference). Opt-in: the realistic loads,
# 20 Hz with a load, the +-N ms windows and the synthetic patterns
MODES: tuple[FrameMode, ...] = (
    *(parse_mode(str(rate)) for rate in (60, 30, 20)),
    *(parse_mode(f"{rate}-naive-{load}") for load in ("light", "typical", "heavy") for rate in (60, 30)),
)


def format_number(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{float(value):.6g}"


@dataclass(frozen=True)
class Speed:
    """A motion speed: how many round trips of the eased back and forth motion fit in a clip (more is faster), or, for an interface
    scroll, a constant speed in virtual pixels per second of a row scrolling right to left. travel (virtual pixels) or travel_share
    (of the settings' travel) gives this speed its own path length, centred like the others (slow: a shorter path)."""

    name: str
    round_trips: int = 1
    scroll: Fraction | None = None
    travel: int | None = None
    travel_share: Fraction = Fraction(1)


# Interface scrolling: a row of items scrolling right to left at constant speed, in virtual pixels per second. With the default
# layout at pixel size 2 (48 px boxes, 96 apart) that is 2, 3, 4 and 8 items per second, like dragging, holding a key or
# flinging in a list; at pixel size 1 it is half as many, at 4 twice as many. On a coarser grid the same speed moves more video
# pixels, so a timing error shows as a larger movement.
UI_SCROLL = (Fraction(192), Fraction(288), Fraction(384), Fraction(768))
# The default virtual pixel size: 2 x 2 video pixels, so a timing error moves a box in steps a viewer on a large screen can see
DEFAULT_PIXEL_SIZE = 2
# Every clip's length: the jitter profiles are laid out over it (2 s per quarter of the mixed jitter pattern; for the realistic loads
# 4 s each of single late frames and late spells), so every video shows them the same way
CLIP_SECONDS = Fraction(8)


def ui_speed(scroll: Fraction) -> Speed:
    """A constant scroll of `scroll` virtual pixels per second, named by it (ui-384)."""
    return Speed(f"ui-{format_number(scroll)}", 1, scroll)


# The follow scene's default videos, each a stack of boxes: the ideal 60 Hz reference with the naive timer under the three system
# loads, as a demo (errors in most frames) and realistic, and an extreme cases video with the +-1 to +-4 ms windows (too much to watch
# for most people next to the others). A follow video shows one rate: its camera is updated at that rate, like the game's
FOLLOW_BOXES: tuple[FrameMode, ...] = tuple(parse_mode(name) for name in ("60", "60-naive-light", "60-naive-typical", "60-naive-heavy"))
FOLLOW_REALISTIC: tuple[FrameMode, ...] = tuple(
    parse_mode(name) for name in ("60", "60-naive-light-realistic", "60-naive-typical-realistic", "60-naive-heavy-realistic")
)
FOLLOW_EXTREME: tuple[FrameMode, ...] = tuple(parse_mode(name) for name in ("60", "60-naive-1ms", "60-naive-2ms", "60-naive-3ms", "60-naive-4ms"))
FOLLOW_STACKS: tuple[tuple[str, tuple[FrameMode, ...]], ...] = (("", FOLLOW_BOXES), ("realistic", FOLLOW_REALISTIC), ("extreme", FOLLOW_EXTREME))


@dataclass(frozen=True)
class Settings:
    top: tuple[FrameMode, ...] = MODES
    bottom: tuple[FrameMode, ...] = MODES
    # An exact list of top/bottom pairs instead of every top x bottom pair (--pairs); empty: every pair
    pairs: tuple[tuple[FrameMode, FrameMode], ...] = ()
    # Encode for browsers (--web): H.264 High 4:2:0, near-lossless, instead of lossless 4:4:4
    web: bool = False
    speeds: tuple[Speed, ...] = (Speed("normal", 2), Speed("fast", 4), *(ui_speed(scroll) for scroll in UI_SCROLL))
    # Video size in video pixels
    width: int = 1280
    height: int = 720
    # Virtual pixel size: the moving scene is laid out and drawn in virtual pixels of N x N video pixels (1: native) on a canvas of
    # width / N x height / N, with sub-pixel blending per virtual pixel. The default layout follows the canvas, so the scene keeps
    # its proportions at every size. The divider and labels are drawn in video pixels (1:1).
    pixel_size: int = DEFAULT_PIXEL_SIZE
    fps: Fraction = Fraction(60)
    # Every clip's length in seconds
    seconds: Fraction = CLIP_SECONDS
    # Seconds the box rests at each end of its travel (not affected by the speed; the ui scroll never rests)
    settle: Fraction = Fraction(1, 10)
    # Sine ease-in-out at both ends of the travel; False: constant speed
    easing: bool = True
    # The naive loop (frame_timing): the usual short wake-up delay after a flip, the rendering
    # work as a share of the frame time, and the synthetic pattern's amount and kind
    wake_noise: tuple[Fraction, Fraction] = (Fraction(0), Fraction(3, 10_000))
    frame_cost: Fraction = Fraction(3, 10)
    # The loads' demo profile (light, typical, heavy): the share of frames that read the clock late or early (-realistic: 4, 9 and
    # 20 %)
    demo_load_share: Fraction = Fraction(19, 20)
    jitter: Fraction = Fraction(1, 1000)
    jitter_pattern: str = "mixed"
    # The layout, in virtual pixels. Box size; None: 2/15 of the canvas height (48 on 1280 x 720 at the default pixel size 2, 96 at 1, 24 at 4)
    box_size: int | None = None
    # How far the box travels / a row moves per page; None: 4 x the box spacing
    travel: int | None = None
    # Space between each row and the divider line in the middle; None: half the box size
    box_gap: int | None = None
    # From one box of a row to the next; None: twice the box size
    box_spacing: int | None = None
    # What each half shows at the normal and fast speeds: one box moving side to side, or a row of boxes paging left and back. The
    # ui speeds always scroll a row. follow: the follow camera scene at every speed.
    scene: str = "box"
    # Each refresh is shown for this many video frames (slow motion), one video per factor; the timing data stays in real time
    slow_motions: tuple[int, ...] = (1,)
    # The follow scene's videos: a name ("" or "extreme") and a stack of boxes, top to bottom
    follow_stacks: tuple[tuple[str, tuple[FrameMode, ...]], ...] = FOLLOW_STACKS
    # Neutral grays with clear contrast (about 8.5:1) but away from black and white, so they look the same on every display: LCD
    # overdrive has room in both directions, VA panels stay out of their slow near-black transitions, OLEDs out of near-black
    # smearing, and no colour bleeds or clips in re-encoded (4:2:0, 16-235) web video
    background: Rgb = (48, 48, 48)
    box_color: Rgb = (208, 208, 208)
    divider: bool = True
    divider_color: Rgb = (80, 80, 80)
    label_color: Rgb = (200, 200, 200)
    labels: bool = False
    # Follow scene: the lines that mark where a perfectly timed box stays
    line_color: Rgb = (208, 72, 72)

    @property
    def canvas(self) -> tuple[int, int]:
        """Width and height of the scene in virtual pixels: the video size divided by the pixel size, rounded up (the enlarged scene
        is centred and cropped to the video)."""
        return -(-self.width // self.pixel_size), -(-self.height // self.pixel_size)

    @property
    def resolved_box_size(self) -> int:
        return max(1, round(self.canvas[1] * 2 / 15)) if self.box_size is None else self.box_size

    @property
    def resolved_travel(self) -> int:
        return 4 * self.resolved_spacing if self.travel is None else self.travel

    def travel_for(self, speed: Speed) -> int:
        """Virtual pixels the box travels / a row moves per page at this speed: its own travel (slow), else the settings'."""
        return floor(self.resolved_travel * speed.travel_share) if speed.travel is None else speed.travel

    def scene_for(self, speed: Speed) -> str:
        """What the clips of this speed show: the follow scene at every speed, otherwise a ui scroll always shows a row."""
        if self.scene == "follow":
            return "follow"
        return "row" if speed.scroll is not None else self.scene

    @property
    def resolved_spacing(self) -> int:
        return 2 * self.resolved_box_size if self.box_spacing is None else self.box_spacing

    @property
    def resolved_box_gap(self) -> int:
        return self.resolved_box_size // 2 if self.box_gap is None else self.box_gap

    @property
    def divider_rows(self) -> tuple[int, int]:
        """First row and thickness of the divider line in the middle, in video pixels (its place is kept when it is not drawn)."""
        thickness = max(1, self.height // 180)
        return (self.height - thickness) // 2, thickness

    @property
    def band_height(self) -> int:
        """Height of a row of boxes in video pixels."""
        return self.resolved_box_size * self.pixel_size

    @property
    def box_rows(self) -> tuple[int, int]:
        """Top video pixel row of the top and of the bottom row of boxes: each sits box gap virtual pixels from the divider."""
        first, thickness = self.divider_rows
        gap = self.resolved_box_gap * self.pixel_size
        return first - gap - self.band_height, first + thickness + gap

    @property
    def modes(self) -> tuple[FrameMode, ...]:
        """The selected modes, each once: the follow scene's stack, or the top and bottom modes."""
        if self.scene == "follow":
            return tuple(dict.fromkeys(mode for _, stack in self.follow_stacks for mode in stack))
        return tuple(dict.fromkeys(self.top + self.bottom))

    @property
    def follow_gap(self) -> int:
        """Virtual pixels between the stacked boxes of the follow scene."""
        return max(1, self.resolved_box_size // 4)

    @property
    def timing(self) -> TimingParameters:
        """The frame loop's parameters (frame_timing)."""
        return TimingParameters(
            fps=self.fps,
            noise=self.wake_noise,
            frame_cost=self.frame_cost,
            demo_load_share=self.demo_load_share,
            synthetic=self.jitter,
            synthetic_pattern=self.jitter_pattern,
        )

    def label(self, mode: FrameMode) -> str:
        """The text written next to a box, for example "60 Hz naive timer, busy scheduler"."""
        return describe(mode, self.timing)

    def move_time(self, speed: Speed) -> Fraction:
        """Seconds for one way across (left to right) at this speed: half a round trip without its rest; a ui scroll moves all the
        time."""
        return self.seconds if speed.scroll is not None else self.period(speed) / 2 - self.settle_for(speed)

    def period(self, speed: Speed) -> Fraction:
        """Seconds per round trip at this speed, including the rest at both ends; for a ui scroll, the clip length."""
        return self.seconds if speed.scroll is not None else self.seconds / speed.round_trips

    def settle_for(self, speed: Speed) -> Fraction:
        """Seconds the box rests at each end of its travel at this speed."""
        return Fraction(0) if speed.scroll is not None else self.settle

    def duration(self, speed: Speed) -> Fraction:
        """Clip length in seconds (the same at every speed)."""
        del speed
        return self.seconds

    def frame_count(self, speed: Speed) -> int:
        """Refreshes per clip (the timing data is per refresh)."""
        return floor(self.duration(speed) * self.fps)

    def video_frame_count(self, job: VideoJob) -> int:
        """Frames of the job's encoded video: every refresh shown slow motion times."""
        return self.frame_count(job.speed) * job.slow_motion


SCENES = ("box", "row", "follow")


@dataclass(frozen=True)
class VideoJob:
    top: FrameMode
    bottom: FrameMode
    speed: Speed
    scene: str = "box"
    labels: bool = False
    pixel_size: int = DEFAULT_PIXEL_SIZE
    jitter_pattern: str = "mixed"
    slow_motion: int = 1
    # The follow scene's stack (its video has no top and bottom pair) and its name ("" or "extreme")
    boxes: tuple[FrameMode, ...] = ()
    stack: str = ""

    @property
    def _variant(self) -> list[str]:
        """What sets the clip apart from the default besides its modes and speed: the grid size, a single synthetic jitter pattern
        (only when a mode uses it) and slow motion."""
        pixel = [] if self.pixel_size == DEFAULT_PIXEL_SIZE else [f"px{self.pixel_size}"]
        synthetic = any(mode.noise == "synthetic" for mode in (self.top, self.bottom, *self.boxes))
        pattern = [] if self.jitter_pattern == "mixed" or not synthetic else [self.jitter_pattern]
        return pixel + pattern + ([] if self.slow_motion == 1 else [f"slow{self.slow_motion}"])

    @property
    def filename(self) -> str:
        prefix = "" if self.scene == "box" else f"{self.scene}_"
        suffix = "".join(f"_{part}" for part in self._variant)
        if self.scene == "follow":
            stack = f"-{self.stack}" if self.stack else ""
            return f"follow{stack}_{self.speed.name}{suffix}.mp4"
        return f"{prefix}{self.speed.name}_top-{self.top.name}_bottom-{self.bottom.name}{suffix}.mp4"

    @property
    def group(self) -> Path:
        """The job's folder under the output folder: the scene (with -labels when labelled, -px4 on a 4 x 4 virtual pixel grid),
        then the speed, e.g. box/fast or row-labels-px4/ui-768."""
        suffix = ("-labels" if self.labels else "") + "".join(f"-{part}" for part in self._variant)
        return Path(self.scene + suffix) / self.speed.name


def validate(settings: Settings) -> None:
    """Raise ValueError unless every selected clip can be made and loops seamlessly (frame N repeats frame 0 exactly)."""
    if not settings.top or not settings.bottom:
        raise ValueError("select at least one top and one bottom pacing mode")
    if not settings.speeds:
        raise ValueError("select at least one speed")
    if settings.width <= 0 or settings.height <= 0:
        raise ValueError(f"the size must be positive, got {settings.width}x{settings.height}")
    if settings.pixel_size < 1:
        raise ValueError(f"the virtual pixel size must be at least 1, got {settings.pixel_size}")
    canvas_width, canvas_height = settings.canvas
    box = settings.resolved_box_size
    top_y, bottom_y = settings.box_rows
    if box <= 0 or settings.resolved_box_gap < 0 or top_y < 0 or bottom_y + settings.band_height > settings.height:
        raise ValueError(f"box size {box} with a gap of {settings.resolved_box_gap} to the divider does not fit in the height {canvas_height}")
    if not settings.slow_motions or min(settings.slow_motions) < 1:
        raise ValueError(f"the slow motion factors must be at least 1, got {', '.join(map(str, settings.slow_motions))}")
    if settings.scene == "follow":
        for _, stack in settings.follow_stacks:
            count = len(stack)
            if count == 0:
                raise ValueError("the follow scene needs at least one box (--follow-boxes)")
            if count * settings.resolved_box_size + (count - 1) * settings.follow_gap > settings.canvas[1]:
                raise ValueError(f"{count} boxes of {settings.resolved_box_size} do not fit above each other in the height {settings.canvas[1]}")
            rates = sorted({mode.rate for mode in stack}, reverse=True)
            if len(rates) > 1:
                raise ValueError(
                    f"the follow scene shows one frame rate, like a game: its camera is updated at that rate, so all boxes need the same rate (got {', '.join(map(str, rates))} Hz)"
                )
    if settings.jitter_pattern not in JITTER_PATTERNS:
        raise ValueError(f"unknown jitter pattern {settings.jitter_pattern!r}: use {' or '.join(JITTER_PATTERNS)}")
    if settings.scene not in SCENES:
        raise ValueError(f"unknown scene {settings.scene!r}: use {' or '.join(SCENES)}")
    for speed in settings.speeds:
        if settings.scene_for(speed) == "box" and box + settings.travel_for(speed) > canvas_width:
            raise ValueError(f"box size {box} + travel {settings.travel_for(speed)} does not fit in the width {canvas_width}")
    if settings.resolved_spacing <= box:
        raise ValueError(f"the box spacing {settings.resolved_spacing} must be larger than the box size {box}")
    if any(settings.travel_for(speed) < 0 for speed in settings.speeds):
        raise ValueError("the travel must not be negative")
    if settings.fps <= 0 or settings.seconds <= 0:
        raise ValueError("fps and the clip length must be greater than zero")
    for speed in settings.speeds:
        if speed.round_trips < 1 or (speed.scroll is None and settings.move_time(speed) <= 0):
            raise ValueError(f"the {speed.name} speed's round trips must fit the clip with the rest at both ends (--settle)")

    if any(settings.settle_for(speed) < 0 for speed in settings.speeds):
        raise ValueError("the settle time must not be negative")
    for speed in settings.speeds:
        if speed.scroll is None or settings.scene == "follow":
            continue
        # The row repeats every box spacing, so a clip loops seamlessly when it scrolls a whole number of spacings
        distance = speed.scroll * settings.duration(speed)
        if speed.scroll <= 0 or (distance / settings.resolved_spacing).denominator != 1:
            raise ValueError(
                f"{speed.name} scrolls {format_number(distance)} virtual px per clip, which must be a whole number of box spacings "
                + f"({settings.resolved_spacing} virtual px) to loop seamlessly"
            )

    fps = format_number(settings.fps)
    for mode in settings.modes:
        # Whole refreshes per frame, every frame in time for its vsync, the synthetic pattern valid
        validate_timing(mode, settings.timing)

    for speed in settings.speeds:
        duration = settings.duration(speed)
        clip = f"{speed.name} clip is {format_number(duration)} s"
        if (duration * settings.fps).denominator != 1:
            raise ValueError(f"{clip}, which is not a whole number of frames at {fps} fps")
        for mode in settings.modes:
            updates = duration * mode.rate
            if updates.denominator != 1:
                raise ValueError(f"{clip}; {mode.name} needs a whole number of updates per clip to loop seamlessly, got {format_number(updates)}")
            _ = frame_schedule(settings, mode, speed)


def plan_videos(settings: Settings) -> list[VideoJob]:
    if settings.scene == "follow":
        # One video per stack and speed
        return [
            VideoJob(stack[0], stack[-1], speed, "follow", settings.labels, settings.pixel_size, settings.jitter_pattern, slow, stack, name)
            for slow in settings.slow_motions
            for name, stack in settings.follow_stacks
            for speed in settings.speeds
        ]
    pairs = settings.pairs or tuple((top, bottom) for top in settings.top for bottom in settings.bottom)
    return [
        VideoJob(top, bottom, speed, settings.scene_for(speed), settings.labels, settings.pixel_size, settings.jitter_pattern, slow)
        for slow in settings.slow_motions
        for speed in settings.speeds
        for top, bottom in pairs
    ]


# ---------------------------------------------------------------------------------------------------------------------------------
# Motion and rendering


def _ease(progress: Fraction, easing: bool) -> float:
    """0 -> 1 as progress goes 0 -> 1: sine ease-in-out (starts and stops gently), or linear."""
    return (1 - cos(pi * float(progress))) / 2 if easing else float(progress)


def travel_position(settings: Settings, speed: Speed, time: Fraction) -> float:
    """How far a row has paged (0: at rest, 1: one page on) at animation time `time`, repeating every round trip: rest, page, rest,
    page back. Time 0 is the middle of the first rest, so clips start and end at rest."""
    move = settings.move_time(speed)
    settle = settings.settle_for(speed)
    period = settings.period(speed)
    time += settle / 2
    within = time - floor(time / period) * period
    if within < settle:
        return 0.0
    within -= settle
    if within < move:
        return _ease(within / move, settings.easing)
    within -= move
    if within < settle:
        return 1.0
    return 1 - _ease((within - settle) / move, settings.easing)


@dataclass(frozen=True)
class FrameSchedule:
    """The frames of one clip: the output refresh each first appears on, and the animation time it shows (seconds)."""

    shown: tuple[int, ...]
    animation: tuple[Fraction, ...]


@functools.cache
def simulated_frames(settings: Settings, mode: FrameMode, speed: Speed) -> SimulatedFrames:
    """The frame loop over one clip (frame_timing.simulate): when each frame is flipped, when the loop read the clock, and the
    animation time each frame shows."""
    return simulate(mode, settings.timing, settings.frame_count(speed))


def frame_schedule(settings: Settings, mode: FrameMode, speed: Speed) -> FrameSchedule:
    """The frames of one clip: the refresh each is flipped on and the animation time it shows."""
    frames = simulated_frames(settings, mode, speed)
    return FrameSchedule(frames.flips, frames.animation)


def content_time(settings: Settings, mode: FrameMode, speed: Speed, frame: int) -> Fraction:
    """Animation time a box shows in output frame `frame`; frames past the clip continue the motion (the loop checks use this)."""
    schedule = frame_schedule(settings, mode, speed)
    loops, within = divmod(frame, settings.frame_count(speed))
    return schedule.animation[bisect.bisect_right(schedule.shown, within) - 1] + loops * settings.duration(speed)


def animation_errors(settings: Settings, mode: FrameMode, speed: Speed) -> list[Fraction]:
    """Animation error of each frame of the clip, in seconds, as PresentMon computes it: how far the animation time advanced since
    the previous frame, minus how long the previous frame was on screen. Positive: shown too soon; negative: shown too late. The
    first frame follows the last one of the previous loop."""
    schedule = frame_schedule(settings, mode, speed)
    refresh = 1 / settings.fps
    errors: list[Fraction] = []
    for index, (shown, animation) in enumerate(zip(schedule.shown, schedule.animation, strict=True)):
        if index == 0:
            previous_shown, previous_animation = schedule.shown[-1] - settings.frame_count(speed), schedule.animation[-1] - settings.duration(speed)
        else:
            previous_shown, previous_animation = schedule.shown[index - 1], schedule.animation[index - 1]
        errors.append((animation - previous_animation) - (shown - previous_shown) * refresh)
    return errors


def refreshes_late(settings: Settings, mode: FrameMode, speed: Speed) -> list[int]:
    """How many refreshes after the one it was rendered for each frame of the clip is flipped: 0 on time. A naive timer's frame is
    on time however far off the moment it shows, unless it is also late (the perfect storm)."""
    frames = simulated_frames(settings, mode, speed)
    return [flip - target for flip, target in zip(frames.flips, frames.targets, strict=True)]


def row_offset(settings: Settings, mode: FrameMode, speed: Speed, frame: int) -> float:
    """How far (sub-pixel) the scene is shifted in output frame `frame`: 0 at rest, -travel after the first move, then back. A row
    scrolls left by that much (like pressing right in an interface); the single box moves the other way, to the right. A ui scroll
    shifts the row left at constant speed, reduced to within one box spacing (the row repeats every spacing)."""
    time = content_time(settings, mode, speed, frame)
    if speed.scroll is not None:
        return -float(speed.scroll * time % settings.resolved_spacing)
    return -settings.travel_for(speed) * travel_position(settings, speed, time)


def row_offsets(settings: Settings, job: VideoJob, frame: int) -> tuple[float, float]:
    return row_offset(settings, job.top, job.speed, frame), row_offset(settings, job.bottom, job.speed, frame)


def world_position(settings: Settings, speed: Speed, time: Fraction) -> Fraction | float:
    """How far the moving object is to the right in the world at animation time `time`, in virtual pixels: a ui scroll moves at
    constant speed, the other speeds along the eased round trip."""
    if speed.scroll is not None:
        return speed.scroll * time
    return settings.travel_for(speed) * travel_position(settings, speed, time)


def follow_positions(settings: Settings, job: VideoJob, frame: int) -> tuple[float, ...]:
    """For the follow camera, in virtual pixels: how far each box of the stack is from where a perfect box is. The camera follows
    the perfect motion at the stack's rate (the ideal timer: updated at that rate, like the game's camera), so an ideal box stays at
    0 and only a timing error moves a box."""
    speed = job.speed
    camera = world_position(settings, speed, content_time(settings, parse_mode(str(job.boxes[0].rate)), speed, frame))
    errors = [float(world_position(settings, speed, content_time(settings, box, speed, frame)) - camera) for box in job.boxes]
    return tuple(errors)


def _mix(a: Rgb, b: Rgb, weight: float) -> Rgb:
    return round(a[0] + (b[0] - a[0]) * weight), round(a[1] + (b[1] - a[1]) * weight), round(a[2] + (b[2] - a[2]) * weight)


def edge_fade(width: int) -> list[float]:
    """Weight of each column (0 at the frame edges, 1 inside): a smoothstep over the first and last tenth of the width."""
    fade = max(1, width // 10)
    weights: list[float] = []
    for x in range(width):
        distance = min(1.0, (min(x, width - 1 - x) + 0.5) / fade)
        weights.append(distance * distance * (3 - 2 * distance))
    return weights


def divider_colors(settings: Settings) -> list[Rgb]:
    """Colour of each column of the divider: it fades in from the background over the first and last tenth of the width."""
    return [_mix(settings.background, settings.divider_color, weight) for weight in edge_fade(settings.width)]


class FrameRenderer:
    """Draws the frames of one clip: a background (divider, labels) prepared once, plus the two rows of boxes. The rows are drawn on
    the virtual pixel grid (--pixel-size) and enlarged to video pixels on that fixed grid; the background stays at full resolution."""

    def __init__(self, settings: Settings, job: VideoJob) -> None:
        self._settings: Settings = settings
        self._scene: str = job.scene
        self._background: Image.Image = Image.new("RGB", (settings.width, settings.height), settings.background)
        draw = ImageDraw.Draw(self._background)
        if settings.divider:
            first, thickness = settings.divider_rows
            for x, color in enumerate(divider_colors(settings)):
                draw.rectangle((x, first, x, first + thickness - 1), fill=color)
        rows = settings.box_rows
        self._top_y: int = rows[0]
        self._bottom_y: int = rows[1]
        if settings.labels:
            # Centred next to each row, on the side away from the divider: above the top row, below the bottom row
            font = ImageFont.load_default(size=max(12, settings.height // 20))
            margin = max(4, settings.height // 45)
            centre = settings.width / 2
            draw.text((centre, self._top_y - margin), settings.label(job.top), fill=settings.label_color, font=font, anchor="md")
            draw.text((centre, self._bottom_y + settings.band_height + margin), settings.label(job.bottom), fill=settings.label_color, font=font, anchor="ma")
        # Row: at rest one box is centred, and the row repeats every spacing pixels in both directions. Box: its path is centred
        # In virtual pixels: the row's anchor box and the single box's start are centred on the canvas
        canvas_width = settings.canvas[0]
        box = settings.resolved_box_size
        self._anchor: float = (canvas_width - box) / 2
        self._box_start: float = (canvas_width - box - settings.travel_for(job.speed)) // 2
        # The rows are drawn in virtual pixels, enlarged and centred on the video (cropping any part of a virtual pixel that does not
        # fit); boxes fade in and out at the canvas edges instead of popping in
        pixel = settings.pixel_size
        band_size = (canvas_width, box)
        self._crop: int = (canvas_width * pixel - settings.width) // 2
        self._band_background: Image.Image = Image.new("RGB", band_size, settings.background)
        self._fade: Image.Image = Image.new("L", band_size)
        fade_draw = ImageDraw.Draw(self._fade)
        for x, weight in enumerate(edge_fade(band_size[0])):
            fade_draw.rectangle((x, 0, x, band_size[1] - 1), fill=round(255 * weight))

    def box_lefts(self, offset: float) -> list[float]:
        """Left edges of the boxes that touch the frame, for a scene shifted by `offset` (see row_offset)."""
        if self._scene == "box":
            return [self._box_start - offset]
        spacing = self._settings.resolved_spacing
        start = self._anchor + offset
        first = floor((-self._settings.resolved_box_size - start) / spacing) + 1
        lefts: list[float] = []
        index = first
        while start + index * spacing < self._settings.canvas[0]:
            lefts.append(start + index * spacing)
            index += 1
        return lefts

    def _row(self, offset: float) -> Image.Image:
        """One row as a band of box height in video pixels. It is drawn in virtual pixels: a box between virtual pixels covers its
        first and last column partly, and those columns are blended with the background by how much they are covered (sub-pixel
        motion); then every virtual pixel becomes a block of pixel size x pixel size video pixels."""
        settings = self._settings
        pixel = settings.pixel_size
        band = self._band_background.copy()
        draw = ImageDraw.Draw(band)
        size = settings.resolved_box_size
        for x in self.box_lefts(offset):
            left = floor(x)
            cover = x - left
            if cover < 1 / 512:
                draw.rectangle((left, 0, left + size - 1, size - 1), fill=settings.box_color)
                continue
            draw.rectangle((left, 0, left, size - 1), fill=_mix(settings.background, settings.box_color, 1 - cover))
            if size > 1:
                draw.rectangle((left + 1, 0, left + size - 1, size - 1), fill=settings.box_color)
            draw.rectangle((left + size, 0, left + size, size - 1), fill=_mix(settings.background, settings.box_color, cover))
        row = Image.composite(band, self._band_background, self._fade)
        if pixel == 1:
            return row
        enlarged = row.resize((row.width * pixel, row.height * pixel), Image.Resampling.NEAREST)  # pyright: ignore[reportUnknownMemberType]
        return enlarged.crop((self._crop, 0, self._crop + settings.width, enlarged.height))

    def render(self, top_offset: float, bottom_offset: float) -> Image.Image:
        """The frame with the top and bottom rows shifted by `top_offset` and `bottom_offset` pixels."""
        image = self._background.copy()
        image.paste(self._row(top_offset), (0, self._top_y))
        image.paste(self._row(bottom_offset), (0, self._bottom_y))
        return image


def _bar(image: Image.Image, x: float, width: int, y: int, height: int, color: Rgb) -> None:
    """Draw a bar `width` wide whose left edge is at the sub-pixel position `x`. The columns it covers partly are blended with what is
    under them (read at row `y`) by how much they are covered."""
    draw = ImageDraw.Draw(image)
    left = floor(x)
    cover = x - left

    def partial(column: int, weight: float) -> None:
        if 0 <= column < image.width:
            under = cast(Rgb, image.getpixel((column, y)))
            draw.rectangle((column, y, column, y + height - 1), fill=_mix(under, color, weight))

    if cover < 1 / 512:
        draw.rectangle((left, y, left + width - 1, y + height - 1), fill=color)
        return
    partial(left, 1 - cover)
    if width > 1:
        draw.rectangle((left + 1, y, left + width - 1, y + height - 1), fill=color)
    partial(left + width, cover)


class FollowRenderer:
    """The follow camera scene (--scene follow), after the slow motion demo of Unity's Time.deltaTime fix: a stack of boxes in the
    middle, each with its own mode, and two fixed lines marking where a perfectly timed box stays. The boxes are drawn in virtual
    pixels; the lines and labels in video pixels (1:1), on top."""

    def __init__(self, settings: Settings, job: VideoJob) -> None:
        self._settings: Settings = settings
        self._job: VideoJob = job
        canvas_width, canvas_height = settings.canvas
        box = settings.resolved_box_size
        gap = settings.follow_gap
        pixel = settings.pixel_size
        # In virtual pixels: a perfect box's left edge, and the top of each box of the stack (centred on the canvas)
        self._left: int = (canvas_width - box) // 2
        count = len(job.boxes)
        first = (canvas_height - count * box - (count - 1) * gap) // 2
        self._tops: list[int] = [first + index * (box + gap) for index in range(count)]
        self._crop: tuple[int, int] = ((canvas_width * pixel - settings.width) // 2, (canvas_height * pixel - settings.height) // 2)
        self._blank: Image.Image = Image.new("RGB", settings.canvas, settings.background)
        self._plain: Image.Image = Image.new("RGB", (settings.width, settings.height), settings.background)
        # The lines (behind the boxes) and the labels, in video pixels
        self._lines: Image.Image = Image.new("RGBA", (settings.width, settings.height), (0, 0, 0, 0))
        lines = ImageDraw.Draw(self._lines)
        thickness = max(1, settings.height // 360)
        left = self._left * pixel - self._crop[0]
        right = (self._left + box) * pixel - self._crop[0]
        lines.rectangle((left - thickness, 0, left - 1, settings.height - 1), fill=settings.line_color)
        lines.rectangle((right, 0, right + thickness - 1, settings.height - 1), fill=settings.line_color)
        self._overlay: Image.Image = Image.new("RGBA", (settings.width, settings.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(self._overlay)
        if settings.labels:
            # Next to each box, right of the lines and clear of the furthest any box swings to the right; smaller than the two-half
            # labels, so the longest fits in the right half
            font = ImageFont.load_default(size=max(12, settings.height // 30))
            margin = max(4, settings.height // 45)
            positions = [follow_positions(settings, job, frame) for frame in range(settings.frame_count(job.speed))]
            swing = max([0.0, *(offset for values in positions for offset in values)])
            x = right + thickness + ceil(swing * pixel) + 2 * margin
            for follow_box, top in zip(job.boxes, self._tops, strict=True):
                middle = (top + box / 2) * pixel - self._crop[1]
                draw.text((x, middle), settings.label(follow_box), fill=settings.label_color, font=font, anchor="lm")

    def positions(self, frame: int) -> tuple[float, ...]:
        return follow_positions(self._settings, self._job, frame)

    def draw(self, positions: tuple[float, ...]) -> Image.Image:
        """The frame with each box its offset (virtual pixels) off the perfect position."""
        offsets = positions
        settings = self._settings
        box = settings.resolved_box_size
        scene = self._blank.copy()
        for offset, top in zip(offsets, self._tops, strict=True):
            _bar(scene, self._left + offset, box, top, box, settings.box_color)
        pixel = settings.pixel_size
        if pixel > 1:
            enlarged = scene.resize((scene.width * pixel, scene.height * pixel), Image.Resampling.NEAREST)  # pyright: ignore[reportUnknownMemberType]
            scene = enlarged.crop((self._crop[0], self._crop[1], self._crop[0] + settings.width, self._crop[1] + settings.height))
        # The lines go behind the boxes: only where the background shows
        uncovered = ImageChops.difference(scene, self._plain).convert("L").point([255] + [0] * 255)  # pyright: ignore[reportUnknownMemberType]
        scene.paste(self._lines, (0, 0), ImageChops.multiply(uncovered, self._lines.getchannel("A")))
        scene.paste(self._overlay, (0, 0), self._overlay)
        return scene


class Renderer(Protocol):
    def positions(self, frame: int) -> tuple[float, ...]: ...

    def draw(self, positions: tuple[float, ...]) -> Image.Image: ...


class RowRenderer:
    """FrameRenderer driven by the row offsets of a clip."""

    def __init__(self, settings: Settings, job: VideoJob) -> None:
        self._settings: Settings = settings
        self._job: VideoJob = job
        self._renderer: FrameRenderer = FrameRenderer(settings, job)

    def positions(self, frame: int) -> tuple[float, ...]:
        return row_offsets(self._settings, self._job, frame)

    def draw(self, positions: tuple[float, ...]) -> Image.Image:
        top, bottom = positions
        return self._renderer.render(top, bottom)


def renderer_for(settings: Settings, job: VideoJob) -> Renderer:
    return FollowRenderer(settings, job) if job.scene == "follow" else RowRenderer(settings, job)


def clip_frames(settings: Settings, job: VideoJob) -> Iterator[bytes]:
    """The clip's video frames as raw RGB24 bytes: every refresh, shown slow motion times."""
    renderer = renderer_for(settings, job)
    previous: tuple[tuple[float, ...], bytes] | None = None
    for frame in range(settings.frame_count(job.speed)):
        positions = renderer.positions(frame)
        # Held updates repeat the previous frame
        if previous is None or previous[0] != positions:
            previous = (positions, renderer.draw(positions).tobytes())
        for _ in range(job.slow_motion):
            yield previous[1]


# ---------------------------------------------------------------------------------------------------------------------------------
# FFmpeg


class FfmpegError(Exception):
    """FFmpeg is missing, cannot encode lossless H.264, or failed."""


@dataclass(frozen=True)
class FfmpegLocation:
    path: Path
    # Where the path came from, for messages
    source: str


def _executable(tool: str) -> str:
    return f"{tool}.exe" if os.name == "nt" else tool


def resolve_tool(location: Path, tool: str = "ffmpeg") -> Path | None:
    """`location` is the tool itself or a folder that holds it (directly or in a bin subfolder)."""
    if location.is_file():
        return location
    if location.is_dir():
        for candidate in (location / _executable(tool), location / "bin" / _executable(tool)):
            if candidate.is_file():
                return candidate
    return None


def read_config_ffmpeg(config: Path) -> Path | None:
    """The [ffmpeg] path of a local.toml; a relative path is relative to the file's folder."""
    try:
        with config.open("rb") as file:
            data: dict[str, object] = tomllib.load(file)
    except tomllib.TOMLDecodeError as error:
        raise FfmpegError(f"{config}: {error}") from error
    section = data.get("ffmpeg")
    if section is None:
        return None
    if not isinstance(section, dict):
        raise FfmpegError(f"{config}: 'ffmpeg' must be a table ([ffmpeg])")
    value = cast(dict[str, object], section).get("path")
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise FfmpegError(f"{config}: [ffmpeg] path must be a non-empty string")
    return config.parent / Path(value).expanduser()


def _require(location: Path, source: str) -> FfmpegLocation:
    resolved = resolve_tool(location)
    if resolved is None:
        raise FfmpegError(f"{source}: '{location}' is not ffmpeg or a folder that holds it")
    return FfmpegLocation(resolved.resolve(), source)


def find_ffmpeg(
    explicit: str | None = None,
    config: Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    default_config: Path = DEFAULT_CONFIG,
) -> FfmpegLocation:
    """Find FFmpeg: --ffmpeg, then MB_FFMPEG, then the config file ([ffmpeg] path), then PATH (the order mb-framepacing uses).

    A source that is set but does not point to FFmpeg is an error rather than skipped, so a typo is not hidden by another FFmpeg.
    """
    environ = os.environ if environ is None else environ
    if explicit:
        return _require(Path(explicit).expanduser(), "--ffmpeg")
    from_environment = environ.get(FFMPEG_ENVIRONMENT_VARIABLE)
    if from_environment:
        return _require(Path(from_environment).expanduser(), FFMPEG_ENVIRONMENT_VARIABLE)
    if config is not None and not config.is_file():
        raise FfmpegError(f"--config: '{config}' does not exist")
    config_file = config if config is not None else default_config
    if config_file.is_file():
        configured = read_config_ffmpeg(config_file)
        if configured is not None:
            return _require(configured, str(config_file))
    on_path = shutil.which("ffmpeg")
    if on_path:
        return FfmpegLocation(Path(on_path), "PATH")
    raise FfmpegError(
        "FFmpeg was not found. Install it (Windows: winget install Gyan.FFmpeg) or point to it with local.toml ([ffmpeg] path), "
        + f"the {FFMPEG_ENVIRONMENT_VARIABLE} environment variable or --ffmpeg."
    )


def find_ffprobe(ffmpeg: Path) -> Path | None:
    """ffprobe next to ffmpeg, else on PATH."""
    sibling = ffmpeg.with_name(_executable("ffprobe"))
    if sibling.is_file():
        return sibling
    on_path = shutil.which("ffprobe")
    return Path(on_path) if on_path else None


def list_encoders(ffmpeg: Path) -> str:
    result = subprocess.run([str(ffmpeg), "-hide_banner", "-encoders"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise FfmpegError(f"'{ffmpeg} -encoders' failed: {result.stderr.strip()}")
    return result.stdout


def require_lossless_encoder(encoders: str, ffmpeg: Path) -> None:
    """Fail unless FFmpeg has libx264: the output must be lossless, so there is no fallback to another encoder."""
    if not any(line.split()[1:2] == [ENCODER] for line in encoders.splitlines()):
        raise FfmpegError(
            f"{ffmpeg} has no {ENCODER} encoder, which lossless H.264 needs (there is no lossy fallback). "
            + "Use an FFmpeg build with libx264, for example: winget install Gyan.FFmpeg"
        )


def encoder_command(ffmpeg: Path, settings: Settings, frame_count: int, output: Path) -> list[str]:
    return [
        str(ffmpeg),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        # Input: raw RGB24 frames on stdin
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{settings.width}x{settings.height}",
        "-framerate",
        str(settings.fps),
        "-i",
        "-",
        "-frames:v",
        str(frame_count),
        # RGB -> YUV (4:4:4, or 4:2:0 for the web), BT.709 limited range, with accurate rounding; neutral grays convert exactly
        "-vf",
        "scale=out_color_matrix=bt709:out_range=tv:flags=accurate_rnd+full_chroma_int",
        # Output: lossless H.264 (-qp 0, High 4:4:4 Predictive profile), or for the web near-lossless H.264 High 4:2:0; tagged BT.709
        # so players convert back to the same colours
        "-c:v",
        ENCODER,
        *(["-crf", str(WEB_CRF), "-preset", "slow", "-profile:v", "high"] if settings.web else ["-qp", "0", "-preset", "medium"]),
        "-pix_fmt",
        WEB_PIXEL_FORMAT if settings.web else PIXEL_FORMAT,
        "-colorspace",
        "bt709",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-color_range",
        "tv",
        "-movflags",
        "+faststart",
        "-f",
        "mp4",
        str(output),
    ]


def encode_video(ffmpeg: Path, settings: Settings, job: VideoJob, output: Path) -> None:
    """Stream the clip to FFmpeg. It writes a temporary file that replaces `output` only when encoding succeeded."""
    partial = output.with_name(f"{output.stem}.partial{output.suffix}")
    command = encoder_command(ffmpeg, settings, settings.video_frame_count(job), partial)
    try:
        with subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE) as process:
            if process.stdin is None or process.stderr is None:
                raise FfmpegError("could not connect to FFmpeg")
            try:
                for frame in clip_frames(settings, job):
                    _ = process.stdin.write(frame)
            except BrokenPipeError:
                pass  # FFmpeg stopped early: its exit code and message below say why
            finally:
                with contextlib.suppress(BrokenPipeError):
                    process.stdin.close()
            stderr: IO[bytes] = process.stderr  # typeshed types the pipes as IO[Any]
            errors = stderr.read().decode(errors="replace").strip()
            exit_code = process.wait()
        if exit_code != 0 or not partial.is_file():
            raise FfmpegError(f"FFmpeg failed on {output.name} (exit code {exit_code}): {errors}")
        _ = partial.replace(output)
    finally:
        partial.unlink(missing_ok=True)


# ---------------------------------------------------------------------------------------------------------------------------------
# Manifest


def _json_number(value: Fraction) -> int | float:
    return value.numerator if value.denominator == 1 else float(value)


def _hex_color(color: Rgb) -> str:
    return f"#{color[0]:02X}{color[1]:02X}{color[2]:02X}"


def _milliseconds(values: Sequence[Fraction]) -> list[float]:
    return [round(float(value * 1000), 3) for value in values]


def _mode_entry(settings: Settings, mode: FrameMode, speed: Speed) -> dict[str, object]:
    frames = simulated_frames(settings, mode, speed)
    animation = list(frames.animation)
    duration = settings.duration(speed)
    return {
        "mode": mode.name,
        "rate": mode.rate,
        "timer": mode.timer.value,
        "noise": None if mode.noise is None else mode.noise.value,
        "noiseWindowMs": None if mode.window is None else _json_number(mode.window * 1000),
        "label": settings.label(mode),
        # Every frame of the clip: the output refresh it is flipped on, when the naive loop read the clock (ms, the first frame is
        # shown at 0), the dt its animation advanced by, its animation error (PresentMon's MsAnimationError) and how many refreshes
        # after the one it was rendered for it is flipped (0: on time)
        "frames": {
            "refresh": list(frames.flips),
            "sampleMs": _milliseconds(frames.samples),
            "dtMs": _milliseconds([animation[0] - (animation[-1] - duration)] + [b - a for a, b in itertools.pairwise(animation)]),
            "animationErrorMs": _milliseconds(animation_errors(settings, mode, speed)),
            "late": refreshes_late(settings, mode, speed),
        },
    }


def _halves(settings: Settings, job: VideoJob) -> dict[str, object]:
    """The modes of a video: top and bottom, or the follow scene's stack of boxes (top to bottom)."""
    if job.scene == "follow":
        return {"boxes": [_mode_entry(settings, box, job.speed) for box in job.boxes]}
    return {"top": _mode_entry(settings, job.top, job.speed), "bottom": _mode_entry(settings, job.bottom, job.speed)}


def build_manifest(settings: Settings, jobs: Sequence[VideoJob]) -> dict[str, object]:
    return {
        "generator": "tools/frame_pacing_video/generate_videos.py",
        "settings": {
            "width": settings.width,
            "height": settings.height,
            "pixelSize": settings.pixel_size,
            "canvas": list(settings.canvas),
            "fps": _json_number(settings.fps),
            "clipSeconds": _json_number(settings.seconds),
            "settleSeconds": _json_number(settings.settle),
            "easing": settings.easing,
            "wakeNoiseMs": [_json_number(value * 1000) for value in settings.wake_noise],
            "frameCost": _json_number(settings.frame_cost),
            "demoLoadShare": _json_number(settings.demo_load_share),
            "syntheticJitterMs": _json_number(settings.jitter * 1000),
            "jitterPattern": settings.jitter_pattern,
            "boxSize": settings.resolved_box_size,
            "travel": settings.resolved_travel,
            "scene": settings.scene,
            "boxSpacing": settings.resolved_spacing,
            "boxGap": settings.resolved_box_gap,
            "background": _hex_color(settings.background),
            "boxColor": _hex_color(settings.box_color),
            "divider": settings.divider,
            "dividerColor": _hex_color(settings.divider_color),
            "labelColor": _hex_color(settings.label_color),
            "labels": settings.labels,
            "encoder": ENCODER,
            "pixelFormat": WEB_PIXEL_FORMAT if settings.web else PIXEL_FORMAT,
            "web": settings.web,
        },
        "videos": [
            {
                "file": job.filename,
                "speed": job.speed.name,
                "roundTrips": None if job.speed.scroll is not None else job.speed.round_trips,
                "travel": None if job.speed.scroll is not None else settings.travel_for(job.speed),
                "scene": job.scene,
                "scrollVirtualPixelsPerSecond": None if job.speed.scroll is None else _json_number(job.speed.scroll),
                "moveSeconds": _json_number(settings.move_time(job.speed)),
                "settleSeconds": _json_number(settings.settle_for(job.speed)),
                "roundTripSeconds": _json_number(settings.period(job.speed)),
                "durationSeconds": _json_number(settings.duration(job.speed)),
                "fps": _json_number(settings.fps),
                "frameCount": settings.frame_count(job.speed),
                "slowMotion": job.slow_motion,
                "videoFrameCount": settings.video_frame_count(job),
                "width": settings.width,
                "height": settings.height,
                **_halves(settings, job),
            }
            for job in jobs
        ],
    }


# ---------------------------------------------------------------------------------------------------------------------------------
# Command line


class Arguments(argparse.Namespace):
    """The parsed command line, typed. argparse sets every attribute (each option has a default)."""

    output_dir: Path
    top: list[FrameMode] | None
    bottom: list[FrameMode] | None
    pairs: list[tuple[FrameMode, FrameMode]] | None
    web: bool
    speed: list[str]
    ui_scroll: list[Fraction | str]
    seconds: Fraction
    labels: bool
    width: int
    height: int
    pixel_size: int
    fps: Fraction
    settle: Fraction
    no_easing: bool
    noise_ms: list[Fraction | str]
    frame_cost: Fraction
    demo_load_share: Fraction
    jitter_ms: Fraction
    jitter_pattern: str
    normal_round_trips: int
    fast_round_trips: int
    slow_travel: int | None
    box_size: int | None
    travel: int | None
    box_gap: int | None
    box_spacing: int | None
    scene: str
    background: Rgb
    box_color: Rgb
    no_divider: bool
    divider_color: Rgb
    label_color: Rgb
    line_color: Rgb
    slow_motion: list[int] | None
    follow_boxes: list[FrameMode] | None
    ffmpeg: str | None
    config: Path | None
    preview_png: bool
    check_ffmpeg: bool


def _positive_fraction(text: str) -> Fraction:
    try:
        value = Fraction(text)
    except (ValueError, ZeroDivisionError) as error:
        raise argparse.ArgumentTypeError(f"'{text}' is not a number (examples: 60, 2.5, 60000/1001)") from error
    if value <= 0:
        raise argparse.ArgumentTypeError(f"'{text}' must be greater than zero")
    return value


def _non_negative_fraction(text: str) -> Fraction:
    try:
        value = Fraction(text)
    except (ValueError, ZeroDivisionError) as error:
        raise argparse.ArgumentTypeError(f"'{text}' is not a number (examples: 4, 2.5)") from error
    if value < 0:
        raise argparse.ArgumentTypeError(f"'{text}' must not be negative")
    return value


def _mode(text: str) -> FrameMode:
    try:
        return parse_mode(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def _pair(text: str) -> tuple[FrameMode, FrameMode]:
    """A --pairs item: TOP:BOTTOM, two mode names."""
    top, separator, bottom = text.partition(":")
    if not separator:
        raise argparse.ArgumentTypeError(f"'{text}' is not a pair: use TOP:BOTTOM, e.g. 60:60-naive-4ms")
    return _mode(top), _mode(bottom)


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"'{text}' is not a whole number") from error
    if value <= 0:
        raise argparse.ArgumentTypeError(f"'{text}' must be greater than zero")
    return value


def _non_negative_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"'{text}' is not a whole number") from error
    if value < 0:
        raise argparse.ArgumentTypeError(f"'{text}' must not be negative")
    return value


def _color(text: str) -> Rgb:
    try:
        rgb = ImageColor.getrgb(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"'{text}' is not a colour (examples: gray, lightgray, #808080)") from error
    return rgb[0], rgb[1], rgb[2]


def build_parser() -> argparse.ArgumentParser:
    defaults = Settings()
    parser = argparse.ArgumentParser(
        description="Generate the frame pacing comparison videos as lossless H.264 through FFmpeg.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    add = parser.add_argument
    _ = add("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="folder for the videos and manifest.json")
    default_names = " ".join(mode.name for mode in MODES)
    modes_help = "RATE (ideal timer, e.g. 60) or RATE-naive-NOISE with NOISE a system load (light, typical, heavy), a window like 1ms or 4ms, or synthetic"
    _ = add("--top", nargs="+", type=_mode, metavar="MODE", help=f"modes of the top half: {modes_help} (default: {default_names})")
    _ = add("--bottom", nargs="+", type=_mode, metavar="MODE", help="modes of the bottom half (default: as --top)")
    _ = add(
        "--pairs",
        nargs="+",
        type=_pair,
        metavar="TOP:BOTTOM",
        help="an exact list of top/bottom pairs instead of every --top x --bottom pair, e.g. 60:60-naive-4ms 60-naive-4ms:60",
    )
    _ = add("--web", action="store_true", help=f"encode for browsers: H.264 High 4:2:0, near-lossless (CRF {WEB_CRF}), instead of lossless 4:4:4")
    _ = add(
        "--speed",
        nargs="+",
        default=["all"],
        metavar="SPEED",
        help="which speeds to generate: normal, fast, slow (not in all), ui (every ui scroll speed), a single ui speed like ui-384, or all",
    )
    _ = add("--labels", action="store_true", help="write each half's pacing mode centred next to it")
    _ = add("--width", type=_positive_int, default=defaults.width, help="video width in pixels")
    _ = add("--height", type=_positive_int, default=defaults.height, help="video height in pixels (two halves)")
    _ = add(
        "--pixel-size",
        type=_positive_int,
        default=defaults.pixel_size,
        help="virtual pixel size: lay out and draw the moving scene in virtual pixels of N x N video pixels (divider and labels stay 1:1)",
    )
    _ = add("--fps", type=_positive_fraction, default=str(defaults.fps), help="output frame rate")
    _ = add(
        "--seconds", type=_positive_fraction, default=format_number(defaults.seconds), help="every clip's length (the jitter profiles are laid out over it)"
    )
    _ = add("--settle", type=_non_negative_fraction, default=format_number(defaults.settle), help="seconds the box rests at each end (normal, fast)")
    _ = add(
        "--ui-scroll",
        nargs="+",
        type=_positive_fraction,
        default=[format_number(scroll) for scroll in UI_SCROLL],
        metavar="VPX_PER_S",
        help="virtual pixels per second of each ui scroll speed (one speed each, named by it: ui-384)",
    )
    _ = add("--no-easing", action="store_true", help="move at constant speed instead of easing in and out at both ends")
    _ = add(
        "--noise-ms",
        nargs=2,
        type=_non_negative_fraction,
        default=[format_number(value * 1000) for value in defaults.wake_noise],
        metavar=("FROM", "TO"),
        help="naive timer: how late the loop reads the clock after a flip, typical scheduler (ms)",
    )
    _ = add(
        "--frame-cost",
        type=_non_negative_fraction,
        default=format_number(defaults.frame_cost),
        help="rendering work as a share of the frame time (with the largest wake-up it must fit: every frame makes its vsync)",
    )
    _ = add(
        "--demo-load-share",
        type=_non_negative_fraction,
        default=format_number(defaults.demo_load_share),
        help="the loads' demo profile (light, typical, heavy): the share of frames that read the clock late or early, below 1 (-realistic: 0.04, 0.09, 0.2)",
    )
    _ = add(
        "--jitter-ms",
        type=_non_negative_fraction,
        default=format_number(defaults.jitter * 1000),
        help="synthetic noise (RATE-naive-synthetic): the amount (+- ms)",
    )
    _ = add(
        "--jitter-pattern",
        choices=JITTER_PATTERNS,
        default=defaults.jitter_pattern,
        help="synthetic noise: mixed (alternating and random quarters), alternating +-amount (the largest animation error) or random",
    )
    _ = add("--normal-round-trips", type=_positive_int, default=2, help="round trips per clip of the normal videos (more is faster)")
    _ = add("--fast-round-trips", type=_positive_int, default=4, help="round trips per clip of the fast videos")
    _ = add(
        "--slow-travel",
        type=_non_negative_int,
        default=None,
        help="virtual pixels the box travels at the slow speed (as normal, on a shorter path; default: a quarter of the travel)",
    )
    _ = add("--box-size", type=_positive_int, default=None, help="box width and height in virtual pixels (default: 2/15 of the canvas height)")
    _ = add("--travel", type=_non_negative_int, default=None, help="virtual pixels the box travels / a row moves per page (default: 4 x the box spacing)")
    _ = add(
        "--scene",
        choices=SCENES,
        default="box",
        help="normal and fast: one box moving side to side, or a row of boxes paging left and back; follow: the follow camera scene at every speed",
    )
    _ = add(
        "--follow-boxes",
        nargs="+",
        type=_mode,
        metavar="MODE",
        help=f"follow scene: one video with this stack of boxes, top to bottom (default: {' '.join(mode.name for mode in FOLLOW_BOXES)}, and an extreme cases video with {' '.join(mode.name for mode in FOLLOW_EXTREME)})",
    )
    _ = add(
        "--slow-motion",
        nargs="+",
        type=_positive_int,
        metavar="N",
        help="show every refresh for N video frames (N times slower), one video per factor (default: 1, real speed)",
    )
    _ = add("--box-spacing", type=_positive_int, default=None, help="virtual pixels from one box of a row to the next (default: twice the box size)")
    _ = add("--box-gap", type=_non_negative_int, default=None, help="virtual pixels between each box and the divider (default: half the box size)")
    _ = add("--background", type=_color, default=_hex_color(defaults.background), help="background colour")
    _ = add("--box-color", type=_color, default=_hex_color(defaults.box_color), help="box colour")
    _ = add("--no-divider", action="store_true", help="leave out the divider line between the two halves")
    _ = add("--divider-color", type=_color, default=_hex_color(defaults.divider_color), help="divider line colour (fades in from the background at both ends)")
    _ = add("--label-color", type=_color, default=_hex_color(defaults.label_color), help="label text colour")
    _ = add("--line-color", type=_color, default=_hex_color(defaults.line_color), help="follow scene: colour of the lines marking a perfectly timed box")
    _ = add("--ffmpeg", metavar="PATH", help="FFmpeg executable or its folder (default: MB_FFMPEG, local.toml, then PATH)")
    _ = add("--config", type=Path, metavar="FILE", help=f"machine-local settings file (default: {DEFAULT_CONFIG.name} in the repository root)")
    _ = add("--preview-png", action="store_true", help="also save each video's first frame as a PNG next to it")
    _ = add("--check-ffmpeg", action="store_true", help="only show which FFmpeg is used and whether it can encode lossless H.264")
    return parser


def select_speeds(args: Arguments) -> tuple[Speed, ...]:
    """The speeds named by --speed, in the order given; "ui" means every ui speed. Raises ValueError for an unknown name. The follow
    scene's default is an illustration speed: an eighth of the width per display frame, so a 1 ms timing error moves a box by
    about 10 px at 1280 wide (3.75 times the speed of Unity's demo, which moves twice the width per second)."""
    if args.scene == "follow" and args.speed == ["all"]:
        per_frame = Fraction(-(-args.width // args.pixel_size), 8)
        return (Speed("eighth-width-per-frame", 1, per_frame * args.fps),)
    # argparse leaves a list default as given (strings)
    ui = [ui_speed(scroll) for scroll in dict.fromkeys(Fraction(scroll) for scroll in args.ui_scroll)]
    speeds = {speed.name: speed for speed in (Speed("normal", args.normal_round_trips), Speed("fast", args.fast_round_trips), *ui)}
    groups = {"all": list(speeds.values()), "ui": list(ui)}
    # slow: the normal timing on a shorter path (a quarter of the travel by default), so low frame rates move in smaller steps.
    # Not part of all, so the default run stays the same
    speeds["slow"] = Speed("slow", args.normal_round_trips, travel=args.slow_travel, travel_share=Fraction(1, 4))
    selected: list[Speed] = []
    for name in args.speed:
        if name in groups:
            selected += groups[name]
        elif name in speeds:
            selected.append(speeds[name])
        else:
            raise ValueError(f"unknown speed {name!r}: use {', '.join([*speeds, 'ui', 'all'])}")
    return tuple(dict.fromkeys(selected))


def _seconds_pair(milliseconds: Sequence[Fraction | str]) -> tuple[Fraction, Fraction]:
    low, high = (Fraction(value) / 1000 for value in milliseconds)
    return low, high


def settings_from_arguments(args: Arguments) -> Settings:
    return Settings(
        top=tuple(dict.fromkeys(top for top, _ in args.pairs)) if args.pairs else MODES if args.top is None else tuple(dict.fromkeys(args.top)),
        bottom=tuple(dict.fromkeys(bottom for _, bottom in args.pairs))
        if args.pairs
        else (MODES if args.bottom is None else tuple(dict.fromkeys(args.bottom))),
        pairs=tuple(dict.fromkeys(args.pairs)) if args.pairs else (),
        web=args.web,
        speeds=select_speeds(args),
        width=args.width,
        height=args.height,
        pixel_size=args.pixel_size,
        fps=args.fps,
        seconds=args.seconds,
        settle=args.settle,
        easing=not args.no_easing,
        # argparse leaves a list default as given (strings)
        wake_noise=_seconds_pair(args.noise_ms),
        frame_cost=args.frame_cost,
        demo_load_share=args.demo_load_share,
        jitter=args.jitter_ms / 1000,
        jitter_pattern=args.jitter_pattern,
        box_size=args.box_size,
        travel=args.travel,
        box_gap=args.box_gap,
        box_spacing=args.box_spacing,
        scene=args.scene,
        background=args.background,
        box_color=args.box_color,
        divider=not args.no_divider,
        divider_color=args.divider_color,
        label_color=args.label_color,
        line_color=args.line_color,
        slow_motions=tuple(dict.fromkeys(args.slow_motion)) if args.slow_motion else (1,),
        follow_stacks=FOLLOW_STACKS if args.follow_boxes is None else (("", tuple(args.follow_boxes)),),
        labels=args.labels,
    )


def parse_arguments(argv: Sequence[str] | None = None) -> tuple[Arguments, Settings]:
    """Parse and validate the command line; invalid settings exit with the usage message like any other argument error."""
    parser = build_parser()
    args = parser.parse_args(argv, namespace=Arguments())
    if args.pairs and (args.top is not None or args.bottom is not None):
        parser.error("use either --pairs or --top/--bottom, not both")
    if args.pairs and args.scene == "follow":
        parser.error("--pairs selects top/bottom pairs; the follow scene has a stack of boxes instead (--follow-boxes)")
    try:
        settings = settings_from_arguments(args)
        validate(settings)
    except ValueError as error:
        parser.error(str(error))
    return args, settings


def check_ffmpeg(args: Arguments) -> int:
    try:
        location = find_ffmpeg(args.ffmpeg, args.config)
        print(f"FFmpeg:  {location.path} (from {location.source})")
        ffprobe = find_ffprobe(location.path)
        print(f"ffprobe: {ffprobe if ffprobe else 'not found (only the tests need it)'}")
        require_lossless_encoder(list_encoders(location.path), location.path)
        print(f"Encoder: {ENCODER} (lossless H.264) is available")
    except (FfmpegError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args, settings = parse_arguments(argv)
    if args.check_ffmpeg:
        return check_ffmpeg(args)

    jobs = plan_videos(settings)
    count = f"{len(jobs)} video" + ("" if len(jobs) == 1 else "s")
    output_dir = args.output_dir.resolve()
    try:
        location = find_ffmpeg(args.ffmpeg, args.config)
        require_lossless_encoder(list_encoders(location.path), location.path)
        print(f"Generating {count} in {output_dir} (FFmpeg: {location.path})")
        # Each group folder (scene, then speed) gets its videos and its own manifest, so runs of other groups leave it alone
        groups: dict[Path, list[VideoJob]] = {}
        for job in jobs:
            groups.setdefault(job.group, []).append(job)
        index = 0
        for group, group_jobs in groups.items():
            folder = output_dir / group
            folder.mkdir(parents=True, exist_ok=True)
            for job in group_jobs:
                index += 1
                speed = job.speed
                seconds = format_number(settings.duration(speed) * job.slow_motion)
                frames = f"{settings.video_frame_count(job)} frames, {seconds} s"
                print(f"[{index}/{len(jobs)}] {group.as_posix()}/{job.filename}: {frames}", flush=True)
                encode_video(location.path, settings, job, folder / job.filename)
                if args.preview_png:
                    renderer = renderer_for(settings, job)
                    preview = renderer.draw(renderer.positions(0))
                    preview.save(folder / f"{Path(job.filename).stem}.png")
            manifest = json.dumps(build_manifest(settings, group_jobs), indent=2) + "\n"
            _ = (folder / MANIFEST_NAME).write_text(manifest, encoding="utf-8")
    except (FfmpegError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    folders = ", ".join(sorted({job.group.as_posix() for job in jobs}))
    print(f"Done: {count} with a {MANIFEST_NAME} per folder in {output_dir} ({folders})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
