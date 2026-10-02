# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""Tests of check_marker_run.py: comparing mb-framepacing's measurement of a marked clip with the generator's manifest."""

import json
import tempfile
import unittest
from pathlib import Path

import check_marker_run as check


class CompareTests(unittest.TestCase):
    def test_equal_errors_pass_and_the_first_frame_is_not_compared(self) -> None:
        measured: dict[int, float | None] = {10: None, 11: -4.0, 12: 4.0}
        self.assertEqual(check.compare(10, [99.0, -4.0, 4.001], measured, 0.01), [])

    def test_differences_missing_and_extra_frames_are_reported(self) -> None:
        measured: dict[int, float | None] = {10: None, 12: 5.0, 13: 0.0}
        problems = check.compare(10, [0.0, 1.0, 4.0], measured, 0.01)
        self.assertEqual(len(problems), 3)
        self.assertIn("1 frame(s) not presented in the measurement, first 11", problems[0])
        self.assertIn("1 frame(s) the clip does not have, first 13", problems[1])
        self.assertIn("frame 2 (index 12): measured 5.0 ms, expected 4.0 ms", problems[2])

    def test_frames_a_fault_does_not_present_must_be_absent(self) -> None:
        # Frame 11 is dropped (or shown out of order): no error, and not measured
        expected: list[float | None] = [0.0, None, 4.0, 1.0]
        self.assertEqual(check.compare(10, expected, {10: None, 12: 4.0, 13: 1.0}, 0.01, [0, 2, 3]), [])
        problems = check.compare(10, expected, {10: None, 11: 2.0, 12: 4.0, 13: 1.0}, 0.01, [0, 2, 3])
        self.assertEqual(problems, ["1 frame(s) the clip does not present, first 11"])
        self.assertIn("1 frame(s) not presented in the measurement, first 12", check.compare(10, expected, {10: None, 13: 1.0}, 0.01, [0, 2, 3])[0])


class JudgedStepTests(unittest.TestCase):
    def test_a_step_judged_on_one_side_only_is_reported(self) -> None:
        # Frame 12's step is judged in the manifest and not in the measurement; frame 13's the other way round
        problems = check.compare(10, [0.0, 1.0, -100.0, None, 2.0], {10: None, 11: 1.0, 12: None, 13: 5.0, 14: 2.0}, 0.01)
        self.assertEqual(len(problems), 2)
        self.assertIn("frame 2 (index 12): not judged in the measurement, expected -100.0 ms", problems[0])
        self.assertIn("frame 3 (index 13): measured 5.0 ms, but its step is static by the manifest's flags", problems[1])

    def test_the_step_from_a_frame_assumed_static_is_not_judged(self) -> None:
        expected: list[float | None] = [0.0, 1.0, None, -100.0, 2.0]
        measured: dict[int, float | None] = {10: None, 11: 1.0, 13: None, 14: 2.0}
        # Frame 12 is dropped; mb-framepacing assumed frame 11 static, so the step into frame 13 has no error
        self.assertEqual(check.compare(10, expected, measured, 0.01, [0, 1, 3, 4], {11}), [])
        self.assertEqual(check.assumed_steps(10, expected, measured, [0, 1, 3, 4], {11}), 1)
        # Without the guess it is a difference; and with the guess off, the judged step is compared as usual
        self.assertEqual(len(check.compare(10, expected, measured, 0.01, [0, 1, 3, 4])), 1)
        self.assertEqual(check.compare(10, expected, {10: None, 11: 1.0, 13: -100.0, 14: 2.0}, 0.01, [0, 1, 3, 4]), [])
        self.assertEqual(check.assumed_steps(10, expected, {10: None, 11: 1.0, 13: -100.0, 14: 2.0}, [0, 1, 3, 4], set()), 0)

    def test_the_assumed_frames_come_from_the_flags_column(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "run-1-frames.csv"
            _ = path.write_text(
                "frameIndex,animationErrorTicks,flags\n10,,\n11,0,StaticAfter|StaticAssumed\n12,,SkippedBefore|StaticBefore\n13,-1000000,\n", encoding="utf-8"
            )
            self.assertEqual(check.assumed_static(Path(folder)), {11})
            # The errors are whole 100 ns ticks in the file, milliseconds here; an empty one is a step not judged
            self.assertEqual(check.measured_errors(Path(folder)), {10: None, 11: 0.0, 12: None, 13: -100.0})
            # An analysis without the column has none
            _ = path.write_text("frameIndex,animationErrorTicks\n10,\n11,0\n", encoding="utf-8")
            self.assertEqual(check.assumed_static(Path(folder)), set())


class ManifestTests(unittest.TestCase):
    def expected(self, after: list[bool], before: list[bool], presented: list[int] | None = None) -> tuple[int, list[float | None], list[int] | None]:
        frames = {"animationErrorMs": [0.0, 1.0, -100.0, 2.0, 3.0], "staticAfter": after, "staticBefore": before}
        box: dict[str, object] = {"frames": frames}
        if presented is not None:
            box["presented"] = presented
        manifest = {"videos": [{"file": "video.mp4", "markerFirstFrameIndex": 5, "box": box}]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "manifest.json"
            _ = path.write_text(json.dumps(manifest), encoding="utf-8")
            return check.expected_errors(path, "video.mp4")

    def test_the_step_from_a_static_frame_is_not_compared(self) -> None:
        none = [False] * 5
        # Frame 1 is static after (in advance) or frame 2 static before (in hindsight): the step from frame 1 (the paused clock's
        # -100 ms) is not judged; the step into frame 1 is
        self.assertEqual(self.expected([False, True, False, False, False], none), (5, [0.0, 1.0, None, 2.0, 3.0], None))
        self.assertEqual(self.expected(none, [False, False, True, False, False]), (5, [0.0, 1.0, None, 2.0, 3.0], None))
        # The clip's first frame follows its last one
        self.assertEqual(self.expected(none, [True, False, False, False, False])[1], [None, 1.0, -100.0, 2.0, 3.0])

    def test_static_before_after_a_frame_never_shown_marks_nothing(self) -> None:
        # Frame 1 is dropped: frame 2 follows frame 0, so its static before (for frame 1) leaves its step judged
        self.assertEqual(self.expected([False] * 5, [False, False, True, False, False], [0, 2, 3, 4]), (5, [0.0, 1.0, -100.0, 2.0, 3.0], [0, 2, 3, 4]))


if __name__ == "__main__":
    _ = unittest.main()
