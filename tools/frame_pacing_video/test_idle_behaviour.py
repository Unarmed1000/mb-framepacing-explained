# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""Tests of idle_behaviour.py: what a game renders while nothing moves, and what its markers say. Run from the repository root (in
the .venv): python -m unittest discover -s tools/frame_pacing_video -v
"""

import unittest
from collections.abc import Callable
from fractions import Fraction

import frame_timing as ft
import idle_behaviour as idle

FPS = Fraction(60)
FRAME = 1 / FPS


def clip(count: int) -> ft.SimulatedFrames:
    """`count` frames at 60 Hz, one a refresh, each showing its own flip's moment."""
    moments = tuple(index * FRAME for index in range(count))
    return ft.SimulatedFrames(tuple(range(count)), moments, moments, tuple(range(count)), (1,) * count, moments, (FRAME / 2,) * count)


def resting(*spans: tuple[int, int]) -> Callable[[Fraction], bool]:
    """At rest in the refreshes of the spans (from, to inclusive)."""
    return lambda moment: any(low <= moment * FPS <= high for low, high in spans)


class IdleTests(unittest.TestCase):
    def test_static_rests_renders_every_frame_and_flags_the_ones_at_rest(self) -> None:
        result = idle.apply(ft.parse_mode("60-static-rests"), clip(10), resting((0, 1), (5, 7)), FPS)
        self.assertEqual(result.frames, clip(10))
        self.assertEqual(result.static, (True, True, False, False, False, True, True, True, False, False))
        self.assertFalse(result.on_demand)

    def test_on_demand_renders_only_the_first_frame_at_rest(self) -> None:
        result = idle.apply(ft.parse_mode("60-on-demand"), clip(10), resting((0, 1), (5, 7)), FPS)
        # Frame 0 always, then 2 to 5, then nothing until frame 8 moves
        self.assertEqual(result.frames.flips, (0, 2, 3, 4, 5, 8, 9))
        self.assertEqual(result.static, (True, False, False, False, True, False, False))
        self.assertTrue(result.on_demand)
        # The clock runs on: every frame shows its own flip's moment
        self.assertEqual(result.frames.animation, tuple(Fraction(flip) / FPS for flip in result.frames.flips))
        self.assertEqual(result.scene, result.frames.animation)

    def test_a_paused_clock_resumes_with_one_frames_step(self) -> None:
        result = idle.apply(ft.parse_mode("60-on-demand-paused-clock"), clip(10), resting((0, 1), (5, 7)), FPS)
        self.assertEqual(result.frames.flips, (0, 2, 3, 4, 5, 8, 9))
        # The scene is where the box is drawn; the clock is behind it after each rest: 1 frame (0 -> 2), 1 frame (5 -> 8)
        self.assertEqual(result.scene, tuple(Fraction(flip) / FPS for flip in result.frames.flips))
        self.assertEqual([moment * FPS for moment in result.frames.animation], [0, 1, 2, 3, 4, 5, 6])

    def test_idling_at_1_fps_keeps_a_frame_a_second_paced_at_the_idle_rate(self) -> None:
        # At rest from the start and from refresh 100 to the clip's end
        result = idle.apply(ft.parse_mode("60-idle-1fps"), clip(240), resting((0, 30), (100, 239)), FPS)
        flips = result.frames.flips
        self.assertEqual([flip for flip, still in zip(flips, result.static, strict=True) if still], [0, 100, 160, 220])
        self.assertEqual(flips[-1], 220)
        # The clip's first follows the previous loop's last at rest (idle); the first at rest still comes at the full rate
        intervals = dict(zip(flips, result.frames.intervals, strict=True))
        self.assertEqual((intervals[0], intervals[31], intervals[100], intervals[160], intervals[220]), (60, 1, 1, 60, 60))
        self.assertFalse(result.on_demand)

    def test_the_box_must_rest(self) -> None:
        with self.assertRaisesRegex(ValueError, "never rests at this speed"):
            _ = idle.apply(ft.parse_mode("60-on-demand"), clip(10), resting(), FPS)
        with self.assertRaisesRegex(ValueError, "never rests 1 s"):
            _ = idle.apply(ft.parse_mode("60-idle-1fps"), clip(120), resting((10, 20), (60, 70)), FPS)


if __name__ == "__main__":
    _ = unittest.main()
