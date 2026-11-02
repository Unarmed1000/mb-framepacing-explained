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

# What is on screen, a letter per target frame time, as the request pictures it (written out here, not taken from the script)
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
EDGES = {"23-dropped-first-frame", "23-dropped-last-frame"}
EVERY_CLIP = {*PICTURES, *REFRESH_PICTURES, *EDGES, "08-every-other-dropped", "12-rest-first-frame-dropped", "12-rest-last-frame-dropped"}
SIXTY_ONLY = {"15-faster-than-display"}
THIRTY_ONLY = {*THIRTY_PICTURES, "18-uneven-cadence", "19-wrong-animation-rate"}


@final
class Clip:
    """A stress clip as its markers and manifest say it."""

    def __init__(self, rate: int) -> None:
        self.settings: gv.Settings
        self.job: gv.VideoJob
        self.settings, self.job = next(clip for clip in export.planned_stress() if clip[1].top.rate == rate)
        self.mode = self.job.top
        self.interval = 60 // rate
        self.script = stress.clip(rate, TimingParameters())
        self.frames = self.script.frames
        self.schedule = gv.frame_schedule(self.settings, self.mode, self.job.speed)
        self.late = gv.refreshes_late(self.settings, self.mode, self.job.speed)
        self.scenarios = {scenario.name: scenario for scenario in self.script.scenarios}

    def animation_refreshes(self, index: int) -> Fraction:
        return self.frames.animation[index] * self.settings.fps

    def indices(self, name: str) -> range:
        scenario = self.scenarios[name]
        return range(scenario.first, scenario.first + scenario.count)

    def spelled(self, name: str, letters_long: int, unit: int) -> str:
        """What is on screen from a scenario's first frame, a letter per `unit` refreshes."""
        first = self.scenarios[name].first
        start = self.schedule.shown[first]
        assert start is not None, name
        return " ".join(chr(ord("a") + self.schedule.screen[start + slot * unit] - first) for slot in range(letters_long))


CLIPS = {rate: Clip(rate) for rate in (60, 30)}


class ScenarioTests(unittest.TestCase):
    def test_each_clip_has_its_scenarios(self) -> None:
        self.assertEqual(set(CLIPS[60].scenarios), EVERY_CLIP | SIXTY_ONLY)
        self.assertEqual(set(CLIPS[30].scenarios), EVERY_CLIP | THIRTY_ONLY)

    def test_the_screen_is_the_requests_picture_at_both_paces(self) -> None:
        for clip in CLIPS.values():
            for name, picture in PICTURES.items():
                self.assertEqual(clip.spelled(name, len(picture.split()), clip.interval), picture, (clip.mode.name, name))
            for name, picture in REFRESH_PICTURES.items():
                self.assertEqual(clip.spelled(name, len(picture.split()), 1), picture, (clip.mode.name, name))
        for name, picture in THIRTY_PICTURES.items():
            self.assertEqual(CLIPS[30].spelled(name, len(picture.split()), 1), picture, name)

    def test_scenarios_have_at_least_twelve_frames_on_time_between_them(self) -> None:
        for clip in CLIPS.values():
            scenarios = sorted(clip.script.scenarios, key=lambda scenario: scenario.first)
            for before, after in zip(scenarios, scenarios[1:], strict=False):
                between = range(before.first + before.count, after.first)
                self.assertGreaterEqual(len(between), 12, (clip.mode.name, before.name, after.name))
                # The last letter of a scenario is on time: every step up to the next scenario is one target on screen and in animation time
                for index in (*between, after.first):
                    target = clip.frames.intervals[index]
                    self.assertEqual(clip.late[index], 0, (clip.mode.name, index))
                    self.assertEqual(cast(int, clip.schedule.shown[index]) - cast(int, clip.schedule.shown[index - 1]), target, (clip.mode.name, index))
                    self.assertEqual(clip.animation_refreshes(index) - clip.animation_refreshes(index - 1), target, (clip.mode.name, index))

    def test_a_dropped_frame_animated_for_its_display_time(self) -> None:
        for clip in CLIPS.values():
            first = clip.scenarios["01-dropped"].first
            self.assertIsNone(clip.schedule.shown[first + 1])
            self.assertEqual(clip.animation_refreshes(first + 2) - clip.animation_refreshes(first), 2 * clip.interval)

    def test_the_clock_lost_the_frame(self) -> None:
        for clip in CLIPS.values():
            a, b, c = clip.indices("03-dropped-clock-lost")
            self.assertIsNone(clip.schedule.shown[b])
            # Two targets apart on screen, one in animation time; b and c show the same moment, and c is the frame after b
            self.assertEqual(cast(int, clip.schedule.shown[c]) - cast(int, clip.schedule.shown[a]), 2 * clip.interval)
            self.assertEqual(clip.animation_refreshes(b) - clip.animation_refreshes(a), clip.interval)
            self.assertEqual(clip.frames.animation[c], clip.frames.animation[b])
            self.assertEqual(clip.frames.targets[c], clip.frames.targets[b] + clip.interval)
            self.assertIn(c, clip.schedule.presented)

    def test_a_late_frame_keeps_its_step_or_catches_up(self) -> None:
        for clip in CLIPS.values():
            for name, step in (("04-late-step-stays", 1), ("05-late-catches-up", 2)):
                a, b, c = clip.indices(name)
                self.assertEqual((clip.late[a], clip.late[b], clip.late[c]), (0, clip.interval, 0), name)
                self.assertEqual(clip.animation_refreshes(b) - clip.animation_refreshes(a), clip.interval, name)
                self.assertEqual(clip.animation_refreshes(c) - clip.animation_refreshes(b), step * clip.interval, name)

    def test_the_same_screen_on_the_plan_or_late_against_it(self) -> None:
        for clip in CLIPS.values():
            # a a a c: c rendered for its refresh and animated for it, or rendered for the one before and late
            moved, late = clip.indices("14-plan-moves")[2], clip.indices("07-dropped-then-refresh-lost")[2]
            self.assertEqual((clip.late[moved], clip.late[late]), (0, clip.interval))
            self.assertEqual(clip.animation_refreshes(moved) - clip.animation_refreshes(moved - 2), 3 * clip.interval)
            self.assertEqual(clip.animation_refreshes(late) - clip.animation_refreshes(late - 2), 2 * clip.interval)

    def test_every_other_frame_dropped(self) -> None:
        for clip in CLIPS.values():
            frames = clip.indices("08-every-other-dropped")
            self.assertEqual(len(frames), 31)
            self.assertEqual([clip.schedule.shown[index] is None for index in frames[:-1]], [False, True] * 15)

    def test_a_long_hitch_with_the_clock_running_and_stopped(self) -> None:
        for clip in CLIPS.values():
            for name, step in (("09-hitch-clock-running", 10), ("09-hitch-clock-stopped", 1)):
                a, b = clip.indices(name)
                self.assertEqual(cast(int, clip.schedule.shown[b]) - cast(int, clip.schedule.shown[a]), 10 * clip.interval, name)
                self.assertEqual(clip.animation_refreshes(b) - clip.animation_refreshes(a), step * clip.interval, name)
                # The frames in order, no index lost
                self.assertEqual(b, a + 1, name)

    def test_an_out_of_order_pair_next_to_a_drop(self) -> None:
        for clip in CLIPS.values():
            a, b, c, d, e, f = clip.indices("10-out-of-order-next-to-drop")
            self.assertLess(cast(int, clip.schedule.shown[c]), cast(int, clip.schedule.shown[b]))
            self.assertIsNone(clip.schedule.shown[d])
            self.assertTrue({a, c, e, f} <= set(clip.schedule.presented))
            self.assertFalse({b, d} & set(clip.schedule.presented))
            self.assertIn((b, 2, (1, 0)), [(event.first, event.count, event.order) for event in clip.script.events])

    def test_only_the_frame_after_a_failed_present_says_so(self) -> None:
        for clip in CLIPS.values():
            c = clip.indices("11-present-failed")[2]
            self.assertEqual(clip.script.present_failed, {c})
            shown = cast(int, clip.schedule.shown[c])
            self.assertTrue(gv.marker_payload(clip.settings, clip.job, shown).flags & MarkerFlags.PRESENT_FAILED_BEFORE)
            plain = clip.schedule.shown[clip.indices("11-dropped-by-target")[2]]
            self.assertFalse(gv.marker_payload(clip.settings, clip.job, cast(int, plain)).flags & MarkerFlags.PRESENT_FAILED_BEFORE)

    def test_a_rest_next_to_a_drop(self) -> None:
        for clip in CLIPS.values():
            flagged = {index for index, static in enumerate(clip.script.static_after) if static}
            first, last = clip.indices("12-rest-first-frame-dropped"), clip.indices("12-rest-last-frame-dropped")
            self.assertEqual(flagged, {*first[1:-1], *last[1:-1]})
            # The first frame at rest is dropped, or the last; the frame before and after the rest move
            self.assertIsNone(clip.schedule.shown[first[1]])
            self.assertIsNone(clip.schedule.shown[last[-2]])
            for index in (*first, *last):
                resting = gv.at_rest(clip.settings, clip.job.speed, clip.frames.animation[index])
                self.assertEqual(resting, index in flagged, (clip.mode.name, index))
                self.assertEqual(stress.at_rest(clip.animation_refreshes(index)), resting, (clip.mode.name, index))

    def test_the_pacing_changes_on_a_drop_both_ways(self) -> None:
        for clip in CLIPS.values():
            for name, before, after in (("13-pacing-60-to-30", 1, 2), ("13-pacing-30-to-60", 2, 1)):
                a, b, c = clip.indices(name)
                self.assertEqual(clip.frames.intervals[a], before, name)
                self.assertEqual((clip.frames.intervals[b], clip.frames.intervals[c]), (after, after), name)
                self.assertIsNone(clip.schedule.shown[b], name)

    def test_faster_than_the_display(self) -> None:
        clip = CLIPS[60]
        frames = clip.indices("15-faster-than-display")
        self.assertEqual({clip.frames.intervals[index] for index in frames[1:]}, {Fraction(1, 2)})
        shown = [index for index in frames if clip.schedule.shown[index] is not None]
        self.assertEqual(shown, list(range(frames[0], frames[-1] + 1, 2)))
        self.assertEqual(
            [clip.schedule.shown[index] for index in shown],
            list(range(cast(int, clip.schedule.shown[frames[0]]), cast(int, clip.schedule.shown[frames[-1]]) + 1)),
        )
        self.assertEqual(gv.marker_payload(clip.settings, clip.job, cast(int, clip.schedule.shown[shown[1]])).target_frame_ns, 8_333_333)

    def test_the_scenarios_of_the_30_hz_clip(self) -> None:
        clip = CLIPS[30]
        a, b, c = clip.indices("16-late-by-one")
        self.assertEqual((clip.late[a], clip.late[b], clip.late[c]), (0, 1, 0))
        self.assertEqual([clip.late[index] for index in clip.indices("17-early-then-back")], [0, -1, -1, 0])
        cadence = clip.indices("18-uneven-cadence")
        held = [cast(int, clip.schedule.shown[index + 1]) - cast(int, clip.schedule.shown[index]) for index in cadence[:-1]]
        self.assertEqual(held, [3, 1] * 12)
        wrong = clip.indices("19-wrong-animation-rate")
        for index in wrong[1:]:
            self.assertEqual(cast(int, clip.schedule.shown[index]) - cast(int, clip.schedule.shown[index - 1]), 2)
            self.assertEqual(clip.animation_refreshes(index) - clip.animation_refreshes(index - 1), 1)

    def test_the_run_edges(self) -> None:
        for clip in CLIPS.values():
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
            self.assertEqual(refreshes - cast(int, clip.schedule.shown[count - 1]), 2 * clip.interval)


class MarkerTests(unittest.TestCase):
    def test_every_marker_field_is_filled(self) -> None:
        for clip in CLIPS.values():
            refreshes = range(-gv.MARKER_LEAD_REFRESHES, len(clip.schedule.screen) + gv.MARKER_LEAD_REFRESHES)
            for refresh in refreshes:
                payload = gv.marker_payload(clip.settings, clip.job, refresh)
                self.assertGreater(payload.target_frame_ns, 0)
                self.assertGreater(payload.preferred_frame_ns, 0)
                self.assertEqual(payload.refresh_period_ns, 16_666_667)
                self.assertGreater(payload.cpu_busy_ns, 0)
                # As in every test clip, 0 is the first refresh on the clock these two share: only a frame that falls exactly there has it
                frame, loops = gv.frame_on_screen(clip.settings, clip.mode, clip.job.speed, refresh)
                self.assertEqual(payload.intended_display_ns == 0, (frame, loops) == (1, 0))
                self.assertEqual(payload.cpu_start_ns == 0, (frame, loops) == (2, 0))

    def test_a_shown_frames_cpu_times_say_why_it_came_when_it_did(self) -> None:
        for clip in CLIPS.values():
            for index, shown in enumerate(clip.schedule.shown):
                if shown is None:
                    continue
                done = (clip.frames.starts[index] + clip.frames.cpu[index]) * clip.settings.fps
                self.assertLess(done, shown, (clip.mode.name, index))
                late = cast(int, clip.late[index])
                if late > 0:
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
            self.assertEqual(set(scenarios[0]), {"name", "firstFrame", "frameCount"})
            expected = cast(dict[str, object], box["expected"])
            self.assertEqual(set(expected), {"skippedFrameIndices", "outOfOrderRefreshes", "staticSteps"})
            self.assertEqual(cast(list[bool], frames["presentFailedBefore"]).count(True), 1)
            self.assertEqual(box["targetFps"], clip.mode.rate)
            _ = json.dumps(manifest)

    def test_the_other_clips_keep_their_animation_error(self) -> None:
        settings, job = export.planned()[0]
        box = cast(dict[str, object], cast(list[dict[str, object]], export.clip_manifest(settings, job)["videos"])[0]["box"])
        self.assertIn("animationErrorMs", cast(dict[str, object], box["frames"]))
        self.assertNotIn("scenarios", box)


class ValidationTests(unittest.TestCase):
    def test_a_script_is_for_60_or_30_hz_on_a_60_hz_display(self) -> None:
        with self.assertRaisesRegex(ValueError, "60 or 30 Hz"):
            _ = stress.clip(20, TimingParameters())
        with self.assertRaisesRegex(ValueError, "60 Hz display"):
            _ = stress.clip(60, TimingParameters(fps=Fraction(120)))

    def test_a_script_takes_no_idle_behaviour_or_fault(self) -> None:
        with self.assertRaisesRegex(ValueError, "no idle behaviour or fault"):
            validate_timing(parse_mode("60-stress-dropped-frames"), TimingParameters())

    def test_a_clip_is_as_long_as_its_script(self) -> None:
        clip = CLIPS[60]
        with self.assertRaisesRegex(ValueError, "fills 600 refreshes, not 480"):
            _ = gv.simulated_frames(replace(clip.settings, seconds=Fraction(8)), clip.mode, clip.job.speed)


if __name__ == "__main__":
    _ = unittest.main()
