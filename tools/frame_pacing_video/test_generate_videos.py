# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""Tests of generate_videos.py. Run from the repository root (in the .venv):
  python -m unittest discover -s tools/frame_pacing_video -v
The encode test needs FFmpeg (found like the generator finds it) and is skipped without it.
"""

import contextlib
import io
import itertools
import json
import os
import re
import subprocess
import tempfile
import unittest
import uuid
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import cast
from unittest import mock

from PIL import Image

import generate_videos as gv
from frame_timing import parse_mode
from mb_framepacing.marker import (
    ON_DEMAND_FRAME_TICKS,
    MarkerFlags,
    MarkerKind,
    Payload,
    PixelFormat,
    Point,
    SequenceId,
    StartMetadata,
    generate_modules,
    modules_to_bitmap,
)
from mb_framepacing.marker import Options as MarkerOptions

SPEEDS = {speed.name: speed for speed in gv.Settings().speeds}
MODE = parse_mode

# Most tests use a 640 x 360 video on the native grid (box 48, spacing 96, travel 384, gap 24, divider 2 px) so their numbers stay
# small; explicit arguments override it. VirtualPixelTests covers the default, 1280 x 720 on a 2 x 2 grid. Names get _px1 on the
# native grid, so the tests of names use the default grid (plain_settings).
NATIVE = ("--pixel-size", "1")
SMALL = ("--width", "640", "--height", "360", *NATIVE)


def settings_for(*argv: str) -> gv.Settings:
    return gv.parse_arguments([*SMALL, *argv])[1]


def settings_for_unvalidated(*argv: str) -> gv.Settings:
    return gv.settings_from_arguments(gv.build_parser().parse_args([*SMALL, *argv], namespace=gv.Arguments()))


def blocky(image: Image.Image, pixel: int) -> Image.Image:
    """The image shrunk to one pixel per pixel x pixel block and enlarged again: unchanged only if it is made of uniform blocks."""
    small = image.resize((image.width // pixel, image.height // pixel), Image.Resampling.NEAREST)  # pyright: ignore[reportUnknownMemberType]
    return small.resize(image.size, Image.Resampling.NEAREST)  # pyright: ignore[reportUnknownMemberType]


def default_settings(*argv: str) -> gv.Settings:
    """Settings at the default 1280 x 720 video size, on the native grid."""
    return gv.parse_arguments([*NATIVE, *argv])[1]


def plain_settings(*argv: str) -> gv.Settings:
    """Settings from the given arguments alone: 1280 x 720 on the default 2 x 2 grid, so names carry no px suffix."""
    return gv.parse_arguments(list(argv))[1]


def runs(values: list[Fraction]) -> list[int]:
    """Lengths of the runs of equal consecutive values."""
    lengths: list[int] = []
    previous: Fraction | None = None
    for value in values:
        if lengths and value == previous:
            lengths[-1] += 1
        else:
            lengths.append(1)
        previous = value
    return lengths


CLIP_FRAMES = 480  # every clip is 8 s at 60 fps
REST = 0.0  # Row offset at rest
PAGED = -384.0  # Row offset after one page to the left: 4 boxes of 96 px


class PlanTests(unittest.TestCase):
    def test_default_is_every_pair_at_every_speed(self) -> None:
        # The ideal timer at 60, 30 and 20 Hz, the naive timer under the three loads at 60 and 30 Hz: 9 x 9 pairs at six speeds
        jobs = gv.plan_videos(plain_settings())
        self.assertEqual([speed.name for speed in plain_settings().speeds], ["normal", "fast", "ui-192", "ui-288", "ui-384", "ui-768"])
        self.assertEqual(len(jobs), 486)
        self.assertEqual(len({job.filename for job in jobs}), 486)
        pattern = re.compile(
            r"^(normal|fast|row_ui-192|row_ui-288|row_ui-384|row_ui-768)_top-(20|60|30|(60|30)-naive-(light|typical|heavy))_bottom-(20|60|30|(60|30)-naive-(light|typical|heavy))\.mp4$"
        )
        for job in jobs:
            self.assertRegex(job.filename, pattern)

    def test_one_speed_gives_81(self) -> None:
        # 9 x 9 pairs: 60, 30, 20 with the ideal timer, 60 and 30 with the naive timer under each load (20 Hz loads and windows opt-in)
        for speed, prefix in (("normal", "normal_"), ("fast", "fast_"), ("ui-384", "row_ui-384_")):
            jobs = gv.plan_videos(settings_for("--speed", speed))
            self.assertEqual(len(jobs), 81)
            self.assertTrue(all(job.filename.startswith(prefix) for job in jobs))
        # ui: every ui speed
        self.assertEqual(len(gv.plan_videos(settings_for("--speed", "ui"))), 4 * 81)

    def test_speed_selection(self) -> None:
        def names(*argv: str) -> list[str]:
            return [speed.name for speed in settings_for(*argv).speeds]

        self.assertEqual(names("--speed", "ui-768", "fast", "ui"), ["ui-768", "fast", "ui-192", "ui-288", "ui-384"])
        self.assertEqual(names("--speed", "ui", "--ui-scroll", "480", "96"), ["ui-480", "ui-96"])
        with contextlib.redirect_stderr(io.StringIO()) as error, self.assertRaises(SystemExit):
            _ = gv.parse_arguments([*SMALL, "--speed", "ui-100"])
        self.assertIn("unknown speed 'ui-100'", error.getvalue())

    def test_slow_is_normal_timing_on_a_shorter_centred_path(self) -> None:
        settings = settings_for("--speed", "slow", "normal")
        slow, normal = settings.speeds
        self.assertEqual((slow.name, settings.period(slow), settings.move_time(slow)), ("slow", settings.period(normal), settings.move_time(normal)))
        # A quarter of the travel by default, or --slow-travel; not part of all
        self.assertEqual((settings.travel_for(slow), settings.travel_for(normal)), (96, 384))
        custom = settings_for("--speed", "slow", "--slow-travel", "40")
        self.assertEqual(custom.travel_for(custom.speeds[0]), 40)
        self.assertNotIn("slow", [speed.name for speed in settings_for().speeds])
        self.assertEqual(max(abs(offset) for offset in [gv.row_offset(settings, MODE("60"), slow, frame) for frame in range(CLIP_FRAMES)]), 96)

    def test_groups_are_folders_by_scene_and_speed(self) -> None:
        def groups(*argv: str) -> list[str]:
            return sorted({job.group.as_posix() for job in gv.plan_videos(plain_settings(*argv))})

        # The ui speeds always scroll a row
        self.assertEqual(groups(), ["box/fast", "box/normal", "row/ui-192", "row/ui-288", "row/ui-384", "row/ui-768"])
        self.assertEqual(groups("--speed", "fast", "--labels"), ["box-labels/fast"])
        self.assertEqual(groups("--speed", "ui-384", "normal", "--scene", "row"), ["row/normal", "row/ui-384"])

    def test_matrix_override(self) -> None:
        jobs = gv.plan_videos(plain_settings("--top", "60", "--bottom", "20-naive-heavy", "30", "--speed", "normal"))
        self.assertEqual([job.filename for job in jobs], ["normal_top-60_bottom-20-naive-heavy.mp4", "normal_top-60_bottom-30.mp4"])
        with contextlib.redirect_stderr(io.StringIO()) as error, self.assertRaises(SystemExit):
            _ = gv.parse_arguments([*SMALL, "--top", "60-late"])
        self.assertIn("'60-late' is not a mode", error.getvalue())

    def test_pairs(self) -> None:
        jobs = gv.plan_videos(plain_settings("--pairs", "60:60-naive-4ms", "60-naive-4ms:60", "60:60", "--speed", "normal"))
        self.assertEqual(
            [job.filename for job in jobs],
            ["normal_top-60_bottom-60-naive-4ms.mp4", "normal_top-60-naive-4ms_bottom-60.mp4", "normal_top-60_bottom-60.mp4"],
        )
        for argv, message in (
            (["--pairs", "60"], "is not a pair"),
            (["--pairs", "60:60-late"], "'60-late' is not a mode"),
            (["--pairs", "60:30", "--top", "60"], "either --pairs or --top/--bottom"),
            (["--pairs", "60:60", "--scene", "follow"], "the follow scene"),
        ):
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()) as error, self.assertRaises(SystemExit):
                _ = gv.parse_arguments([*SMALL, *argv])
            self.assertIn(message, error.getvalue())

    def test_web_encoding(self) -> None:
        output = Path("clip.mp4")
        lossless = gv.encoder_command(Path("ffmpeg"), plain_settings(), 10, output)
        web = gv.encoder_command(Path("ffmpeg"), plain_settings("--web"), 10, output)
        self.assertIn("yuv444p", lossless)
        self.assertIn("-qp", lossless)
        self.assertIn("yuv420p", web)
        self.assertEqual(web[web.index("-crf") + 1], str(gv.WEB_CRF))
        self.assertEqual(web[web.index("-profile:v") + 1], "high")
        self.assertNotIn("-qp", web)
        manifest = gv.build_manifest(plain_settings("--web"), [])
        settings = cast(dict[str, object], manifest["settings"])
        self.assertEqual((settings["pixelFormat"], settings["web"]), ("yuv420p", True))

    def test_manifest(self) -> None:
        settings = plain_settings("--top", "60", "--bottom", "30-naive-heavy")
        manifest = cast(dict[str, object], json.loads(json.dumps(gv.build_manifest(settings, gv.plan_videos(settings)))))
        videos = cast(list[dict[str, object]], manifest["videos"])
        self.assertEqual(
            [video["file"] for video in videos][:3],
            ["normal_top-60_bottom-30-naive-heavy.mp4", "fast_top-60_bottom-30-naive-heavy.mp4", "row_ui-192_top-60_bottom-30-naive-heavy.mp4"],
        )
        normal, fast, ui = videos[0], videos[1], videos[-1]
        # ui-768: a row scrolling 768 px/s for the whole 8 s, never resting
        self.assertEqual(
            (ui["scene"], ui["scrollVirtualPixelsPerSecond"], ui["moveSeconds"], ui["settleSeconds"], ui["durationSeconds"], ui["frameCount"]),
            ("row", 768, 8, 0, 8, CLIP_FRAMES),
        )
        self.assertEqual((normal["scene"], normal["scrollVirtualPixelsPerSecond"]), ("box", None))
        # Every clip is 8 s: 2 round trips of 4 s at normal (1.9 s per move), 4 of 2 s at fast (0.9 s), each with 0.1 s rests
        self.assertEqual((normal["durationSeconds"], normal["frameCount"], normal["roundTrips"], normal["roundTripSeconds"]), (8, CLIP_FRAMES, 2, 4))
        self.assertEqual((fast["roundTrips"], fast["roundTripSeconds"], fast["moveSeconds"], ui["roundTrips"]), (4, 2, 0.9, None))
        bottom = cast(dict[str, object], normal["bottom"])
        self.assertEqual(
            {key: bottom[key] for key in ("mode", "rate", "timer", "noise", "label")},
            {"mode": "30-naive-heavy", "rate": 30, "timer": "naive", "noise": "heavy", "label": "30 Hz naive timer, heavy load"},
        )
        frames = cast(dict[str, list[float]], bottom["frames"])
        self.assertEqual(frames["refresh"][:3], [0, 2, 4])
        self.assertEqual([len(frames[key]) for key in ("sampleMs", "dtMs", "animationErrorMs")], [240, 240, 240])
        # The dts add up to the clip (each is rounded to a microsecond in the manifest)
        self.assertAlmostEqual(sum(frames["dtMs"]), 8000, delta=0.1)
        # The naive loop reads the clock a little after the previous flip: frame 1 after the flip at 0 ms (the usual 2 ms of work,
        # up to 2 ms sooner or 8 ms later)
        self.assertTrue(0 <= frames["sampleMs"][1] <= 10)
        top_frames = cast(dict[str, list[float]], cast(dict[str, object], normal["top"])["frames"])
        self.assertEqual(set(top_frames["animationErrorMs"]), {0})
        settings_entry = cast(dict[str, object], manifest["settings"])
        self.assertEqual((settings_entry["width"], settings_entry["height"], settings_entry["fps"], settings_entry["travel"]), (1280, 720, 60, 384))
        self.assertEqual((settings_entry["clipSeconds"], settings_entry["settleSeconds"], settings_entry["frameCost"]), (8, 0.1, 0.3))
        self.assertEqual((settings_entry["wakeNoiseMs"], settings_entry["easing"]), ([0, 0.3], True))
        self.assertEqual((settings_entry["background"], settings_entry["boxColor"]), ("#303030", "#D0D0D0"))


class TimingTests(unittest.TestCase):
    def shown(self, name: str, *argv: str) -> list[Fraction]:
        """Animation time of each output frame of a normal clip."""
        settings = settings_for(*argv)
        return [gv.content_time(settings, MODE(name), SPEEDS["normal"], frame) for frame in range(CLIP_FRAMES)]

    def test_ideal_modes_hold_each_frame_evenly_and_show_its_display_time(self) -> None:
        for name, hold in (("60", 1), ("30", 2), ("20", 3)):
            self.assertEqual(set(runs(self.shown(name))), {hold}, name)
            self.assertEqual(self.shown(name)[hold], Fraction(1, 60 // hold), name)
            errors = gv.animation_errors(settings_for(), MODE(name), SPEEDS["normal"])
            self.assertEqual(set(errors), {0}, name)

    def test_the_naive_timer_changes_on_the_same_frames_but_shows_the_wall_clock(self) -> None:
        # Rendering always fits: nothing late, repeated or skipped, only the animation time is off
        for rate in (60, 30, 20):
            ideal = self.shown(str(rate))
            for noise in ("typical", "heavy", "1ms"):
                naive = self.shown(f"{rate}-naive-{noise}")
                self.assertEqual(runs(naive), runs(ideal), (rate, noise))
                errors = [a - b for a, b in zip(naive, ideal, strict=True)]
                self.assertTrue(any(error > 0 for error in errors) and any(error < 0 for error in errors), (rate, noise))
                # Off by how much sooner or later than usual the loop read the clock: up to about 2 ms under typical load
                if noise == "typical":
                    self.assertTrue(all(abs(error) < Fraction(25, 10_000) for error in errors), rate)

    def test_a_frame_is_late_when_flipped_after_the_refresh_it_was_rendered_for(self) -> None:
        settings = settings_for()
        # Evenly paced, and the naive timer's frames all make their vsync: none late, however far off their animation time
        for name in ("60", "30", "60-naive-5ms"):
            self.assertEqual(set(gv.refreshes_late(settings, MODE(name), SPEEDS["normal"])), {0}, name)
        # Slow frames: a few frames a refresh late, the rest on time
        late = gv.refreshes_late(settings, MODE("60-diagram-slow-frames"), SPEEDS["normal"])
        self.assertEqual(set(late), {0, 1})

    def test_the_perfect_storm_has_the_diagrams_late_frames_and_the_naive_timers_jitter(self) -> None:
        settings, speed = settings_for(), SPEEDS["normal"]
        storm, slow = MODE("60-naive-5ms-diagram-slow-frames-every-1s"), MODE("60-diagram-slow-frames-every-1s")
        self.assertEqual(storm.window, Fraction(5, 1000))
        # The same frames flipped on the same refreshes, late as often
        self.assertEqual(gv.simulated_frames(settings, storm, speed).flips, gv.simulated_frames(settings, slow, speed).flips)
        self.assertEqual(gv.refreshes_late(settings, storm, speed), gv.refreshes_late(settings, slow, speed))
        # And every frame's moment a little off: animation error on nearly every frame, not only around the late ones
        errors = gv.animation_errors(settings, storm, speed)
        self.assertGreater(sum(error != 0 for error in errors), len(errors) * 9 // 10)
        self.assertIn("naive timer ±5 ms", settings.label(storm))

    def test_heavy_load_makes_millisecond_spikes(self) -> None:
        errors = gv.animation_errors(settings_for(), MODE("60-naive-heavy"), SPEEDS["normal"])
        self.assertGreater(max(abs(error) for error in errors if error is not None), Fraction(3, 1000))

    def test_noise_options(self) -> None:
        settings = settings_for("--noise-ms", "0.2", "0.4", "--frame-cost", "0.25")
        self.assertEqual((settings.timing.noise, settings.timing.frame_cost), ((Fraction(2, 10_000), Fraction(4, 10_000)), Fraction(1, 4)))
        with contextlib.redirect_stderr(io.StringIO()) as error, self.assertRaises(SystemExit):
            _ = gv.parse_arguments([*SMALL, "--frame-cost", "0.9", "--top", "60-naive-heavy"])
        self.assertIn("would miss a vsync", error.getvalue())

    def test_labels(self) -> None:
        settings = settings_for()
        self.assertEqual(settings.label(MODE("60")), "60 Hz ideal timer")
        self.assertEqual(settings.label(MODE("20-naive-typical")), "20 Hz naive timer, typical load")
        self.assertEqual(settings.label(MODE("60-naive-4ms")), "60 Hz naive timer, ±4 ms mixed")
        self.assertEqual(settings_for("--jitter-ms", "0.5").label(MODE("60-naive-synthetic")), "60 Hz naive timer, synthetic ±0.5 ms mixed")

    def test_row_scene_file_names(self) -> None:
        jobs = gv.plan_videos(plain_settings("--scene", "row", "--top", "60", "--bottom", "60-naive-heavy", "--speed", "normal"))
        self.assertEqual([job.filename for job in jobs], ["row_normal_top-60_bottom-60-naive-heavy.mp4"])
        # A single synthetic pattern shows in the name only when a synthetic mode uses it
        jobs = gv.plan_videos(plain_settings("--top", "60", "--bottom", "60-naive-synthetic", "--speed", "normal", "--jitter-pattern", "random"))
        self.assertEqual(jobs[0].filename, "normal_top-60_bottom-60-naive-synthetic_random.mp4")
        jobs = gv.plan_videos(plain_settings("--top", "60", "--bottom", "60", "--speed", "normal", "--jitter-pattern", "random"))
        self.assertEqual(jobs[0].filename, "normal_top-60_bottom-60.mp4")


class MotionTests(unittest.TestCase):
    def offsets(self, *argv: str, mode: str = "60", speed: str = "normal") -> list[float]:
        settings = settings_for(*argv)
        return [gv.row_offset(settings, MODE(mode), SPEEDS[speed], frame) for frame in range(settings.frame_count(SPEEDS[speed]))]

    def test_the_row_rests_at_both_ends(self) -> None:
        offsets = self.offsets()
        # Normal: two round trips of 4 s. A clip starts and ends in the middle of the 0.1 s rest: rest (frames 0-3), 1.9 s paging
        # left (3-117), rest (117-123), 1.9 s back (123-237), rest (237-243), and the same again from 240
        self.assertEqual(set(offsets[0:4] + offsets[237:244] + offsets[477:480]), {REST})
        self.assertEqual(set(offsets[117:124] + offsets[357:364]), {PAGED})
        moving = offsets[4:117] + offsets[124:237] + offsets[244:357] + offsets[364:477]
        self.assertTrue(all(PAGED < offset < REST for offset in moving))

    def test_one_page_is_four_boxes(self) -> None:
        settings = settings_for()
        self.assertEqual((settings.resolved_spacing, settings.resolved_travel), (96, 384))
        self.assertEqual((min(self.offsets()), max(self.offsets())), (PAGED, REST))
        self.assertEqual(settings_for("--box-spacing", "80", "--speed", "normal").resolved_travel, 320)

    def test_eased_motion_starts_and_stops_gently(self) -> None:
        steps = [a - b for a, b in itertools.pairwise(self.offsets()[3:118])]
        self.assertLess(steps[0], 0.1)
        self.assertLess(steps[-1], 0.1)
        peak = steps.index(max(steps))
        self.assertTrue(55 <= peak <= 58, peak)
        self.assertEqual(steps[: peak + 1], sorted(steps[: peak + 1]))
        self.assertEqual(steps[peak:], sorted(steps[peak:], reverse=True))

    def test_without_easing_the_speed_is_constant(self) -> None:
        steps = {round(a - b, 9) for a, b in itertools.pairwise(self.offsets("--no-easing")[3:118])}
        self.assertEqual(steps, {round(384 / 114, 9)})

    def test_sub_pixel_positions(self) -> None:
        self.assertTrue(any(offset != int(offset) for offset in self.offsets()))

    def test_heavy_load_moves_the_box_off_its_perfect_position(self) -> None:
        differences = [abs(a - b) for a, b in zip(self.offsets(), self.offsets(mode="60-naive-heavy"), strict=True)]
        self.assertGreater(max(differences), 0.3)
        # Never more than the largest wake-up difference times the fastest speed (384 px in 1.9 s, eased: pi / 2 times the average)
        self.assertLess(max(differences), 0.010 * 384 / 1.9 * 1.5708 + 1e-9)


class ClipLengthTests(unittest.TestCase):
    def test_every_clip_is_8_seconds(self) -> None:
        settings = settings_for()
        self.assertEqual([settings.frame_count(speed) for speed in settings.speeds], [CLIP_FRAMES] * 6)
        # The eased speeds fit whole round trips in it, with 0.1 s rests: normal 2 round trips (1.9 s per move), fast 4 (0.9 s)
        self.assertEqual([(settings.period(speed), settings.move_time(speed)) for speed in settings.speeds[:2]], [(4, Fraction(19, 10)), (2, Fraction(9, 10))])

    def test_ui_speeds_scroll_a_row_right_to_left_at_constant_speed(self) -> None:
        settings = settings_for("--speed", "ui")
        for speed, scroll in zip(settings.speeds, (192, 288, 384, 768), strict=True):
            self.assertEqual((settings.scene_for(speed), settings.settle_for(speed)), ("row", 0))
            # The row's shift within one box spacing (the row repeats every 96 px)
            xs = [gv.row_offset(settings, MODE("60"), speed, frame) for frame in range(settings.frame_count(speed))]
            self.assertTrue(all(-96 < x <= 0 for x in xs))
            # Every step moves the row left by exactly scroll / 60 px (modulo the spacing)
            steps = {round((a - b) % 96, 9) for a, b in itertools.pairwise(xs)}
            self.assertEqual(steps, {round(scroll / 60, 9)}, speed.name)
            # A perfect 20 Hz row holds each position for 3 frames and moves 3 times as far
            xs = [gv.row_offset(settings, MODE("20"), speed, frame) for frame in range(settings.frame_count(speed))]
            self.assertEqual({round((a - b) % 96, 9) for a, b in itertools.pairwise(xs[::3])}, {round(scroll / 20, 9)})
        # The --scene option applies to normal and fast only
        self.assertEqual([job.scene for job in gv.plan_videos(settings_for("--top", "60", "--bottom", "60"))], ["box", "box", "row", "row", "row", "row"])
        settings = settings_for("--speed", "ui", "--ui-scroll", "480", "--seconds", "1")
        self.assertEqual([speed.name for speed in settings.speeds], ["ui-480"])
        self.assertEqual(settings.frame_count(settings.speeds[0]), 60)

    def test_a_ui_scroll_must_loop(self) -> None:
        with self.assertRaisesRegex(ValueError, "ui-100 scrolls 800 virtual px per clip, which must be a whole number of box spacings"):
            gv.validate(settings_for_unvalidated("--speed", "ui", "--ui-scroll", "100"))

    def test_overrides(self) -> None:
        settings = settings_for("--normal-round-trips", "1", "--fast-round-trips", "8")
        self.assertEqual([(settings.period(speed), settings.move_time(speed)) for speed in settings.speeds[:2]], [(8, Fraction(39, 10)), (1, Fraction(2, 5))])
        settings = settings_for("--seconds", "4")
        self.assertEqual([settings.frame_count(speed) for speed in settings.speeds], [240] * 6)
        self.assertEqual(settings.move_time(settings.speeds[0]), Fraction(9, 10))
        # 40 round trips of 0.2 s leave no time to move between the 0.1 s rests
        with self.assertRaisesRegex(ValueError, "fast speed's round trips must fit the clip"):
            gv.validate(settings_for_unvalidated("--fast-round-trips", "40"))

    def test_each_clip_is_whole_round_trips(self) -> None:
        settings = settings_for()
        self.assertEqual([settings.duration(speed) / settings.period(speed) for speed in settings.speeds[:2]], [2, 4])


class LoopTests(unittest.TestCase):
    def test_every_mode_and_speed_loops_seamlessly(self) -> None:
        settings = settings_for()
        for speed in settings.speeds:
            frames = settings.frame_count(speed)
            for mode in (*gv.MODES, MODE("60-naive-synthetic"), MODE("30-naive-synthetic")):
                first = [gv.row_offset(settings, mode, speed, frame) for frame in range(frames)]
                second = [gv.row_offset(settings, mode, speed, frame) for frame in range(frames, 2 * frames)]
                self.assertEqual(first, second, f"{mode.name} at {speed.name}")


class ValidationTests(unittest.TestCase):
    def assert_rejected(self, *argv: str, message: str) -> None:
        with self.assertRaises(ValueError) as caught:
            gv.validate(settings_for_unvalidated(*argv))
        self.assertIn(message, str(caught.exception))

    def test_fps_must_be_a_multiple_of_the_rates(self) -> None:
        self.assert_rejected("--fps", "50", message="not a whole multiple of 60 Hz")
        self.assert_rejected("--fps", "50", "--top", "60-naive-heavy", "--bottom", "60-naive-heavy", message="not a whole multiple of 60 Hz")
        # 120 fps suits 60, 30 and 20 Hz; 100 fps suits 20 Hz only
        gv.validate(settings_for("--fps", "120"))
        gv.validate(settings_for("--fps", "100", "--top", "20", "--bottom", "20-naive-heavy", "--speed", "normal"))

    def test_synthetic_jitter_must_stay_below_half_a_frame(self) -> None:
        self.assert_rejected("--jitter-ms", "9", "--top", "60-naive-synthetic", message="less than half the 60 Hz frame time")
        gv.validate(settings_for("--jitter-ms", "9", "--top", "30-naive-synthetic", "--bottom", "20"))

    def test_any_whole_number_of_updates_works_with_the_naive_timer(self) -> None:
        # 4.5 s at 30 Hz is 135 frames: the noise is drawn per clip, so no cycle length has to fit (the eased speeds only: a ui
        # scroll must move whole box spacings per clip)
        gv.validate(settings_for("--top", "30-naive-heavy", "--bottom", "20-naive-4ms", "--seconds", "4.5", "--settle", "0", "--speed", "normal", "fast"))

    def test_clip_must_be_whole_frames(self) -> None:
        self.assert_rejected("--seconds", "1/7", "--scene", "follow", "--follow-boxes", "60", message="not a whole number of frames")

    def test_modes_need_whole_updates_per_clip(self) -> None:
        self.assert_rejected("--seconds", "1/60", "--scene", "follow", "--follow-boxes", "20", message="whole number of updates")

    def test_box_must_fit(self) -> None:
        self.assert_rejected("--box-size", "200", message="does not fit in the height 360")
        self.assert_rejected("--box-spacing", "48", message="the box spacing 48 must be larger than the box size 48")
        self.assert_rejected("--travel", "600", message="does not fit in the width 640")
        self.assert_rejected("--speed", "slow", "--slow-travel", "600", message="does not fit in the width 640")
        gv.validate(settings_for("--travel", "600", "--scene", "row"))
        gv.validate(settings_for("--travel", "600", "--speed", "ui"))

    def test_command_line_reports_invalid_settings(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()) as stderr, self.assertRaises(SystemExit) as caught:
            _ = gv.parse_arguments(["--fps", "50"])
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("not a whole multiple of 60 Hz", stderr.getvalue())


class RenderTests(unittest.TestCase):
    def test_one_box_by_default(self) -> None:
        settings = settings_for("--top", "60", "--bottom", "30", "--no-divider")
        renderer = gv.FrameRenderer(settings, gv.plan_videos(settings)[0])
        # The box's path is centred: 104 at rest, 488 after the move to the right
        self.assertEqual(renderer.box_lefts(0), [104])
        self.assertEqual(renderer.box_lefts(-384), [488])
        image = renderer.render(0, -384)
        colors = {color for _, color in cast(list[tuple[int, tuple[int, int, int]]], image.getcolors())}
        self.assertEqual(colors, {settings.background, settings.box_color})
        top_y, bottom_y = settings.box_rows
        self.assertEqual(image.getpixel((104, top_y)), settings.box_color)
        self.assertEqual(image.getpixel((200, top_y)), settings.background)
        self.assertEqual(image.getpixel((488, bottom_y)), settings.box_color)
        self.assertEqual(image.getpixel((104, bottom_y)), settings.background)

    def test_rows_of_boxes(self) -> None:
        settings = settings_for("--top", "60", "--bottom", "30", "--no-divider", "--scene", "row")
        job = gv.plan_videos(settings)[0]
        renderer = gv.FrameRenderer(settings, job)
        # At rest one box is centred (296) and the others follow every 96 px, past both frame edges
        self.assertEqual(renderer.box_lefts(0), [8, 104, 200, 296, 392, 488, 584])
        self.assertEqual(renderer.box_lefts(-48)[:2], [-40, 56])
        image = renderer.render(0, -48)
        # Away from the faded edges, only background and boxes
        inner = image.crop((64, 0, 576, settings.height))
        colors = {color for _, color in cast(list[tuple[int, tuple[int, int, int]]], inner.getcolors())}
        self.assertEqual(colors, {settings.background, settings.box_color})
        top_y, bottom_y = settings.box_rows
        for x, expected in ((103, settings.background), (104, settings.box_color), (151, settings.box_color), (152, settings.background)):
            self.assertEqual(image.getpixel((x, top_y)), expected, x)
        # The bottom row is shifted half a spacing to the left
        self.assertEqual(image.getpixel((248, bottom_y)), settings.box_color)
        self.assertEqual(image.getpixel((296, bottom_y)), settings.background)

    def test_default_colours_are_neutral_grays_with_clear_contrast(self) -> None:
        settings = settings_for()

        def luminance(color: tuple[int, int, int]) -> float:
            """Relative luminance (WCAG) of a gray."""
            value = color[0] / 255
            return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

        # Neutral, and away from black and white: inside video range (16-235), so nothing clips in re-encoded web video
        for color in (settings.background, settings.box_color, settings.divider_color, settings.label_color):
            self.assertEqual(len(set(color)), 1)
            self.assertTrue(16 < color[0] < 235)
        self.assertLess(settings.background[0], settings.divider_color[0])
        self.assertLess(settings.divider_color[0], settings.box_color[0])
        # Boxes on the background: about 8.5:1
        contrast = (luminance(settings.box_color) + 0.05) / (luminance(settings.background) + 0.05)
        self.assertTrue(8 < contrast < 9, contrast)

    def test_a_box_between_pixels_blends_its_edge_columns(self) -> None:
        settings = settings_for("--no-divider", "--scene", "row")
        image = gv.FrameRenderer(settings, gv.plan_videos(settings)[0]).render(0.25, 0)
        top_y = settings.box_rows[0]
        # 48 background, 208 box: the centred box now starts at 296.25; its first column is 3/4 covered, the column after it 1/4
        self.assertEqual(image.getpixel((296, top_y)), (168, 168, 168))
        self.assertEqual(image.getpixel((297, top_y)), settings.box_color)
        self.assertEqual(image.getpixel((343, top_y)), settings.box_color)
        self.assertEqual(image.getpixel((344, top_y)), (88, 88, 88))
        self.assertEqual(image.getpixel((345, top_y)), settings.background)

    def test_boxes_fade_at_the_frame_edges(self) -> None:
        settings = settings_for("--no-divider", "--scene", "row")
        image = gv.FrameRenderer(settings, gv.plan_videos(settings)[0]).render(0, 0)
        top_y = settings.box_rows[0]
        row = [cast(tuple[int, int, int], image.getpixel((x, top_y)))[0] for x in range(settings.width)]
        # Symmetric (one box is centred), the outermost boxes faded to within a sixteenth of the contrast of the background, the
        # inner boxes untouched
        self.assertEqual(row, row[::-1])
        self.assertLessEqual(row[8] - settings.background[0], (settings.box_color[0] - settings.background[0]) / 16)
        self.assertEqual(row[104], settings.box_color[0])
        self.assertEqual(row[8:56], sorted(row[8:56]))

    def test_boxes_sit_next_to_the_divider(self) -> None:
        settings = settings_for()
        first, thickness = settings.divider_rows
        top_y, bottom_y = settings.box_rows
        self.assertEqual((first, thickness), (179, 2))
        # 24 px (half a box) between each box and the divider, and the same space above and below the pair
        self.assertEqual(first - (top_y + settings.band_height), 24)
        self.assertEqual(bottom_y - (first + thickness), 24)
        self.assertEqual(top_y, settings.height - (bottom_y + settings.band_height))
        with self.assertRaisesRegex(ValueError, "does not fit in the height"):
            gv.validate(settings_for_unvalidated("--box-gap", "200"))

    def test_divider_fades_in_at_both_ends(self) -> None:
        settings = settings_for()
        image = gv.FrameRenderer(settings, gv.plan_videos(settings)[0]).render(0, 0)
        first, thickness = settings.divider_rows
        row = [cast(tuple[int, int, int], image.getpixel((x, first)))[0] for x in range(settings.width)]
        self.assertEqual(row, [cast(tuple[int, int, int], image.getpixel((x, first + thickness - 1)))[0] for x in range(settings.width)])
        fade = settings.width // 10
        self.assertEqual(row[settings.width // 2], settings.divider_color[0])
        self.assertEqual(row[fade:-fade], [settings.divider_color[0]] * (settings.width - 2 * fade))
        self.assertLess(row[0] - settings.background[0], 2)
        self.assertEqual(row, row[::-1])
        self.assertEqual(row[: fade + 1], sorted(row[: fade + 1]))
        self.assertEqual(image.getpixel((settings.width // 2, first - 1)), settings.background)
        self.assertEqual(image.getpixel((settings.width // 2, first + thickness)), settings.background)

    def test_labels_sit_next_to_the_boxes(self) -> None:
        settings = settings_for("--top", "60", "--bottom", "30-naive-heavy", "--labels")
        job = gv.plan_videos(settings)[0]
        image = gv.FrameRenderer(settings, job).render(0, 0)
        top_y, bottom_y = settings.box_rows

        def text_pixels(first: int, last: int) -> list[tuple[int, int]]:
            return [(x, y) for y in range(first, last) for x in range(settings.width) if image.getpixel((x, y)) == settings.label_color]

        def rows_with_text(first: int, last: int) -> list[int]:
            return sorted({y for _, y in text_pixels(first, last)})

        # Above the top box's path (within 40 px of it) and below the bottom box's path, never overlapping the boxes' rows
        above = rows_with_text(0, top_y)
        below = rows_with_text(bottom_y + settings.band_height, settings.height)
        self.assertTrue(above and top_y - 40 < min(above) and max(above) < top_y)
        self.assertTrue(below and bottom_y + settings.band_height < min(below) and max(below) < bottom_y + settings.band_height + 40)
        self.assertEqual(rows_with_text(top_y, top_y + settings.band_height) + rows_with_text(bottom_y, bottom_y + settings.band_height), [])
        # Centred horizontally
        for first, last in ((0, top_y), (bottom_y + settings.band_height, settings.height)):
            xs = [x for x, _ in text_pixels(first, last)]
            self.assertLess(abs((min(xs) + max(xs)) / 2 - settings.width / 2), 3)

    def test_frames_are_raw_rgb(self) -> None:
        settings = settings_for("--top", "60", "--bottom", "20", "--speed", "fast")
        frames = list(gv.clip_frames(settings, gv.plan_videos(settings)[0]))
        self.assertEqual(len(frames), CLIP_FRAMES)
        self.assertTrue(all(len(frame) == 640 * 360 * 3 for frame in frames))


class VirtualPixelTests(unittest.TestCase):
    def test_default_is_1280_by_720_on_a_2_by_2_grid(self) -> None:
        settings = plain_settings()
        self.assertEqual((settings.width, settings.height, settings.pixel_size, settings.canvas), (1280, 720, 2, (640, 360)))
        # In virtual pixels; the divider in video pixels
        layout = (settings.resolved_box_size, settings.resolved_spacing, settings.resolved_travel, settings.resolved_box_gap)
        self.assertEqual(layout, (48, 96, 384, 24))
        self.assertEqual(settings.divider_rows, (358, 4))

    def test_the_layout_follows_the_canvas(self) -> None:
        # Box = 2/15 of the canvas height, in whole virtual pixels; a band is always about the same height in video pixels
        for pixel, canvas, box in ((2, (640, 360), 48), (3, (427, 240), 32), (4, (320, 180), 24)):
            settings = default_settings("--pixel-size", str(pixel))
            self.assertEqual((settings.canvas, settings.resolved_box_size, settings.resolved_spacing), (canvas, box, 2 * box), pixel)
            self.assertEqual(settings.band_height, 96, pixel)
        self.assertEqual(default_settings("--pixel-size", "4", "--box-size", "32").resolved_spacing, 64)
        # A scroll that does not move whole spacings per clip is rejected (box 19, spacing 38 at pixel size 5)
        with self.assertRaisesRegex(ValueError, "ui-192 scrolls 1536 virtual px per clip, which must be a whole number of box spacings \\(38"):
            gv.validate(gv.settings_from_arguments(gv.build_parser().parse_args(["--pixel-size", "5"], namespace=gv.Arguments())))

    def render(self, pixel: int, offset: float = -10.3) -> tuple[gv.Settings, Image.Image]:
        settings = default_settings("--pixel-size", str(pixel), "--speed", "ui-384", "--top", "60", "--bottom", "60", "--labels")
        return settings, gv.FrameRenderer(settings, gv.plan_videos(settings)[0]).render(offset, offset)

    def test_rows_are_drawn_on_the_virtual_pixel_grid(self) -> None:
        for pixel in (1, 2, 3, 4):
            settings, image = self.render(pixel)
            self.assertEqual(image.size, (1280, 720), pixel)
            top_y, _ = settings.box_rows
            band = image.crop((0, top_y, 1280, top_y + settings.band_height))
            # Every virtual pixel is a uniform block: shrinking and enlarging again changes nothing (pixel size 3 is cropped by one
            # video pixel at the right)
            blocks = band.crop((0, 0, 1280 // pixel * pixel, band.height))
            self.assertEqual(blocky(blocks, pixel).tobytes(), blocks.tobytes(), pixel)
            # The box edges are blended per virtual pixel
            colors = {color for _, color in cast(list[tuple[int, tuple[int, int, int]]], band.getcolors(1 << 16))}
            self.assertGreater(len(colors - {settings.background, settings.box_color}), 0, pixel)

    def test_divider_and_labels_are_native(self) -> None:
        settings, image = self.render(4)
        first, thickness = settings.divider_rows
        # 4 video pixels thick, starting off the 4 x 4 grid
        column = [image.getpixel((640, y)) for y in range(first - 1, first + thickness + 1)]
        self.assertEqual(column, [settings.background, *[settings.divider_color] * 4, settings.background])
        self.assertNotEqual(first % 4, 0)
        # The label text is drawn at video resolution, so it is not made of 4 x 4 blocks
        top_y, _ = settings.box_rows
        label = image.crop((0, 0, 1280, top_y))
        self.assertNotEqual(blocky(label, 4).tobytes(), label.tobytes())

    def test_a_coarser_grid_moves_more_video_pixels_for_the_same_speed(self) -> None:
        # ui speeds are in virtual pixels per second: every step (and so every timing error) is the same in virtual pixels, so at
        # pixel size 4 it covers 4 times as many video pixels
        mode, speed = MODE("60-naive-heavy"), SPEEDS["ui-384"]

        def steps(settings: gv.Settings) -> list[float]:
            offsets = [gv.row_offset(settings, mode, speed, frame) for frame in range(121)]
            return [round((a - b) % settings.resolved_spacing, 9) for a, b in itertools.pairwise(offsets)]

        native, coarse = steps(default_settings()), steps(default_settings("--pixel-size", "4"))
        self.assertEqual(native, coarse)
        # The average step is off by the last frame's timing error minus the first's, over 120 frames: heavy load's errors lie
        # within about 10 ms of each other (2 ms early to an 8 ms spike), at 384 px/s
        self.assertLess(abs(sum(native) / len(native) - 384 / 60), 384 * 0.010 / 120)

    def test_names_and_manifest(self) -> None:
        settings = default_settings("--pixel-size", "4", "--speed", "ui-384", "--top", "60", "--bottom", "30", "--labels")
        [job] = gv.plan_videos(settings)
        self.assertEqual((job.group.as_posix(), job.filename), ("row-labels-px4/ui-384", "row_ui-384_top-60_bottom-30_px4.mp4"))
        # The native grid is not the default either
        [job] = gv.plan_videos(default_settings("--speed", "ui-384", "--top", "60", "--bottom", "30"))
        self.assertEqual((job.group.as_posix(), job.filename), ("row-px1/ui-384", "row_ui-384_top-60_bottom-30_px1.mp4"))
        entry = cast(dict[str, object], gv.build_manifest(settings, [job])["settings"])
        self.assertEqual((entry["pixelSize"], entry["canvas"], entry["boxSize"], entry["width"]), (4, [320, 180], 24, 1280))


class FollowTests(unittest.TestCase):
    def settings(self, *argv: str) -> gv.Settings:
        return default_settings("--scene", "follow", *argv)

    def test_three_videos_at_real_speed(self) -> None:
        jobs = gv.plan_videos(plain_settings("--scene", "follow", "--labels"))
        self.assertEqual(
            [(job.group.as_posix(), job.filename) for job in jobs],
            [
                ("follow-labels/eighth-width-per-frame", "follow_eighth-width-per-frame.mp4"),
                ("follow-labels/eighth-width-per-frame", "follow-realistic_eighth-width-per-frame.mp4"),
                ("follow-labels/eighth-width-per-frame", "follow-extreme_eighth-width-per-frame.mp4"),
            ],
        )
        # --slow-motion adds slowed down copies, in their own folders
        slowed = gv.plan_videos(plain_settings("--scene", "follow", "--labels", "--slow-motion", "1", "10"))
        self.assertEqual(
            [(job.group.as_posix(), job.filename) for job in slowed[3:]],
            [
                ("follow-labels-slow10/eighth-width-per-frame", "follow_eighth-width-per-frame_slow10.mp4"),
                ("follow-labels-slow10/eighth-width-per-frame", "follow-realistic_eighth-width-per-frame_slow10.mp4"),
                ("follow-labels-slow10/eighth-width-per-frame", "follow-extreme_eighth-width-per-frame_slow10.mp4"),
            ],
        )
        # The loads (the demo profile), the realistic loads, and the extreme cases
        self.assertEqual([box.name for box in jobs[0].boxes], ["60", "60-naive-light", "60-naive-typical", "60-naive-heavy"])
        self.assertEqual([box.name for box in jobs[1].boxes], ["60", "60-naive-light-realistic", "60-naive-typical-realistic", "60-naive-heavy-realistic"])
        self.assertEqual([box.name for box in jobs[2].boxes], ["60", "60-naive-1ms", "60-naive-2ms", "60-naive-3ms", "60-naive-4ms"])
        # An eighth of the width per frame (80 virtual px, 160 video px at 60 Hz), 8 s
        settings = plain_settings("--scene", "follow")
        self.assertEqual((jobs[0].speed.scroll, settings.frame_count(jobs[0].speed)), (4800, CLIP_FRAMES))
        # --follow-boxes makes one video with that stack; --slow-motion picks the factors
        custom = self.settings("--follow-boxes", "30", "30-naive-heavy", "30-naive-synthetic", "--slow-motion", "1")
        self.assertEqual([(name, [box.name for box in stack]) for name, stack in custom.follow_stacks], [("", ["30", "30-naive-heavy", "30-naive-synthetic"])])
        self.assertEqual(len(gv.plan_videos(custom)), 1)

    def test_one_rate_per_video_and_the_stack_must_fit(self) -> None:
        # One rate per video, like a game: its camera is updated at that rate
        with self.assertRaisesRegex(ValueError, "all boxes need the same rate \\(got 60, 30 Hz\\)"):
            gv.validate(gv.settings_from_arguments(gv.build_parser().parse_args(["--scene", "follow", "--follow-boxes", "60", "30"], namespace=gv.Arguments())))
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            _ = gv.parse_arguments(["--scene", "follow", "--follow-boxes", "60-wobbly"])
        with self.assertRaisesRegex(ValueError, "8 boxes of 48 do not fit above each other in the height 360"):
            gv.validate(
                gv.settings_from_arguments(gv.build_parser().parse_args(["--scene", "follow", "--follow-boxes", *["60"] * 8], namespace=gv.Arguments()))
            )

    def test_only_the_timing_error_moves_a_box(self) -> None:
        settings = self.settings()
        loads, realistic, extreme = gv.plan_videos(settings)[:3]
        per_ms = float(loads.speed.scroll or 0) / 1000  # 9.6 px per ms of timing error
        for job in (loads, realistic):
            positions = [gv.follow_positions(settings, job, frame) for frame in range(CLIP_FRAMES)]
            # The camera follows the perfect motion: the 60 Hz reference never moves
            self.assertEqual({values[0] for values in positions}, {0.0})
            # Each load moves its box both ways; heavy load's spikes (up to 8 ms late) the furthest
            for index in (1, 2, 3):
                errors = [values[index] for values in positions]
                self.assertTrue(min(errors) < -per_ms / 2 and max(errors) > per_ms / 2, (job.filename, index))
            self.assertGreater(max(values[3] for values in positions), 4 * per_ms)
        # The demo profile: off by more than half a millisecond in most frames
        positions = [gv.follow_positions(settings, loads, frame) for frame in range(CLIP_FRAMES)]
        for index in (1, 2, 3):
            self.assertGreater(sum(abs(values[index]) > per_ms / 2 for values in positions), CLIP_FRAMES * 3 // 4, index)
        # The windows: up to +-1 ... +-4 ms, the same pattern scaled
        positions = [gv.follow_positions(settings, extreme, frame) for frame in range(CLIP_FRAMES)]
        for index, window in ((1, 1), (2, 2), (3, 3), (4, 4)):
            errors = [values[index] for values in positions]
            self.assertAlmostEqual(max(errors) - min(errors), 2 * window * per_ms, delta=0.01)
        # A 30 Hz stack: the camera is updated at 30 Hz too, so the ideal box stays on the lines
        settings_30 = self.settings("--follow-boxes", "30", "30-naive-typical")
        [job_30] = [job for job in gv.plan_videos(settings_30) if job.slow_motion == 1]
        positions_30 = [gv.follow_positions(settings_30, job_30, frame) for frame in range(CLIP_FRAMES)]
        self.assertEqual({values[0] for values in positions_30}, {0.0})
        self.assertTrue(any(values[1] for values in positions_30))

    def test_every_video_loops_seamlessly(self) -> None:
        settings = self.settings("--slow-motion", "1")
        for job in gv.plan_videos(settings):
            first = [gv.follow_positions(settings, job, frame) for frame in range(CLIP_FRAMES)]
            second = [gv.follow_positions(settings, job, frame) for frame in range(CLIP_FRAMES, 2 * CLIP_FRAMES)]
            for a, b in zip(first, second, strict=True):
                self.assertEqual([round(value, 6) for value in a], [round(value, 6) for value in b], job.filename)

    def test_boxes_in_front_of_the_lines_and_labels_clear_of_them(self) -> None:
        settings = self.settings("--labels", "--no-divider")
        job = gv.plan_videos(settings)[2]
        renderer = gv.FollowRenderer(settings, job)
        # Box 96 at 592-687, lines of 2 video pixels just outside it, the 5 boxes (gap 24) centred: tops at 72, 192, ...
        image = renderer.draw(tuple(0.0 for _ in job.boxes))
        self.assertEqual(image.size, (1280, 720))
        self.assertEqual([image.getpixel((x, 5)) for x in (590, 591, 688, 689)], [settings.line_color] * 4)
        self.assertEqual([image.getpixel((x, 72 + 48)) for x in (589, 592, 687, 690)], [settings.background, *[settings.box_color] * 2, settings.background])
        # A box over a line hides it: the lines are behind the boxes
        image = renderer.draw(tuple(10.0 for _ in job.boxes))
        self.assertEqual(image.getpixel((688, 72 + 48)), settings.box_color)
        self.assertEqual(image.getpixel((688, 5)), settings.line_color)
        # The labels start right of the furthest any box swings (the 4 ms box: about 38 px)
        swing = max(offset for frame in range(CLIP_FRAMES) for offset in gv.follow_positions(settings, job, frame))
        text = [x for x in range(640, 1280) for y in range(60, 180) if image.getpixel((x, y)) == settings.label_color]
        self.assertGreater(min(text), 690 + swing)

    def test_slow_motion_repeats_every_refresh(self) -> None:
        settings = plain_settings("--scene", "follow", "--slow-motion", "3", "--follow-boxes", "60-naive-typical", "--seconds", "2")
        [job] = gv.plan_videos(settings)
        self.assertEqual(job.filename, "follow_eighth-width-per-frame_slow3.mp4")
        frames = list(gv.clip_frames(settings, job))
        self.assertEqual(len(frames), 3 * 120)
        self.assertEqual(settings.video_frame_count(job), 360)
        self.assertTrue(all(frames[index] == frames[index - index % 3] for index in range(len(frames))))

    def test_manifest_lists_the_stack(self) -> None:
        settings = self.settings("--slow-motion", "1")
        video = cast(list[dict[str, object]], gv.build_manifest(settings, gv.plan_videos(settings))["videos"])[2]
        boxes = cast(list[dict[str, object]], video["boxes"])
        self.assertEqual([box["mode"] for box in boxes], ["60", "60-naive-1ms", "60-naive-2ms", "60-naive-3ms", "60-naive-4ms"])
        self.assertEqual((boxes[1]["label"], boxes[1]["noiseWindowMs"]), ("60 Hz naive timer, ±1 ms mixed", 1))
        self.assertEqual(set(cast(dict[str, list[float]], boxes[0]["frames"])["animationErrorMs"]), {0})
        errors = cast(dict[str, list[float]], boxes[4]["frames"])["animationErrorMs"]
        self.assertEqual(max(map(abs, errors)), 8)
        self.assertNotIn("top", video)


class SingleAndMarkerTests(unittest.TestCase):
    """--single (one box per video) and --marker (mb-framepacing's frame marker), at the default 1280 x 720, where the start marker
    fits left of the box's path."""

    def marked(self, *modes: str) -> tuple[gv.Settings, list[gv.VideoJob]]:
        settings = plain_settings("--single", *modes, "--marker", "--speed", "fast")
        return settings, gv.plan_videos(settings)

    def test_single_makes_one_video_per_mode_in_its_own_folder(self) -> None:
        settings, jobs = self.marked("60", "30")
        self.assertEqual([job.filename for job in jobs], ["single_fast_60.mp4", "single_fast_30.mp4"])
        self.assertEqual({job.group.as_posix() for job in jobs}, {"box-single-marker/fast"})
        plain = gv.plan_videos(plain_settings("--single", "60", "--speed", "fast"))
        self.assertEqual(plain[0].group.as_posix(), "box-single/fast")
        # The box alone, halfway down the frame (at rest at the left end of its path, from x = 208), and no divider
        image = gv.renderer_for(settings, jobs[0]).draw((0.0, 0.0))
        self.assertEqual(image.getpixel((250, settings.single_row)), settings.box_color)
        self.assertEqual(image.getpixel((250, settings.single_row - 1)), settings.background)
        self.assertEqual(settings.single_row, (720 - settings.band_height) // 2)
        self.assertEqual(image.getpixel((640, settings.divider_rows[0])), settings.background)

    def test_the_payload_follows_the_frame_on_screen(self) -> None:
        settings, jobs = self.marked("30")
        job = jobs[0]
        frames = settings.frame_count(job.speed)
        payloads = [gv.marker_payload(settings, job, frame) for frame in gv.video_refreshes(settings, job)]
        self.assertEqual(len(payloads), frames + 2 * gv.MARKER_LEAD_REFRESHES)
        kinds = [payload.kind for payload in payloads]
        lead = gv.MARKER_LEAD_REFRESHES
        self.assertEqual(set(kinds[:lead]), {MarkerKind.SEQUENCE_START})
        self.assertEqual(set(kinds[lead:-lead]), {MarkerKind.FRAME})
        self.assertEqual(set(kinds[-lead:]), {MarkerKind.SEQUENCE_END})
        # 30 Hz: every frame index on two refreshes in a row, counting on through the lead-in and lead-out
        indices = [payload.frame_index for payload in payloads]
        self.assertEqual([b - a for a, b in itertools.pairwise(dict.fromkeys(indices))], [1] * (len(set(indices)) - 1))
        self.assertEqual(payloads[lead].frame_index, frames // 2)
        self.assertEqual(indices[lead : lead + 4], [240, 240, 241, 241])
        # The animation time of the frame on screen, in ticks
        self.assertEqual(payloads[lead + 3].animation_ticks, round(gv.content_time(settings, job.top, job.speed, 3) * 10_000_000))
        self.assertEqual({payload.run_id for payload in payloads}, {gv.MARKER_RUN_ID})
        # The manifest's animation time of each frame is the marker's, in ms
        animation_ms = cast(dict[str, list[float]], gv._mode_entry(settings, job.top, job.speed)["frames"])["animationMs"]  # pyright: ignore[reportPrivateUsage]
        clip = [payload for payload in payloads if payload.kind == MarkerKind.FRAME]
        by_index = {payload.frame_index - frames // 2: payload.animation_ticks for payload in clip}
        self.assertEqual([round(ms * 10_000) for ms in animation_ms], [by_index[k] for k in range(len(animation_ms))])
        # The pacer's plan: 30 fps, each frame meant for its own refresh (every second one), counted from the clip's first refresh
        self.assertEqual({payload.target_frame_ticks for payload in payloads}, {333_333})
        self.assertEqual([payload.intended_display_ticks for payload in payloads[lead : lead + 3]], [0, 0, 333_333])
        # The lead-in shows the previous loop's last frame, meant for 2 refreshes before the clip's first
        self.assertEqual(payloads[lead - 1].intended_display_ticks, -333_333)

    def test_the_marker_is_drawn_into_every_frame(self) -> None:
        settings, jobs = self.marked("60-naive-5ms")
        job = jobs[0]
        video = list(gv.clip_frames(settings, job))
        self.assertEqual(len(video), settings.video_frame_count(job))
        x, y = settings.marker_origin
        for frame in (-gv.MARKER_LEAD_REFRESHES, 0, 1, settings.frame_count(job.speed)):
            with self.subTest(frame=frame):
                image = Image.frombytes("RGB", (settings.width, settings.height), video[frame + gv.MARKER_LEAD_REFRESHES])
                # The quiet zone's corner is white, and the frame's pixels are the plain frame plus the marker's quads
                self.assertEqual(image.getpixel((x, y)), (255, 255, 255))
                plain = gv.renderer_for(settings, job).draw(gv.renderer_for(settings, job).positions(frame)).tobytes()
                self.assertEqual(video[frame + gv.MARKER_LEAD_REFRESHES], gv.draw_marker(settings, job, frame, plain))
        # Every frame shows another frame of the naive timer, so no two neighbouring video frames are the same
        self.assertTrue(all(a != b for a, b in itertools.pairwise(video[gv.MARKER_LEAD_REFRESHES : -gv.MARKER_LEAD_REFRESHES])))

    def test_the_manifest_has_the_rate_the_game_aims_for(self) -> None:
        settings = plain_settings("--single", "60", "--speed", "fast")
        speed = settings.speeds[0]
        for name, expected in (("60", {60}), ("30", {30}), ("60-naive-5ms", {60}), ("60-diagram-half-rate-bad-pacing", {30}), ("60-busy-adaptive", {30, 60})):
            with self.subTest(name):
                entry = gv._mode_entry(settings, MODE(name), speed)  # pyright: ignore[reportPrivateUsage]
                self.assertEqual(set(cast(dict[str, list[int]], entry["frames"])["targetFps"]), expected)
                self.assertEqual(entry["targetFps"], max(expected))
        self.assertIn("CC BY-NC-SA 4.0", cast(str, gv.build_manifest(settings, gv.plan_videos(settings))["license"]))

    def test_the_sequence_id_is_a_short_name_or_a_uuid_made_from_the_mode(self) -> None:
        # A name of at most 16 characters is the text tag itself, padded with zeros
        short = gv.marker_sequence_id(MODE("60-naive-5ms"))
        self.assertEqual((short, str(short)), (SequenceId(b"60-naive-5ms\0\0\0\0"), "60-naive-5ms"))
        # 16 characters fill it
        full = gv.marker_sequence_id(MODE("60-busy-adaptive"))
        self.assertEqual((full, str(full)), (SequenceId(b"60-busy-adaptive"), "60-busy-adaptive"))
        # A test clip with a longer name has a short name of its own
        storm = "60-naive-5ms-diagram-slow-frames-every-1s"
        tagged = gv.marker_sequence_id(MODE(storm))
        self.assertEqual((tagged, str(tagged)), (SequenceId(b"perfect-storm\0\0\0"), "perfect-storm"))
        # Any other longer one is a version 5 UUID from the repository's URL and the name, shown as the UUID
        name = "60-naive-heavy-realistic"
        expected = uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/Unarmed1000/mb-framepacing-explained/" + name)
        long = gv.marker_sequence_id(MODE(name))
        self.assertEqual((long, str(long)), (SequenceId(expected.bytes), str(expected)))
        # The start marker carries it, with no start time; the manifest shows it as mb-framepacing does, and its bytes in hex
        for mode, sequence_id in (("60-naive-5ms", short), ("60-busy-adaptive", full), (storm, tagged), (name, long)):
            settings, jobs = self.marked(mode)
            job = jobs[0]
            payload = gv.marker_payload(settings, job, -1)
            self.assertEqual(payload.kind, MarkerKind.SEQUENCE_START)
            blank = bytes(3 * settings.width * settings.height)
            expected_matrix = generate_modules(payload, StartMetadata(0, sequence_id))
            expected_image = bytearray(blank)
            modules_to_bitmap(
                expected_matrix,
                MarkerOptions(settings.marker_module_px),
                Point(*settings.marker_origin),
                expected_image,
                settings.width,
                settings.height,
                PixelFormat.R8G8B8,
            )
            self.assertEqual(gv.draw_marker(settings, job, -1, blank), bytes(expected_image))
            video = cast(list[dict[str, object]], gv.build_manifest(settings, jobs)["videos"])[0]
            self.assertEqual((video["sequenceId"], video["sequenceIdHex"]), (str(sequence_id), sequence_id.data.hex()))
            self.assertRegex(cast(str, video["sequenceIdHex"]), "^[0-9a-f]{32}$")

    def test_the_markers_carry_the_manifests_cpu_start_and_busy_times(self) -> None:
        modes = ("60", "30", "60-naive-5ms", "60-busy-full-rate", "60-busy-adaptive", "60-diagram-half-rate-bad-pacing", "60-diagram-slow-frames-every-1s")
        for mode in modes:
            with self.subTest(mode):
                settings, jobs = self.marked(mode)
                job = jobs[0]
                count = settings.frame_count(job.speed)
                first = len(gv.simulated_frames(settings, job.top, job.speed).flips)
                entry = cast(dict[str, list[int]], gv._mode_entry(settings, job.top, job.speed)["frames"])  # pyright: ignore[reportPrivateUsage]
                starts, cpu = entry["cpuStartTicks"], entry["cpuBusyTicks"]
                # Loop 0: every frame of the clip, by its marker frame index (a held frame keeps its values)
                payloads = {payload.frame_index - first: payload for payload in (gv.marker_payload(settings, job, frame) for frame in range(count))}
                self.assertEqual(sorted(payloads), list(range(len(starts))))
                self.assertEqual([payloads[index].cpu_start_ticks for index in range(len(starts))], starts)
                self.assertEqual([payloads[index].cpu_busy_ticks for index in range(len(starts))], cpu)
                # Starts only move forward
                self.assertTrue(all(a < b for a, b in itertools.pairwise(starts)))
                clip_ticks = count * 10_000_000 // 60
                # The lead-in shows the previous loop's last frame, one clip earlier; the lead-out the next loop's first, one clip later
                before, after = gv.marker_payload(settings, job, -1), gv.marker_payload(settings, job, count)
                self.assertEqual((before.cpu_start_ticks, before.cpu_busy_ticks), (starts[-1] - clip_ticks, cpu[-1]))
                self.assertEqual((after.cpu_start_ticks, after.cpu_busy_ticks), (starts[0] + clip_ticks, cpu[0]))
                # A frame is done before the refresh it is flipped on
                flips = entry["refresh"]
                self.assertTrue(all(start + took <= flip * clip_ticks // count + 1 for start, took, flip in zip(starts, cpu, flips, strict=True)))
        # CPU busy is known in every frame except the on-time frames around a replayed diagram's own
        for mode in modes[:-1]:
            settings, jobs = self.marked(mode)
            entry = cast(dict[str, list[int]], gv._mode_entry(settings, jobs[0].top, jobs[0].speed)["frames"])  # pyright: ignore[reportPrivateUsage]
            self.assertTrue(all(took > 0 for took in entry["cpuBusyTicks"]), mode)
        settings, jobs = self.marked("60")
        self.assertEqual(set(cast(dict[str, list[int]], gv._mode_entry(settings, jobs[0].top, jobs[0].speed)["frames"])["cpuBusyTicks"]), {50_000})  # pyright: ignore[reportPrivateUsage]

    def fault_clip(self, fault: str) -> tuple[list[int], dict[str, object]]:
        """The marker frame index of every refresh of the storm with a presentation fault (from the clip's first frame), and its manifest entry."""
        settings, jobs = self.marked(f"60-naive-5ms-diagram-slow-frames-every-1s-{fault}")
        job = jobs[0]
        first = len(gv.simulated_frames(settings, job.top, job.speed).flips)
        indices = [gv.marker_payload(settings, job, frame).frame_index - first for frame in range(settings.frame_count(job.speed))]
        return indices, gv._mode_entry(settings, job.top, job.speed)  # pyright: ignore[reportPrivateUsage]

    def test_dropped_frames_skip_1_to_4_frame_indices_and_never_go_back(self) -> None:
        indices, entry = self.fault_clip("dropped-frames")
        steps = [b - a for a, b in itertools.pairwise(dict.fromkeys(indices))]
        self.assertTrue(all(step > 0 for step in steps))
        self.assertEqual(sorted(step - 1 for step in steps if step > 1), sorted([1, 2, 3, 4] * 4))
        self.assertEqual(indices, cast(list[int], entry["screen"]))
        frames = cast(dict[str, list[object]], entry["frames"])
        dropped = [index for index, refresh in enumerate(frames["refresh"]) if refresh is None]
        self.assertEqual(len(dropped), 40)
        self.assertEqual(sorted(set(range(len(frames["refresh"]))) - set(cast(list[int], entry["presented"]))), dropped)
        self.assertTrue(all(frames["animationErrorMs"][index] is None and frames["late"][index] is None for index in dropped))
        self.assertEqual(entry["expected"], {"skippedFrameIndices": 40, "outOfOrderRefreshes": 0})
        self.assertTrue(cast(str, entry["label"]).endswith(", dropped frames"))

    def test_frames_out_of_order_go_back_in_every_block(self) -> None:
        indices, entry = self.fault_clip("out-of-order")
        self.assertEqual(indices, cast(list[int], entry["screen"]))
        backs = sum(1 for a, b in itertools.pairwise(indices) if b < a)
        self.assertGreaterEqual(backs, 16)
        # mb-framepacing's rule: a frame below one already shown is out of order, not presented
        presented: list[int] = []
        highest, out_of_order = -1, 0
        for index in indices:
            if index > highest:
                presented.append(index)
                highest = index
            elif index < highest:
                out_of_order += 1
        self.assertEqual(entry["presented"], presented)
        skipped = sum(b - a - 1 for a, b in itertools.pairwise(presented))
        self.assertEqual(entry["expected"], {"skippedFrameIndices": skipped, "outOfOrderRefreshes": out_of_order})
        self.assertEqual((skipped, out_of_order), (25, 25))
        frames = cast(dict[str, list[int | None]], entry["frames"])
        # Every frame is shown, some before the frame rendered before them (early), and only the presented ones have an error
        self.assertNotIn(None, frames["refresh"])
        self.assertLess(min(late for late in frames["late"] if late is not None), 0)
        self.assertEqual([index for index, error in enumerate(frames["animationErrorMs"]) if error is not None], presented)

    def test_a_fault_changes_only_what_is_on_screen(self) -> None:
        storm = "60-naive-5ms-diagram-slow-frames-every-1s"
        settings, jobs = self.marked(storm, f"{storm}-dropped-frames", f"{storm}-out-of-order")
        entries = [gv._mode_entry(settings, job.top, job.speed) for job in jobs]  # pyright: ignore[reportPrivateUsage]
        plain = cast(dict[str, object], entries[0]["frames"])
        self.assertNotIn("screen", entries[0])
        for entry in entries[1:]:
            frames = cast(dict[str, object], entry["frames"])
            for key in ("animationMs", "dtMs", "sampleMs", "targetFps", "cpuStartTicks", "cpuBusyTicks"):
                self.assertEqual(frames[key], plain[key], key)
        # And the sequence id is the full name's
        self.assertEqual(len({str(gv.marker_sequence_id(job.top)) for job in jobs}), 3)

    def payloads(self, mode: str, speed: str = "fast") -> tuple[gv.Settings, gv.VideoJob, list[Payload]]:
        """The markers of every refresh of a marked clip, lead-in and lead-out included."""
        settings = plain_settings("--single", mode, "--marker", "--speed", speed)
        job = gv.plan_videos(settings)[0]
        return settings, job, [gv.marker_payload(settings, job, frame) for frame in gv.video_refreshes(settings, job)]

    def test_the_marker_carries_the_preferred_frame_time(self) -> None:
        # Swappy lowered to 30 fps still prefers 60; a 30 fps lock and bad half rate prefer 30; nothing is static
        for mode, preferred, targets in (
            ("60", {166_667}, {166_667}),
            ("30", {333_333}, {333_333}),
            ("60-diagram-half-rate-bad-pacing", {333_333}, {333_333}),
            ("60-busy-adaptive", {166_667}, {166_667, 333_333}),
        ):
            with self.subTest(mode):
                _, _, payloads = self.payloads(mode)
                self.assertEqual({payload.preferred_frame_ticks for payload in payloads}, preferred)
                self.assertEqual({payload.target_frame_ticks for payload in payloads}, targets)
                self.assertEqual({payload.flags for payload in payloads}, {MarkerFlags.NO_FLAGS})

    def test_static_rests_flag_exactly_the_frames_at_rest(self) -> None:
        settings, job, payloads = self.payloads("60-naive-5ms-static-rests")
        lead = gv.MARKER_LEAD_REFRESHES
        for frame, payload in zip(range(-lead, len(payloads) - lead), payloads, strict=True):
            at_rest = gv.at_rest(settings, job.speed, gv.content_time(settings, job.top, job.speed, frame))
            self.assertEqual(payload.flags, MarkerFlags.STATIC_AFTER if at_rest else MarkerFlags.NO_FLAGS, frame)
        entry = gv._mode_entry(settings, job.top, job.speed)  # pyright: ignore[reportPrivateUsage]
        frames = cast(dict[str, list[bool]], entry["frames"])
        # 8 rests of 6 refreshes; every frame rendered; flagged in advance only
        self.assertEqual((sum(frames["staticAfter"]), len(frames["staticAfter"])), (48, 480))
        self.assertEqual(set(frames["staticBefore"]), {False})

    def test_static_rests_with_a_paused_clock_flag_both_inside_a_rest(self) -> None:
        settings, job, payloads = self.payloads("60-static-rests-paused-clock")
        entry = gv._mode_entry(settings, job.top, job.speed)  # pyright: ignore[reportPrivateUsage]
        frames = cast(dict[str, list[object]], entry["frames"])
        after, before = cast(list[bool], frames["staticAfter"]), cast(list[bool], frames["staticBefore"])
        # 8 rests of 7 refreshes (the ideal timer): the frame that reaches the rest pose static after, the 6 after it both
        self.assertEqual((sum(after), sum(before)), (56, 48))
        self.assertTrue(all(not now or previous for now, previous in zip(before, after[-1:] + after[:-1], strict=True)))
        # The clock stands inside a rest
        animation = cast(list[float], frames["animationMs"])
        self.assertTrue(all(b == a for (a, b), now in zip(itertools.pairwise(animation), before[1:], strict=True) if now))
        flags = {payload.flags for payload in payloads}
        self.assertEqual(flags, {MarkerFlags.NO_FLAGS, MarkerFlags.STATIC_AFTER, MarkerFlags.STATIC_AFTER | MarkerFlags.STATIC_BEFORE})

    def test_hindsight_analyses_like_the_flag_in_advance(self) -> None:
        settings, job, hindsight = self.payloads("60-on-demand-paused-clock-hindsight")
        _, _, advance = self.payloads("60-on-demand-paused-clock")
        # The same markers but for the flags: static after on each rest's frame, or static before on the frame after it
        self.assertEqual(
            [replace(payload, flags=MarkerFlags.NO_FLAGS) for payload in hindsight], [replace(payload, flags=MarkerFlags.NO_FLAGS) for payload in advance]
        )
        indices = {payload.frame_index for payload in hindsight}
        woken = {payload.frame_index for payload in hindsight if payload.flags == MarkerFlags.STATIC_BEFORE}
        resting = {payload.frame_index for payload in advance if payload.flags == MarkerFlags.STATIC_AFTER}
        self.assertEqual(woken, {index + 1 for index in resting} & indices)
        self.assertEqual({payload.flags for payload in hindsight}, {MarkerFlags.NO_FLAGS, MarkerFlags.STATIC_BEFORE})
        entry = gv._mode_entry(settings, job.top, job.speed)  # pyright: ignore[reportPrivateUsage]
        self.assertEqual(set(cast(dict[str, list[bool]], entry["frames"])["staticAfter"]), {False})

    def test_a_rest_frame_dropped_before_the_wake_up(self) -> None:
        settings, job, _ = self.payloads("60-on-demand-paused-clock-hindsight-dropped-before-wake")
        entry = gv._mode_entry(settings, job.top, job.speed)  # pyright: ignore[reportPrivateUsage]
        frames = cast(dict[str, list[object]], entry["frames"])
        fault = cast(dict[str, object], entry["fault"])
        (block,) = cast(list[dict[str, int]], fault["blocks"])
        dropped = block["first"]
        expected = cast(dict[str, object], entry["expected"])
        self.assertEqual((fault["kind"], block["count"]), ("dropped-before-wake", 1))
        self.assertEqual((expected["skippedFrameIndices"], expected["outOfOrderRefreshes"]), (1, 0))
        # By the flags alone, every other rest's step is static; this one is not
        self.assertEqual(expected["staticSteps"], [0, 1, 109, 163, 217, 271, 325, 379])
        self.assertNotIn(dropped + 1, cast(list[int], expected["staticSteps"]))
        # The rest's frame is never shown; the frame that wakes up after it still says static before, and its step is judged: the
        # paused clock's full rest (the drop adds a frame to the animation step and a refresh to the display step alike)
        self.assertIsNone(frames["refresh"][dropped])
        self.assertEqual(cast(list[bool], frames["staticBefore"])[dropped + 1], True)
        errors = cast(list[float | None], frames["animationErrorMs"])
        self.assertIsNone(errors[dropped])
        self.assertEqual(errors[dropped + 1], -100.0)

    def test_a_dropped_wake_up_frame_takes_its_static_before_flag_with_it(self) -> None:
        settings, job, payloads = self.payloads("60-on-demand-paused-clock-hindsight-dropped-wake")
        entry = gv._mode_entry(settings, job.top, job.speed)  # pyright: ignore[reportPrivateUsage]
        frames = cast(dict[str, list[object]], entry["frames"])
        fault = cast(dict[str, object], entry["fault"])
        (block,) = cast(list[dict[str, int]], fault["blocks"])
        dropped = block["first"]
        expected = cast(dict[str, object], entry["expected"])
        self.assertEqual((fault["kind"], block["count"]), ("dropped-wake", 1))
        self.assertEqual((expected["skippedFrameIndices"], expected["outOfOrderRefreshes"]), (1, 0))
        self.assertEqual(expected["staticSteps"], [0, 1, 109, 163, 217, 271, 325, 379])
        self.assertNotIn(dropped + 1, cast(list[int], expected["staticSteps"]))
        # The frame that wakes up carries the rest's static before flag and is never shown; the frames around it have no flag
        before = cast(list[bool], frames["staticBefore"])
        self.assertEqual((before[dropped - 1], before[dropped], before[dropped + 1]), (False, True, False))
        self.assertIsNone(frames["refresh"][dropped])
        # No marker shows the dropped frame, so its flag never reaches the screen: in the clip's own loop, one static before fewer
        # than the clip flagged in hindsight
        count = len(frames["refresh"])
        self.assertNotIn(count + dropped, {payload.frame_index for payload in payloads})
        _, _, whole = self.payloads("60-on-demand-paused-clock-hindsight")
        flagged = {payload.frame_index for payload in payloads if payload.flags == MarkerFlags.STATIC_BEFORE}
        self.assertEqual({payload.frame_index for payload in whole if payload.flags == MarkerFlags.STATIC_BEFORE} - flagged, {count + dropped})
        # The step across the rest is judged: the paused clock's full rest
        errors = cast(list[float | None], frames["animationErrorMs"])
        self.assertIsNone(errors[dropped])
        self.assertEqual(errors[dropped + 1], -100.0)

    def test_on_demand_renders_nothing_more_at_rest_and_has_no_frame_time(self) -> None:
        for mode in ("60-on-demand", "60-on-demand-paused-clock"):
            with self.subTest(mode):
                settings, job, payloads = self.payloads(mode)
                self.assertEqual({payload.target_frame_ticks for payload in payloads}, {ON_DEMAND_FRAME_TICKS})
                self.assertEqual({payload.preferred_frame_ticks for payload in payloads}, {ON_DEMAND_FRAME_TICKS})
                # Frame indices stay consecutive: the game renders fewer frames, none is lost
                indices = list(dict.fromkeys(payload.frame_index for payload in payloads))
                self.assertEqual([b - a for a, b in itertools.pairwise(indices)], [1] * (len(indices) - 1))
                entry = gv._mode_entry(settings, job.top, job.speed)  # pyright: ignore[reportPrivateUsage]
                frames = cast(dict[str, list[object]], entry["frames"])
                self.assertEqual((set(frames["targetFps"]), set(frames["preferredFps"]), entry["targetFps"]), ({None}, {None}, None))
                # Only the first frame of each rest is rendered (and static), held until the box moves again
                refreshes, static = cast(list[int], frames["refresh"]), cast(list[bool], frames["staticAfter"])
                self.assertEqual(set(frames["staticBefore"]), {False})
                self.assertTrue(all(not (a and b) for a, b in itertools.pairwise(static)))
                held = [b - a for a, b, still in zip(refreshes, refreshes[1:], static, strict=False) if still]
                self.assertTrue(held and all(hold > 1 for hold in held))
        # The same frames and pictures; the paused clock is behind in the markers only, by a frame less than each rest
        plain, paused = self.payloads("60-on-demand")[2], self.payloads("60-on-demand-paused-clock")[2]
        self.assertEqual([payload.frame_index for payload in plain], [payload.frame_index for payload in paused])
        settings, job, _ = self.payloads("60-on-demand-paused-clock")
        on_demand = gv.plan_videos(plain_settings("--single", "60-on-demand", "--marker", "--speed", "fast"))[0]
        self.assertEqual(
            [gv.content_time(settings, job.top, job.speed, frame) for frame in range(480)],
            [gv.content_time(settings, on_demand.top, on_demand.speed, frame) for frame in range(480)],
        )
        errors = cast(list[float], cast(dict[str, object], gv._mode_entry(settings, job.top, job.speed)["frames"])["animationErrorMs"])  # pyright: ignore[reportPrivateUsage]
        self.assertEqual(min(errors), -100.0)

    def fault_entry(self, mode: str) -> tuple[dict[str, list[object]], list[dict[str, int]], dict[str, object]]:
        """The frames, the fault's blocks and what a measurement should count of a clip with a fault."""
        settings, job, _ = self.payloads(mode)
        entry = gv._mode_entry(settings, job.top, job.speed)  # pyright: ignore[reportPrivateUsage]
        blocks = cast(list[dict[str, int]], cast(dict[str, object], entry["fault"])["blocks"])
        return cast(dict[str, list[object]], entry["frames"]), blocks, cast(dict[str, object], entry["expected"])

    def test_a_static_after_flag_is_lost_with_its_dropped_rest_frame(self) -> None:
        frames, (block,), expected = self.fault_entry("60-on-demand-paused-clock-dropped-before-wake")
        dropped = block["first"]
        # The rest's frame carries static after and is never shown; the frame before it holds the rest without a flag
        after = cast(list[bool], frames["staticAfter"])
        self.assertEqual((after[dropped - 1], after[dropped], after[dropped + 1]), (False, True, False))
        self.assertIsNone(frames["refresh"][dropped])
        self.assertEqual(set(frames["staticBefore"]), {False})
        # So the step to the frame that wakes up is not static by the flags, and is judged: the paused clock's full rest
        self.assertNotIn(dropped + 1, cast(list[int], expected["staticSteps"]))
        self.assertEqual(cast(list[float | None], frames["animationErrorMs"])[dropped + 1], -100.0)
        self.assertEqual(len(cast(list[int], expected["staticSteps"])), 8)

    def test_frames_dropped_in_the_motion_are_no_rests(self) -> None:
        frames, blocks, expected = self.fault_entry("60-on-demand-paused-clock-hindsight-dropped-frames")
        self.assertEqual((len(blocks), expected["skippedFrameIndices"]), (16, 40))
        errors, steps = cast(list[float | None], frames["animationErrorMs"]), cast(list[int], expected["staticSteps"])
        resting = cast(list[bool], frames["staticBefore"])
        for block in blocks:
            shown_next = block["first"] + block["count"]
            # The clock ran through the drop: the next frame shows the right moment, and nothing around it is flagged static
            self.assertEqual(errors[shown_next], 0.0, block)
            self.assertNotIn(shown_next, steps)
            self.assertFalse(any(resting[block["first"] - 1 : shown_next + 1]), block)
        # The rests are flagged as in the clip without drops
        self.assertEqual(len(steps), 9)

    def test_a_frame_dropped_after_a_stall_is_no_rest(self) -> None:
        frames, (block,), expected = self.fault_entry("60-on-demand-paused-clock-hindsight-dropped-after-stall")
        dropped = block["first"]
        refreshes = cast(list[int | None], frames["refresh"])
        self.assertIsNone(refreshes[dropped])
        # The frame before the stall is on screen 8 refreshes (its 7 and the dropped frame's), as long as with a dropped wake-up frame
        self.assertEqual(cast(int, refreshes[dropped + 1]) - cast(int, refreshes[dropped - 1]), 8)
        # But the clock ran on: the next frame shown is 8 frames further, with no animation error, and no flag anywhere near it
        animation = cast(list[float], frames["animationMs"])
        self.assertAlmostEqual(animation[dropped + 1] - animation[dropped - 1], 8 * 1000 / 60, places=3)
        self.assertEqual(cast(list[float | None], frames["animationErrorMs"])[dropped + 1], 0.0)
        self.assertFalse(any(cast(list[bool], frames["staticBefore"])[dropped - 1 : dropped + 2]))
        self.assertNotIn(dropped + 1, cast(list[int], expected["staticSteps"]))
        self.assertEqual((expected["skippedFrameIndices"], len(cast(list[int], expected["staticSteps"]))), (1, 9))
        # The stall needs a game that presents on demand
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            _ = gv.parse_arguments(["--single", "60-dropped-after-stall", "--marker", "--speed", "fast"])

    def test_idling_at_1_fps_prefers_what_it_runs_at(self) -> None:
        settings, job, payloads = self.payloads("60-idle-1fps", "idle")
        self.assertEqual({(payload.target_frame_ticks, payload.preferred_frame_ticks) for payload in payloads}, {(166_667, 166_667), (10_000_000, 10_000_000)})
        entry = gv._mode_entry(settings, job.top, job.speed)  # pyright: ignore[reportPrivateUsage]
        frames = cast(dict[str, list[object]], entry["frames"])
        idle_refreshes = [refresh for refresh, rate in zip(frames["refresh"], frames["targetFps"], strict=True) if rate == 1]
        self.assertEqual(idle_refreshes, [0, 60, 210, 270, 330, 450])
        self.assertEqual(frames["targetFps"], frames["preferredFps"])
        # The fast speed's rests are too short to idle a second
        with contextlib.redirect_stderr(io.StringIO()) as error, self.assertRaises(SystemExit):
            _ = gv.parse_arguments(["--single", "60-idle-1fps", "--marker", "--speed", "fast"])
        self.assertIn("never rests 1 s", error.getvalue())

    def test_a_busy_frame_starts_when_the_previous_one_is_shown(self) -> None:
        settings, jobs = self.marked("60-busy-adaptive")
        entry = cast(dict[str, list[int]], gv._mode_entry(settings, jobs[0].top, jobs[0].speed)["frames"])  # pyright: ignore[reportPrivateUsage]
        self.assertEqual(entry["cpuStartTicks"][1:], [round(Fraction(flip, 60) * 10_000_000) for flip in entry["refresh"][:-1]])

    def test_the_manifest_says_how_to_measure(self) -> None:
        settings, jobs = self.marked("60")
        manifest = gv.build_manifest(settings, jobs)
        marker = cast(dict[str, object], cast(dict[str, object], manifest["settings"])["marker"])
        self.assertEqual((marker["moduleSizePx"], marker["origin"], marker["runId"]), (3, [32, 32], 1))
        video = cast(list[dict[str, object]], manifest["videos"])[0]
        self.assertEqual(video["markerFirstFrameIndex"], 480)
        self.assertEqual(video["measure"], "mb-framepacing import single_fast_60.mp4 --analyze -o single_fast_60")
        self.assertIn("box", video)
        self.assertNotIn("top", video)

    def test_the_marker_needs_a_single_box_at_real_speed_with_room(self) -> None:
        def rejected(message: str, *argv: str) -> None:
            with self.assertRaises(ValueError) as caught:
                gv.validate(gv.settings_from_arguments(gv.build_parser().parse_args(list(argv), namespace=gv.Arguments())))
            self.assertIn(message, str(caught.exception))

        rejected("--marker needs --single", "--marker", "--speed", "fast")
        rejected("needs real speed", "--single", "60", "--marker", "--speed", "fast", "--slow-motion", "10")
        rejected("shows a row", "--single", "60", "--marker", "--speed", "ui-384")
        rejected("at least 3 for --web", "--single", "60", "--marker", "--speed", "fast", "--web", "--marker-module-px", "2")
        rejected("overlaps the box's path", "--single", "60", "--marker", "--speed", "fast", "--marker-module-px", "5")
        rejected("does not fit in the height", "--single", "60", "--marker", "--speed", "fast", "--height", "150", "--box-size", "10")
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            _ = gv.parse_arguments(["--single", "60", "--top", "30"])


class FfmpegLookupTests(unittest.TestCase):
    @property
    def folder(self) -> Path:
        """A temporary folder, one per test."""
        if self._folder is None:
            self._folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        return self._folder

    _folder: Path | None = None

    @property
    def missing_config(self) -> Path:
        return self.folder / "no-such-local.toml"

    def make_ffmpeg(self, folder: Path) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        _ = path.write_bytes(b"")
        return path

    def find(self, explicit: str | None = None, config: Path | None = None, environ: dict[str, str] | None = None) -> gv.ToolLocation:
        return gv.find_ffmpeg(explicit, config, environ=environ or {}, default_config=self.missing_config)

    def test_explicit_file_or_folder(self) -> None:
        ffmpeg = self.make_ffmpeg(self.folder / "a" / "bin")
        for given in (ffmpeg, ffmpeg.parent, self.folder / "a"):
            self.assertEqual(self.find(str(given)).path, ffmpeg.resolve())

    def test_order_explicit_environment_config_path(self) -> None:
        explicit = self.make_ffmpeg(self.folder / "explicit")
        environment = self.make_ffmpeg(self.folder / "environment")
        configured = self.make_ffmpeg(self.folder / "configured")
        config = self.folder / "local.toml"
        _ = config.write_text("[ffmpeg]\npath = 'configured'\n", encoding="utf-8")
        environ = {gv.FFMPEG_ENVIRONMENT_VARIABLE: str(environment)}
        with mock.patch("generate_videos.shutil.which", return_value=str(self.folder / "on-path" / "ffmpeg")):
            self.assertEqual(self.find(str(explicit), config, environ).source, "--ffmpeg")
            self.assertEqual(self.find(None, config, environ).source, gv.FFMPEG_ENVIRONMENT_VARIABLE)
            found = self.find(None, config)
            self.assertEqual((found.path, found.source), (configured.resolve(), str(config)))
            self.assertEqual(self.find().source, "PATH")

    def test_default_config_is_used(self) -> None:
        configured = self.make_ffmpeg(self.folder / "tools")
        config = self.folder / "local.toml"
        _ = config.write_text(f"[ffmpeg]\npath = '{configured.parent}'\n", encoding="utf-8")
        self.assertEqual(gv.find_ffmpeg(environ={}, default_config=config).path, configured.resolve())

    def test_config_without_path_falls_through_to_path(self) -> None:
        config = self.folder / "local.toml"
        _ = config.write_text("[ffmpeg]\n# path = 'C:\\ffmpeg'\n", encoding="utf-8")
        with mock.patch("generate_videos.shutil.which", return_value="ffmpeg-on-path"):
            self.assertEqual(self.find(None, config).source, "PATH")

    def test_set_but_wrong_is_an_error(self) -> None:
        with self.assertRaisesRegex(gv.FfmpegError, "--ffmpeg"):
            _ = self.find(str(self.folder / "nothing"))
        with self.assertRaisesRegex(gv.FfmpegError, gv.FFMPEG_ENVIRONMENT_VARIABLE):
            _ = self.find(environ={gv.FFMPEG_ENVIRONMENT_VARIABLE: str(self.folder / "nothing")})
        config = self.folder / "local.toml"
        _ = config.write_text("[ffmpeg]\npath = 'nothing'\n", encoding="utf-8")
        with self.assertRaisesRegex(gv.FfmpegError, "local.toml"):
            _ = self.find(None, config)
        with self.assertRaisesRegex(gv.FfmpegError, "--config"):
            _ = self.find(None, self.missing_config)

    def test_not_found(self) -> None:
        with mock.patch("generate_videos.shutil.which", return_value=None), self.assertRaisesRegex(gv.FfmpegError, "not found"):
            _ = self.find()

    def test_lossless_encoder_is_required(self) -> None:
        with_encoder = " V....D libx264              libx264 H.264\n V....D h264_nvenc           NVIDIA NVENC H.264 encoder\n"
        gv.require_lossless_encoder(with_encoder, Path("ffmpeg"))
        # libx264rgb alone is not enough: the videos are YUV
        without = " V....D libx264rgb           libx264 H.264 RGB\n V....D h264_nvenc           NVIDIA NVENC H.264 encoder\n"
        with self.assertRaisesRegex(gv.FfmpegError, "no lossy fallback"):
            gv.require_lossless_encoder(without, Path("ffmpeg"))


def _installed_ffmpeg() -> tuple[Path, Path] | None:
    try:
        ffmpeg = gv.find_ffmpeg().path
    except gv.FfmpegError:
        return None
    ffprobe = gv.find_ffprobe(ffmpeg)
    return (ffmpeg, ffprobe) if ffprobe else None


INSTALLED = _installed_ffmpeg()
# Convert back to RGB the way the video is tagged (BT.709, limited range)
DECODE_FILTER = "scale=in_color_matrix=bt709:in_range=tv:flags=accurate_rnd+full_chroma_int"


@unittest.skipIf(INSTALLED is None, "FFmpeg and ffprobe not found (see README.md)")
class EncodeTests(unittest.TestCase):
    def test_small_clip_is_lossless_h264(self) -> None:
        assert INSTALLED is not None
        ffmpeg, ffprobe = INSTALLED
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        argv = ["--output-dir", str(folder), "--ffmpeg", str(ffmpeg), "--top", "60", "--bottom", "20-naive-heavy", "--speed", "fast"]
        # On the default 2 x 2 grid: a 4 x 4 box (8 x 8 video pixels) on a 32 x 16 canvas
        argv += ["--seconds", "3/2", "--fast-round-trips", "1", "--width", "64", "--height", "32", "--box-size", "4", "--travel", "20", "--labels"]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(gv.main(argv), 0)

        # Labelled box scene at fast speed: box-labels/fast
        self.assertEqual([path.name for path in folder.iterdir()], ["box-labels"])
        group = folder / "box-labels" / "fast"
        video = group / "fast_top-60_bottom-20-naive-heavy.mp4"
        self.assertEqual(sorted(path.name for path in group.iterdir()), [video.name, gv.MANIFEST_NAME])
        manifest = cast(dict[str, list[dict[str, object]]], json.loads((group / gv.MANIFEST_NAME).read_text(encoding="utf-8")))
        self.assertEqual(manifest["videos"][0]["frameCount"], 90)

        probe = subprocess.run(
            [str(ffprobe), "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_streams", "-of", "json", str(video)],
            capture_output=True,
            text=True,
            check=True,
        )
        stream = cast(dict[str, list[dict[str, object]]], json.loads(probe.stdout))["streams"][0]
        self.assertEqual(stream["codec_name"], "h264")
        self.assertEqual(stream["profile"], "High 4:4:4 Predictive")
        self.assertEqual((stream["pix_fmt"], stream["color_space"], stream["color_range"]), ("yuv444p", "bt709", "tv"))
        self.assertEqual((stream["width"], stream["height"]), (64, 32))
        self.assertEqual(stream["r_frame_rate"], "60/1")
        self.assertEqual(stream["nb_read_frames"], "90")

        decoded = subprocess.run(
            [str(ffmpeg), "-v", "error", "-i", str(video), "-vf", DECODE_FILTER, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            capture_output=True,
            check=True,
        ).stdout
        settings = gv.parse_arguments(argv)[1]
        expected = b"".join(gv.clip_frames(settings, gv.plan_videos(settings)[0]))
        self.assertEqual(len(decoded), len(expected))
        # H.264 at -qp 0 is lossless; only the RGB <-> YUV conversion around it may move an in-between gray (anti-aliased text,
        # the divider's fade) by one step. The designed colours (background, boxes) come back exactly.
        exact = {settings.background, settings.box_color}
        for index in range(0, len(expected), 3):
            rendered = (expected[index], expected[index + 1], expected[index + 2])
            got = (decoded[index], decoded[index + 1], decoded[index + 2])
            if rendered in exact:
                self.assertEqual(got, rendered, f"pixel {index // 3}")
            else:
                self.assertLessEqual(max(abs(a - b) for a, b in zip(got, rendered, strict=True)), 1, f"pixel {index // 3}")


if __name__ == "__main__":
    _ = unittest.main()
