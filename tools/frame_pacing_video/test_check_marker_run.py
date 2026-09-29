# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""Tests of check_marker_run.py: comparing mb-framepacing's measurement of a marked clip with the generator's manifest."""

import unittest

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


if __name__ == "__main__":
    _ = unittest.main()
