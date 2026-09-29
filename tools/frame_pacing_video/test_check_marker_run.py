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


class ManifestTests(unittest.TestCase):
    def test_a_step_from_or_to_a_static_frame_is_not_compared(self) -> None:
        frames = {"animationErrorMs": [0.0, 1.0, -100.0, 2.0, 3.0], "static": [False, True, False, False, False]}
        manifest = {"videos": [{"file": "video.mp4", "markerFirstFrameIndex": 5, "box": {"frames": frames}}]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "manifest.json"
            _ = path.write_text(json.dumps(manifest), encoding="utf-8")
            first, expected, presented = check.expected_errors(path, "video.mp4")
        # Frame 1 is static, so neither its step nor the one after it (the paused clock's -100 ms) is judged
        self.assertEqual((first, expected, presented), (5, [0.0, None, None, 2.0, 3.0], None))


if __name__ == "__main__":
    _ = unittest.main()
