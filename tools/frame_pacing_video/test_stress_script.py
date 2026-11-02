# SPDX-FileCopyrightText: Copyright (C) 2026 Rene Thrane
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""Tests of stress_script.py: the scenarios as mb-framepacing asked for them, on screen and in their markers."""

import json
import unittest
from dataclasses import replace
from fractions import Fraction
from typing import cast, final

import export_test_clips as export
import generate_videos as gv
import stress_script as stress
from frame_timing import TimingParameters, parse_mode
from frame_timing import validate as validate_timing
from mb_framepacing.marker import MarkerFlags, MarkerKind

# What is on screen, a letter per target frame time, as the requests picture it (written out here, not taken from the script)
PICTURES = {
    "01-dropped": "a a c",
    "02-dropped-run-2": "a a a d",
    "02-dropped-run-3": "a a a a e",
    "02-dropped-run-4": "a a a a a f",
    "03-dropped-clock-lost": "a a c",
    "04-late-step-stays": "a a b c",
    "05-late-catches-up": "a a b c",
    "06-two-late": "a a b b c",
    "07-dropped-then-refresh-lost": "a a a c",
    "09-hitch-clock-running": "a a a a a a a a a a b",
    "09-hitch-clock-stopped": "a a a a a a a a a a b",
    "10-out-of-order-next-to-drop": "a c b e",
    "11-present-failed": "a a c",
    "11-dropped-by-target": "a a c",
    "14-plan-moves": "a a a c",
    "14-plan-keeps-grid": "a a c",
    "20-two-drops-close": "a a c d d f",
    "21-dropped-after-late": "a a b b d",
    "22-dropped-before-late": "a a c c d",
    "24-dropped-overshoots": "a a c",
    "25-animation-goes-backwards": "a b c d",
    "30-present-failed-in-run": "a a a a e",
    "36-swapped-pair": "a c b d",
    "36-block-of-3": "a d b c e",
    "36-block-of-4": "a c e b d f",
    "37-older-frame-again": "a b a c",
    "38-two-back-again": "a b c a d",
    "39-out-of-order-next-to-late": "a a b d c e",
}
# The same, a letter per refresh: the pacing changes on a 60 Hz display at either pace, and the scenarios of the 30 Hz clip alone
REFRESH_PICTURES = {
    "13-pacing-60-to-30": "a a a a c",
    "13-pacing-30-to-60": "a a c",
}
THIRTY_PICTURES = {
    "16-late-by-one": "a a a b c c",
    "17-early-then-back": "a b b c c",
}
# The ways back at a target of 2 that fit, a letter per refresh
THIRTY_RECOVERIES = {
    "31-realign-late-1": "a a a b b c c d",
    "31-realign-late-2": "a a a a b b c c d",
    "31-realign-late-3": "a a a a a b b c c d",
    "31-realign-dropped": "a a a c c d d e",
    "32-back-on-grid-late-1": "a a a b c c d",
    "32-back-on-grid-dropped": "a a a c d d e",
    "33-interval-1-late-1": "a a a b c c d",
    "33-interval-1-dropped": "a a a c d d e",
}
# The request's three at a target of 4, a letter per refresh, and what its rule makes of the others
FIFTEEN_RECOVERIES = {
    "31-realign-late-1": "a a a a a b b b b c c c c d",
    "31-realign-late-2": "a a a a a a b b b b c c c c d",
    "31-realign-late-3": "a a a a a a a b b b b c c c c d",
    "31-realign-dropped": "a a a a a c c c c d d d d e",
    "32-back-on-grid-late-1": "a a a a a b b b c c c c d",
    "32-back-on-grid-late-2": "a a a a a a b b c c c c d",
    "32-back-on-grid-late-3": "a a a a a a a b c c c c d",
    "32-back-on-grid-dropped": "a a a a a c c c d d d d e",
    "33-interval-1-late-1": "a a a a a b c c d",
    "33-interval-1-late-2": "a a a a a a b c d",
    "33-interval-1-late-3": "a a a a a a a b c c c c d",
    "33-interval-1-dropped": "a a a a a c d d e",
}
EDGES = {"23-dropped-first-frame", "23-dropped-last-frame"}
RESTS = {"12-rest-first-frame-dropped", "12-rest-last-frame-dropped", "40-out-of-order-in-rest"}
LONG = {"08-every-other-dropped", "25-animation-stands-still", "29-dropped-run-long", "29-hold-long"}
EVERY_SCRIPT = {*PICTURES, *EDGES, *RESTS, *LONG}
ON_DISPLAYS = (
    "01-dropped",
    "03-dropped-clock-lost",
    "04-late-step-stays",
    "05-late-catches-up",
    "07-dropped-then-refresh-lost",
    "10-out-of-order-next-to-drop",
)
ORDER_BLOCKS = {"36-swapped-pair", "36-block-of-3", "36-block-of-4"}
OUT_OF_ORDER = {*ORDER_BLOCKS, "37-older-frame-again", "38-two-back-again", "39-out-of-order-next-to-late", "40-out-of-order-in-rest"}
EDGE_ORDER = {"41-out-of-order-first-frames", "41-out-of-order-last-frames"}
TARGET_1 = {name + "-target-1" for name in FIFTEEN_RECOVERIES if name.startswith("33")}
THIRTY_ONLY = {"16-late-by-one", "17-early-then-back", "18-uneven-cadence", "19-wrong-animation-rate", "26-frames-every-refresh"}
CLOCK_VARIANTS = {"34-realign-clock-stays", "34-interval-1-clock-stays"}


@final
class Clip:
    """A stress clip as its markers and manifest say it."""

    def __init__(self, name: str) -> None:
        self.settings: gv.Settings
        self.job: gv.VideoJob
        self.settings, self.job = next(clip for clip in export.planned_stress() if clip[1].top.name == name)
        self.mode = self.job.top
        self.spec = stress.CLIPS[name]
        self.interval = self.spec.interval
        self.script = stress.clip(name, TimingParameters(fps=self.settings.fps))
        self.frames = self.script.frames
        self.schedule = gv.frame_schedule(self.settings, self.mode, self.job.speed)
        self.late = gv.refreshes_late(self.settings, self.mode, self.job.speed)
        self.scenarios = {scenario.name: scenario for scenario in self.script.scenarios}

    def animation_refreshes(self, index: int) -> Fraction:
        return self.frames.animation[index] * self.settings.fps

    def indices(self, name: str) -> range:
        scenario = self.scenarios[name]
        return range(scenario.first, scenario.first + scenario.count)

    def shown(self, index: int) -> int:
        return cast(int, self.schedule.shown[index])

    def step(self, index: int) -> int:
        """The display time step to a frame, from the frame before it, in refreshes."""
        return self.shown(index) - self.shown(index - 1)

    def spelled(self, name: str, letters_long: int, unit: int | Fraction) -> str:
        """What is on screen from a scenario's first frame, a letter per `unit` refreshes."""
        first = self.scenarios[name].first
        start = self.schedule.shown[first]
        assert start is not None, name
        return " ".join(chr(ord("a") + self.schedule.screen[int(start + slot * unit)] - first) for slot in range(letters_long))


CLIPS = {name: Clip(name) for name in stress.CLIPS}
PACED = (CLIPS["60-stress"], CLIPS["30-stress"], CLIPS["15-stress"])
DISPLAYS = (CLIPS["50-stress"], CLIPS["120-stress"], CLIPS["144-stress"])


class FirstRequestTests(unittest.TestCase):
    def test_each_clip_has_its_scenarios(self) -> None:
        self.assertEqual(set(CLIPS["60-stress"].scenarios), EVERY_SCRIPT | set(REFRESH_PICTURES) | {"15-faster-than-display"})
        thirty = EVERY_SCRIPT | set(REFRESH_PICTURES) | THIRTY_ONLY | set(THIRTY_RECOVERIES) | CLOCK_VARIANTS
        thirty |= {"33-interval-1-late-1-target-1", "33-interval-1-dropped-target-1"}
        self.assertEqual(set(CLIPS["30-stress"].scenarios), thirty)
        fifteen = EVERY_SCRIPT | THIRTY_ONLY | set(FIFTEEN_RECOVERIES) | TARGET_1 | CLOCK_VARIANTS | {"13-pacing-30-to-15", "13-pacing-15-to-30", "35-target-3"}
        self.assertEqual(set(CLIPS["15-stress"].scenarios), fifteen)

    def test_the_second_requests_scenarios_come_after_the_first_ones(self) -> None:
        for clip in PACED[:2]:
            names = [scenario.name for scenario in clip.script.scenarios]
            self.assertEqual(names[0], "23-dropped-first-frame")
            self.assertEqual(names[names.index("22-dropped-before-late") + 1], "24-dropped-overshoots")
            self.assertEqual(names[-1], "23-dropped-last-frame")

    def test_the_screen_is_the_requests_picture_at_every_pace(self) -> None:
        for clip in PACED:
            for name, picture in PICTURES.items():
                self.assertEqual(clip.spelled(name, len(picture.split()), clip.interval), picture, (clip.mode.name, name))
        for clip in PACED[:2]:
            for name, picture in REFRESH_PICTURES.items():
                self.assertEqual(clip.spelled(name, len(picture.split()), 1), picture, (clip.mode.name, name))
        for name, picture in THIRTY_PICTURES.items():
            self.assertEqual(CLIPS["30-stress"].spelled(name, len(picture.split()), 1), picture, name)
            self.assertEqual(CLIPS["15-stress"].spelled(name, len(picture.split()), 2), picture, name)

    def test_scenarios_have_a_gap_of_frames_on_time_between_them(self) -> None:
        for clip in CLIPS.values():
            scenarios = sorted(clip.script.scenarios, key=lambda scenario: scenario.first)
            for before, after in zip(scenarios, scenarios[1:], strict=False):
                between = range(before.first + before.count, after.first)
                self.assertGreaterEqual(len(between), clip.spec.gap, (clip.mode.name, before.name, after.name))
                # Every step up to the next scenario is one target on screen and in animation time
                for index in between:
                    target = clip.frames.intervals[index]
                    self.assertEqual(clip.late[index], 0, (clip.mode.name, index))
                    self.assertEqual(clip.step(index), target, (clip.mode.name, index))
                    self.assertEqual(clip.animation_refreshes(index) - clip.animation_refreshes(index - 1), target, (clip.mode.name, index))

    def test_a_dropped_frame_animated_for_its_display_time(self) -> None:
        for clip in PACED:
            first = clip.scenarios["01-dropped"].first
            self.assertIsNone(clip.schedule.shown[first + 1])
            self.assertEqual(clip.animation_refreshes(first + 2) - clip.animation_refreshes(first), 2 * clip.interval)

    def test_the_clock_lost_the_frame(self) -> None:
        for clip in (*PACED, *DISPLAYS):
            a, b, c = clip.indices("03-dropped-clock-lost")
            self.assertIsNone(clip.schedule.shown[b])
            # Two targets apart on screen, one in animation time; b and c show the same moment, and c is the frame after b
            self.assertEqual(clip.shown(c) - clip.shown(a), 2 * clip.interval)
            self.assertEqual(clip.animation_refreshes(b) - clip.animation_refreshes(a), clip.interval)
            self.assertEqual(clip.frames.animation[c], clip.frames.animation[b])
            self.assertEqual(clip.frames.targets[c], clip.frames.targets[b] + clip.interval)
            self.assertIn(c, clip.schedule.presented)

    def test_a_late_frame_keeps_its_step_or_catches_up(self) -> None:
        for clip in PACED:
            for name, step in (("04-late-step-stays", 1), ("05-late-catches-up", 2)):
                a, b, c = clip.indices(name)
                self.assertEqual((clip.late[a], clip.late[b], clip.late[c]), (0, clip.interval, 0), name)
                self.assertEqual(clip.animation_refreshes(b) - clip.animation_refreshes(a), clip.interval, name)
                self.assertEqual(clip.animation_refreshes(c) - clip.animation_refreshes(b), step * clip.interval, name)

    def test_the_same_screen_on_the_plan_or_late_against_it(self) -> None:
        for clip in PACED:
            # a a a c: c rendered for its refresh and animated for it, or rendered for the one before and late
            moved, late = clip.indices("14-plan-moves")[2], clip.indices("07-dropped-then-refresh-lost")[2]
            self.assertEqual((clip.late[moved], clip.late[late]), (0, clip.interval))
            self.assertEqual(clip.animation_refreshes(moved) - clip.animation_refreshes(moved - 2), 3 * clip.interval)
            self.assertEqual(clip.animation_refreshes(late) - clip.animation_refreshes(late - 2), 2 * clip.interval)

    def test_every_other_frame_dropped(self) -> None:
        for clip in PACED:
            frames = clip.indices("08-every-other-dropped")
            self.assertEqual(len(frames), 31)
            self.assertEqual([clip.schedule.shown[index] is None for index in frames[:-1]], [False, True] * 15)

    def test_a_long_hitch_with_the_clock_running_and_stopped(self) -> None:
        for clip in PACED:
            for name, step in (("09-hitch-clock-running", 10), ("09-hitch-clock-stopped", 1)):
                a, b = clip.indices(name)
                self.assertEqual(clip.shown(b) - clip.shown(a), 10 * clip.interval, name)
                self.assertEqual(clip.animation_refreshes(b) - clip.animation_refreshes(a), step * clip.interval, name)
                # The frames in order, no index lost
                self.assertEqual(b, a + 1, name)

    def test_an_out_of_order_pair_next_to_a_drop(self) -> None:
        for clip in (*PACED, *DISPLAYS):
            a, b, c, d, e, f = clip.indices("10-out-of-order-next-to-drop")
            self.assertLess(clip.shown(c), clip.shown(b))
            self.assertIsNone(clip.schedule.shown[d])
            self.assertTrue({a, c, e, f} <= set(clip.schedule.presented))
            self.assertFalse({b, d} & set(clip.schedule.presented))
            self.assertIn((b, 2, (1, 0)), [(event.first, event.count, event.order) for event in clip.script.events])

    def test_only_the_frame_after_a_failed_present_says_so(self) -> None:
        for clip in PACED:
            c, e = clip.indices("11-present-failed")[2], clip.indices("30-present-failed-in-run")[4]
            self.assertEqual(clip.script.present_failed, {c, e})
            self.assertTrue(gv.marker_payload(clip.settings, clip.job, clip.shown(c)).flags & MarkerFlags.PRESENT_FAILED_BEFORE)
            plain = clip.indices("11-dropped-by-target")[2]
            self.assertFalse(gv.marker_payload(clip.settings, clip.job, clip.shown(plain)).flags & MarkerFlags.PRESENT_FAILED_BEFORE)

    def test_a_rest_next_to_a_drop(self) -> None:
        for clip in PACED:
            first, last = clip.indices("12-rest-first-frame-dropped"), clip.indices("12-rest-last-frame-dropped")
            flagged = {index for index, static in enumerate(clip.script.static_after) if static}
            swapped = clip.indices("40-out-of-order-in-rest")
            self.assertEqual(flagged, {*first[1:-1], *last[1:-1], *swapped[1:-1]})
            # The first frame at rest is dropped, or the last; the frame before and after the rest move
            self.assertIsNone(clip.schedule.shown[first[1]])
            self.assertIsNone(clip.schedule.shown[last[-2]])

    def test_the_flagged_rests_are_the_boxs_rests(self) -> None:
        for clip in CLIPS.values():
            for scenario in clip.script.scenarios:
                if "rest" not in scenario.name:
                    continue
                for index in clip.indices(scenario.name):
                    resting = gv.at_rest(clip.settings, clip.job.speed, clip.frames.animation[index])
                    self.assertEqual(resting, clip.script.static_after[index], (clip.mode.name, scenario.name, index))
                    self.assertEqual(stress.at_rest(clip.frames.animation[index], clip.spec.settle), resting, (clip.mode.name, index))

    def test_the_pacing_changes_on_a_drop_both_ways(self) -> None:
        cases = [(CLIPS[name], *change) for name in ("60-stress", "30-stress") for change in (("13-pacing-60-to-30", 1, 2), ("13-pacing-30-to-60", 2, 1))]
        cases += [(CLIPS["15-stress"], "13-pacing-30-to-15", 2, 4), (CLIPS["15-stress"], "13-pacing-15-to-30", 4, 2)]
        for clip, name, before, after in cases:
            a, b, c = clip.indices(name)
            self.assertEqual(clip.frames.intervals[a], before, name)
            self.assertEqual((clip.frames.intervals[b], clip.frames.intervals[c]), (after, after), name)
            self.assertIsNone(clip.schedule.shown[b], name)

    def test_faster_than_the_display(self) -> None:
        clip = CLIPS["60-stress"]
        frames = clip.indices("15-faster-than-display")
        self.assertEqual({clip.frames.intervals[index] for index in frames[1:]}, {Fraction(1, 2)})
        shown = [index for index in frames if clip.schedule.shown[index] is not None]
        self.assertEqual(shown, list(range(frames[0], frames[-1] + 1, 2)))
        self.assertEqual([clip.shown(index) for index in shown], list(range(clip.shown(frames[0]), clip.shown(frames[-1]) + 1)))
        self.assertEqual(gv.marker_payload(clip.settings, clip.job, clip.shown(shown[1])).target_frame_ns, 8_333_333)

    def test_the_scenarios_of_the_slower_clips(self) -> None:
        for clip in PACED[1:]:
            half = clip.interval / 2
            a, b, c = clip.indices("16-late-by-one")
            self.assertEqual((clip.late[a], clip.late[b], clip.late[c]), (0, half, 0))
            self.assertEqual([clip.late[index] for index in clip.indices("17-early-then-back")], [0, -half, -half, 0])
            cadence = clip.indices("18-uneven-cadence")
            self.assertEqual([clip.shown(index + 1) - clip.shown(index) for index in cadence[:-1]], [3 * half, half] * 12)
            for index in clip.indices("19-wrong-animation-rate")[1:]:
                self.assertEqual(clip.step(index), clip.interval)
                self.assertEqual(clip.animation_refreshes(index) - clip.animation_refreshes(index - 1), half)

    def test_the_run_edges(self) -> None:
        for clip in PACED:
            count = len(clip.frames.flips)
            refreshes = len(clip.schedule.screen)
            self.assertIsNone(clip.schedule.shown[0])
            self.assertEqual((clip.schedule.screen[0], clip.schedule.presented[0]), (1, 1))
            # The start marker's last frame, then the frame after the one lost
            before, after = gv.marker_payload(clip.settings, clip.job, -1), gv.marker_payload(clip.settings, clip.job, 0)
            self.assertEqual((before.kind, after.kind), (MarkerKind.SEQUENCE_START, MarkerKind.FRAME))
            self.assertEqual((before.frame_index, after.frame_index), (count - 1, count + 1))
            # The last frame fills the target of the frame lost, then the end marker
            last, end = gv.marker_payload(clip.settings, clip.job, refreshes - 1), gv.marker_payload(clip.settings, clip.job, refreshes)
            self.assertEqual((last.kind, end.kind), (MarkerKind.FRAME, MarkerKind.SEQUENCE_END))
            self.assertEqual((last.frame_index, end.frame_index), (2 * count - 1, 2 * count + 1))
            self.assertEqual(refreshes - clip.shown(count - 1), 2 * clip.interval)


class SecondRequestTests(unittest.TestCase):
    def test_a_dropped_frame_overshoots(self) -> None:
        for clip in PACED:
            a, _, c = clip.indices("24-dropped-overshoots")
            self.assertEqual(clip.shown(c) - clip.shown(a), 2 * clip.interval)
            self.assertEqual(clip.animation_refreshes(c) - clip.animation_refreshes(a), 3 * clip.interval)

    def test_animation_time_stands_still_and_goes_back_with_frames_on_time(self) -> None:
        for clip in PACED:
            still = clip.indices("25-animation-stands-still")
            self.assertEqual({clip.frames.animation[index] for index in still}, {clip.frames.animation[still[0]]})
            a, b, c, d = clip.indices("25-animation-goes-backwards")
            self.assertEqual(clip.frames.animation[c], clip.frames.animation[a])
            self.assertLess(clip.frames.animation[c], clip.frames.animation[b])
            self.assertEqual(clip.animation_refreshes(d) - clip.animation_refreshes(b), 2 * clip.interval)
            for index in (*still, a, b, c, d):
                self.assertEqual(clip.late[index], 0)

    def test_frames_arrive_every_refresh_with_the_target_staying(self) -> None:
        clip = CLIPS["30-stress"]
        for index in clip.indices("26-frames-every-refresh")[1:]:
            self.assertEqual((clip.step(index), clip.frames.intervals[index], clip.late[index]), (1, 2, 0))

    def test_a_long_run_of_drops_and_a_long_hold(self) -> None:
        for clip in PACED:
            run = clip.indices("29-dropped-run-long")
            self.assertGreater(sum(clip.schedule.shown[index] is None for index in run), 100)
            a, b = clip.indices("29-hold-long")
            self.assertGreater(clip.shown(b) - clip.shown(a), 100)
            self.assertGreater(clip.shown(b) - clip.shown(a), 10 * clip.interval)

    def test_the_ways_back_at_a_target_of_4_and_2(self) -> None:
        for clip, pictures in ((CLIPS["15-stress"], FIFTEEN_RECOVERIES), (CLIPS["30-stress"], THIRTY_RECOVERIES)):
            for name, picture in pictures.items():
                # The picture's last letter is on screen for one target: the frame after it is on time
                frames = clip.indices(name)
                start = clip.shown(frames[0])
                spelled = [chr(ord("a") + clip.schedule.screen[start + refresh] - frames[0]) for refresh in range(len(picture.split()))]
                self.assertEqual(" ".join(spelled), picture, (clip.mode.name, name))
                self.assertEqual(clip.shown(frames[-1] + 1) - clip.shown(frames[-1]), clip.interval, (clip.mode.name, name))

    def test_the_marker_says_interval_1_on_that_frame_alone(self) -> None:
        clip = CLIPS["15-stress"]
        for name in FIFTEEN_RECOVERIES:
            if name.startswith("33"):
                plain, target_1 = clip.indices(name), clip.indices(f"{name}-target-1")
                self.assertEqual({clip.frames.intervals[index] for index in plain}, {4}, name)
                targets = [clip.frames.intervals[index] for index in target_1]
                self.assertEqual(sorted(targets), [1, *([4] * (len(targets) - 1))], name)
                # The game still prefers its own rate
                self.assertEqual({clip.script.preferred[index] for index in target_1}, {4}, name)
                self.assertEqual([clip.schedule.shown[index] is None for index in plain], [clip.schedule.shown[index] is None for index in target_1], name)

    def test_the_clock_catches_up_unless_its_step_stays(self) -> None:
        clip = CLIPS["15-stress"]
        a, b, c, d = clip.indices("31-realign-late-1")
        self.assertEqual([clip.animation_refreshes(index) - clip.animation_refreshes(a) for index in (b, c, d)], [4, 9, 13])
        for name in ("34-realign-clock-stays", "34-interval-1-clock-stays"):
            a, b, c, d = clip.indices(name)
            self.assertEqual([clip.animation_refreshes(index) - clip.animation_refreshes(a) for index in (b, c, d)], [4, 8, 12], name)

    def test_a_stretch_at_a_target_of_3(self) -> None:
        clip = CLIPS["15-stress"]
        stretch = clip.indices("35-target-3")
        for index in stretch:
            self.assertEqual((clip.step(index), clip.frames.intervals[index]), (3, 3))
        self.assertEqual((clip.step(stretch[-1] + 1), clip.frames.intervals[stretch[-1] + 1]), (4, 4))

    def test_a_whole_capture_at_40_fps(self) -> None:
        clip = CLIPS["40-stress"]
        count = len(clip.frames.flips)
        self.assertEqual(clip.schedule.presented, tuple(range(count)))
        self.assertEqual(clip.schedule.shown[:4], (0, 1, 3, 4))
        self.assertEqual({clip.step(index) for index in range(1, count)}, {1, 2})
        for refresh in gv.video_refreshes(clip.settings, clip.job):
            self.assertEqual(gv.marker_payload(clip.settings, clip.job, refresh).target_frame_ns, 25_000_000)
        self.assertEqual(clip.animation_refreshes(2) - clip.animation_refreshes(0), 3)

    def test_stretches_at_periods_of_no_whole_refreshes(self) -> None:
        clip = CLIPS["60-stress-uneven"]
        names = [name for name in clip.scenarios if name.startswith("42")]
        self.assertEqual(len(names), 8)
        starts = [clip.scenarios[name].first for name in names]
        for name in names:
            milliseconds = 25 if "-25-" in name else 20
            for index in clip.indices(name):
                marker = gv.marker_payload(clip.settings, clip.job, clip.shown(index))
                self.assertEqual(marker.target_frame_ns, milliseconds * 1_000_000, name)
                self.assertEqual(marker.preferred_frame_ns, 16_666_667, name)
        self.assertTrue(all(clip.shown(after) - clip.shown(before) >= 50 for before, after in zip(starts, starts[1:], strict=False)))

    def test_out_of_order_in_every_clip_but_the_whole_capture(self) -> None:
        for clip in CLIPS.values():
            if clip.mode.name == "40-stress":
                self.assertFalse(clip.script.events)
            elif clip.mode.name.endswith("-edges"):
                self.assertEqual(set(clip.scenarios), EDGE_ORDER)
            else:
                self.assertTrue(set(clip.scenarios) >= OUT_OF_ORDER, clip.mode.name)

    def test_no_frame_of_a_block_keeps_its_place(self) -> None:
        for clip in PACED:
            for name, size in (("36-block-of-3", 3), ("36-block-of-4", 4)):
                first = clip.scenarios[name].first + 1
                event = next(event for event in clip.script.events if event.first == first)
                self.assertEqual(sorted(event.order), list(range(size)), name)
                self.assertTrue(all(offset != place for place, offset in enumerate(event.order)), name)

    def test_older_frames_shown_again(self) -> None:
        for clip in PACED:
            a, b, c = clip.indices("37-older-frame-again")
            start = clip.shown(a)
            self.assertEqual(clip.schedule.screen[int(start + 2 * clip.interval)], a)
            self.assertEqual(clip.shown(c), start + 3 * clip.interval)
            self.assertIn(b, clip.schedule.presented)
            a, _, _, d = clip.indices("38-two-back-again")
            self.assertEqual(clip.schedule.screen[int(clip.shown(a) + 3 * clip.interval)], a)
            self.assertEqual(clip.shown(d), clip.shown(a) + 4 * clip.interval)

    def test_out_of_order_at_the_edges(self) -> None:
        for clip in (*(CLIPS[name] for name in ("60-stress-edges", "30-stress-edges", "15-stress-edges", "60-stress-uneven")), *DISPLAYS):
            count = len(clip.frames.flips)
            refreshes = len(clip.schedule.screen)
            self.assertEqual((clip.schedule.screen[0], clip.schedule.presented[0]), (1, 1))
            self.assertEqual(clip.schedule.screen[int(clip.interval)], 0)
            self.assertEqual(clip.schedule.screen[-1], count - 2, clip.mode.name)
            self.assertEqual(clip.schedule.screen[refreshes - 1 - int(clip.interval)], count - 1, clip.mode.name)
            self.assertEqual(clip.schedule.presented[-1], count - 1)

    def test_the_other_displays(self) -> None:
        for clip, period in zip(DISPLAYS, (20_000_000, 8_333_333, 6_944_444), strict=True):
            self.assertEqual(gv.marker_payload(clip.settings, clip.job, 0).refresh_period_ns, period)
            for name in ON_DISPLAYS:
                self.assertEqual({clip.frames.intervals[index] for index in clip.indices(name)}, {1}, name)
                self.assertEqual({clip.frames.intervals[index] for index in clip.indices(f"{name}-target-2")}, {2}, name)
                picture = PICTURES[name]
                self.assertEqual(clip.spelled(name, len(picture.split()), 1), picture, name)
                self.assertEqual(clip.spelled(f"{name}-target-2", len(picture.split()), 2), picture, name)


class MarkerTests(unittest.TestCase):
    def test_every_marker_field_is_filled(self) -> None:
        for clip in CLIPS.values():
            period = round(Fraction(10**9) / clip.settings.fps)
            for refresh in gv.video_refreshes(clip.settings, clip.job):
                payload = gv.marker_payload(clip.settings, clip.job, refresh)
                self.assertGreater(payload.target_frame_ns, 0)
                self.assertGreater(payload.preferred_frame_ns, 0)
                self.assertEqual(payload.refresh_period_ns, period)
                self.assertGreater(payload.cpu_busy_ns, 0)

    def test_a_shown_frames_cpu_times_say_why_it_came_when_it_did(self) -> None:
        for clip in CLIPS.values():
            for index, shown in enumerate(clip.schedule.shown):
                if shown is None:
                    continue
                done = (clip.frames.starts[index] + clip.frames.cpu[index]) * clip.settings.fps
                self.assertLess(done, shown, (clip.mode.name, index))
                if cast(Fraction, clip.late[index]) >= 1:
                    self.assertGreater(done, clip.frames.targets[index], (clip.mode.name, index))


class ManifestTests(unittest.TestCase):
    def test_the_manifest_says_what_was_rendered_and_on_screen(self) -> None:
        for clip in CLIPS.values():
            manifest = export.clip_manifest(clip.settings, clip.job)
            box = cast(dict[str, object], cast(list[dict[str, object]], manifest["videos"])[0]["box"])
            frames = cast(dict[str, object], box["frames"])
            self.assertNotIn("animationErrorMs", frames)
            self.assertEqual(box["screen"], list(clip.schedule.screen))
            self.assertEqual(box["presented"], list(clip.schedule.presented))
            self.assertEqual(cast(dict[str, object], box["fault"])["kind"], "scripted")
            scenarios = cast(list[dict[str, object]], box["scenarios"])
            self.assertEqual({entry["name"] for entry in scenarios}, set(clip.scenarios))
            self.assertEqual(len(scenarios), len(clip.scenarios), "scenario names are unique")
            self.assertEqual(set(scenarios[0]), {"name", "firstFrame", "frameCount"})
            expected = cast(dict[str, object], box["expected"])
            self.assertEqual(set(expected), {"skippedFrameIndices", "outOfOrderRefreshes", "staticSteps"})
            self.assertEqual(box["targetFps"], clip.mode.rate)
            _ = json.dumps(manifest)

    def test_a_frame_between_two_refreshes_is_a_part_of_a_refresh_late(self) -> None:
        clip = CLIPS["40-stress"]
        box = cast(dict[str, object], cast(list[dict[str, object]], export.clip_manifest(clip.settings, clip.job)["videos"])[0]["box"])
        self.assertEqual(cast(dict[str, list[float]], box["frames"])["late"][:4], [0.5, 0, 0.5, 0])

    def test_the_other_clips_keep_their_animation_error(self) -> None:
        settings, job = export.planned()[0]
        box = cast(dict[str, object], cast(list[dict[str, object]], export.clip_manifest(settings, job)["videos"])[0]["box"])
        self.assertIn("animationErrorMs", cast(dict[str, object], box["frames"]))
        self.assertNotIn("scenarios", box)


class ValidationTests(unittest.TestCase):
    def test_a_script_is_for_its_clip_and_display(self) -> None:
        with self.assertRaisesRegex(ValueError, "no stress clip named '20-stress'"):
            _ = stress.clip("20-stress", TimingParameters())
        with self.assertRaisesRegex(ValueError, "60 Hz display"):
            _ = stress.clip("60-stress", TimingParameters(fps=Fraction(120)))

    def test_a_script_takes_no_idle_behaviour_or_fault(self) -> None:
        with self.assertRaisesRegex(ValueError, "no idle behaviour or fault"):
            validate_timing(parse_mode("60-stress-dropped-frames"), TimingParameters())

    def test_a_clip_is_as_long_as_its_script(self) -> None:
        clip = CLIPS["60-stress"]
        with self.assertRaisesRegex(ValueError, "not 480"):
            _ = gv.simulated_frames(replace(clip.settings, seconds=Fraction(8)), clip.mode, clip.job.speed)


if __name__ == "__main__":
    _ = unittest.main()
