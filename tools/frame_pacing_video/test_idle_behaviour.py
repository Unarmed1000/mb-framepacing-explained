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
        self.assertEqual(result.resting, (True, True, False, False, False, True, True, True, False, False))
        self.assertEqual((result.static_after, result.static_before), (result.resting, (False,) * 10))
        self.assertFalse(result.on_demand)

    def test_static_rests_with_a_paused_clock_flag_both_inside_a_rest(self) -> None:
        result = idle.apply(ft.parse_mode("60-static-rests-paused-clock"), clip(10), resting((0, 1), (5, 7)), FPS)
        self.assertEqual(result.frames.flips, clip(10).flips)
        self.assertEqual(result.static_after, result.resting)
        # The frame that reaches the rest pose (5) is static after only; inside the rest (1, 6, 7) both. The clip's first frame follows
        # its last, which moves
        self.assertEqual(result.static_before, (False, True, False, False, False, False, True, True, False, False))
        # The clock stands through each rest and resumes with one frame's step; the frame that reaches the rest pose keeps its step
        self.assertEqual([moment * FPS for moment in result.frames.animation], [0, 0, 1, 2, 3, 4, 4, 4, 5, 6])
        self.assertEqual(result.scene, clip(10).animation)

    def test_on_demand_renders_only_the_first_frame_at_rest(self) -> None:
        result = idle.apply(ft.parse_mode("60-on-demand"), clip(10), resting((0, 1), (5, 7)), FPS)
        # Frame 0 always, then 2 to 5, then nothing until frame 8 moves
        self.assertEqual(result.frames.flips, (0, 2, 3, 4, 5, 8, 9))
        self.assertEqual(result.resting, (True, False, False, False, True, False, False))
        self.assertEqual((result.static_after, result.static_before), (result.resting, (False,) * 7))
        self.assertTrue(result.on_demand)
        # The clock runs on: every frame shows its own flip's moment
        self.assertEqual(result.frames.animation, tuple(Fraction(flip) / FPS for flip in result.frames.flips))
        self.assertEqual(result.scene, result.frames.animation)

    def test_a_stall_renders_nothing_while_the_clock_runs_on(self) -> None:
        mode = ft.parse_mode("60-on-demand-paused-clock-hindsight")
        result = idle.apply(mode, clip(12), resting((0, 1), (9, 11)), FPS, range(4, 7))
        # Frames 4 to 6 are not rendered: frame 3 stays on screen 4 refreshes, and frame 7 shows its own moment (the paused clock is
        # 1 frame behind since the first rest, as before the stall)
        self.assertEqual(result.frames.flips, (0, 2, 3, 7, 8, 9))
        self.assertEqual(result.scene, tuple(Fraction(flip) / FPS for flip in result.frames.flips))
        self.assertEqual([moment * FPS for moment in result.frames.animation], [0, 1, 2, 6, 7, 8])
        # Nothing was static in the stall: only the rests are flagged (on the frames after them)
        self.assertEqual(result.resting, (True, False, False, False, False, True))
        self.assertEqual(result.static_before, (True, True, False, False, False, False))
        with self.assertRaisesRegex(ValueError, "away from every rest"):
            _ = idle.apply(mode, clip(12), resting((0, 1), (9, 11)), FPS, range(2, 4))
        with self.assertRaisesRegex(ValueError, "away from every rest"):
            _ = idle.apply(mode, clip(12), resting((0, 1), (9, 11)), FPS, range(6, 9))
        with self.assertRaisesRegex(ValueError, "needs a game that presents on demand"):
            _ = idle.apply(ft.parse_mode("60-static-rests"), clip(12), resting((0, 1), (9, 11)), FPS, range(4, 7))

    def test_a_paused_clock_resumes_with_one_frames_step(self) -> None:
        result = idle.apply(ft.parse_mode("60-on-demand-paused-clock"), clip(10), resting((0, 1), (5, 7)), FPS)
        self.assertEqual(result.frames.flips, (0, 2, 3, 4, 5, 8, 9))
        # The scene is where the box is drawn; the clock is behind it after each rest: 1 frame (0 -> 2), 1 frame (5 -> 8)
        self.assertEqual(result.scene, tuple(Fraction(flip) / FPS for flip in result.frames.flips))
        self.assertEqual([moment * FPS for moment in result.frames.animation], [0, 1, 2, 3, 4, 5, 6])

    def test_hindsight_moves_the_flag_to_the_frame_that_wakes_up(self) -> None:
        advance = idle.apply(ft.parse_mode("60-on-demand-paused-clock"), clip(10), resting((0, 1), (5, 7)), FPS)
        hindsight = idle.apply(ft.parse_mode("60-on-demand-paused-clock-hindsight"), clip(10), resting((0, 1), (5, 7)), FPS)
        self.assertEqual((hindsight.frames, hindsight.scene, hindsight.resting, hindsight.on_demand), (advance.frames, advance.scene, advance.resting, True))
        self.assertEqual(hindsight.static_after, (False,) * 7)
        # Static before on the frame after each rest frame: the frame shown before it
        self.assertEqual(hindsight.static_before, (False, True, False, False, False, True, False))
        self.assertEqual(hindsight.static_before, advance.static_after[-1:] + advance.static_after[:-1])

    def test_idling_at_1_fps_keeps_a_frame_a_second_paced_at_the_idle_rate(self) -> None:
        # At rest from the start and from refresh 100 to the clip's end
        result = idle.apply(ft.parse_mode("60-idle-1fps"), clip(240), resting((0, 30), (100, 239)), FPS)
        flips = result.frames.flips
        self.assertEqual([flip for flip, still in zip(flips, result.static_after, strict=True) if still], [0, 100, 160, 220])
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
