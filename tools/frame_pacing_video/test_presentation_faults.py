# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""Tests of presentation_faults.py: dropped frames and frames out of order, only in what reaches the screen. Run from the repository
root (in the .venv): python -m unittest discover -s tools/frame_pacing_video -v
"""

import unittest
from fractions import Fraction

import frame_timing as ft
import presentation_faults as faults
from pcg32 import Pcg32

FPS = Fraction(60)
CLIP = 480  # 8 s at 60 fps
STORM = "60-naive-5ms-diagram-slow-frames-every-1s"
# Eight frames, one a refresh
FLIPS = (0, 1, 2, 3, 4, 5, 6, 7)


def events(name: str) -> tuple[ft.SimulatedFrames, list[faults.Block]]:
    mode = ft.parse_mode(name)
    frames = ft.simulate(mode, ft.TimingParameters(), CLIP)
    late = [flip - target for flip, target in zip(frames.flips, frames.targets, strict=True)]
    return frames, faults.blocks(mode, frames.flips, late, frames.intervals, FPS, CLIP)


class BlockTests(unittest.TestCase):
    def test_two_events_a_second_at_30_and_70_percent(self) -> None:
        for fault in (faults.DROPPED, faults.OUT_OF_ORDER):
            frames, blocks = events(f"{STORM}-{fault}")
            self.assertEqual(len(blocks), 16, fault)
            starts = [frames.flips[block.first] for block in blocks]
            self.assertEqual(starts, [second * 60 + at for second in range(8) for at in (18, 42)], fault)

    def test_before_wake_drops_the_first_single_frame_rest_after_the_first_frame(self) -> None:
        mode = ft.parse_mode("60-on-demand-paused-clock-hindsight-dropped-before-wake")
        # Frame 0 rests (the clip's first frame is never dropped); frame 3 is the first rest between moving frames
        self.assertEqual(faults.wake_event(mode, (True, False, False, True, False, True, False)), faults.Block(3, 1))
        with self.assertRaisesRegex(ValueError, "no rest of a single frame"):
            _ = faults.wake_event(mode, (True, False, False, False))
        # The frame before it stays on screen
        self.assertEqual(faults.screen((0, 1, 2, 5, 6), 8, faults.DROPPED_BEFORE_WAKE, [faults.Block(3, 1)]), (0, 1, 2, 2, 2, 2, 4, 4))

    def test_a_stall_holds_a_moving_frame_as_long_as_a_rest_and_the_next_frame_is_dropped(self) -> None:
        mode = ft.parse_mode("60-on-demand-paused-clock-hindsight-dropped-after-stall")
        # The frame on screen at 30 % of the first second (refresh 18) stays 7 refreshes: the 6 frames after it are not rendered
        self.assertEqual(faults.stall(mode, tuple(range(CLIP)), FPS), range(19, 25))
        # Over the rendered frames: frame 2 rests and frame 3 comes 7 refreshes later (a rest's wait); frame 5 moves and frame 6
        # comes 7 refreshes later: the stall
        flips, resting = (0, 1, 2, 9, 10, 11, 18, 19), (False, False, True, False, False, False, False, False)
        self.assertEqual(faults.after_stall(mode, flips, resting), faults.Block(6, 1))
        with self.assertRaisesRegex(ValueError, "no stall of 7 refreshes"):
            _ = faults.after_stall(mode, flips[:5], resting[:5])
        # The stalled frame stays on screen a refresh longer
        self.assertEqual(faults.screen(flips, 20, faults.DROPPED_AFTER_STALL, [faults.Block(6, 1)])[11:], (5,) * 8 + (7,))

    def test_the_wake_up_frame_after_that_rest_is_dropped(self) -> None:
        mode = ft.parse_mode("60-on-demand-paused-clock-hindsight-dropped-wake")
        # The frame after the rest's frame (3), with a moving frame after it to be shown next
        self.assertEqual(faults.wake_event(mode, (True, False, False, True, False, False, True, False)), faults.Block(4, 1))
        # A wake-up frame followed by another rest is passed over: the next shown frame must move
        self.assertEqual(faults.wake_event(mode, (True, False, True, False, True, False, False)), faults.Block(5, 1))
        with self.assertRaisesRegex(ValueError, "no rest of a single frame"):
            _ = faults.wake_event(mode, (True, False, False, True, False))
        # The rest's frame stays on screen a refresh longer
        self.assertEqual(faults.screen((0, 1, 2, 5, 6, 7), 9, faults.DROPPED_WAKE, [faults.Block(3, 1)]), (0, 1, 2, 2, 2, 2, 4, 5, 5))

    def test_drop_runs_are_1_to_4_frames(self) -> None:
        _, blocks = events(f"{STORM}-dropped-frames")
        self.assertEqual([block.count for block in blocks], [1, 2, 3, 4] * 4)
        self.assertTrue(all(block.order == () for block in blocks))

    def test_out_of_order_blocks_are_swapped_pairs_and_derangements(self) -> None:
        _, blocks = events(f"{STORM}-out-of-order")
        self.assertEqual([block.count for block in blocks], [2, 3, 2, 4] * 4)
        for block in blocks:
            self.assertEqual(sorted(block.order), list(range(block.count)), block)
            self.assertTrue(all(offset != index for index, offset in enumerate(block.order)), block)
        self.assertEqual({block.order for block in blocks if block.count == 2}, {(1, 0)})
        # Deterministic: the same clip always gets the same order
        self.assertEqual(blocks, events(f"{STORM}-out-of-order")[1])

    def test_derangements_have_no_fixed_point(self) -> None:
        generator = Pcg32.from_text("test")
        for size in (2, 3, 4, 5):
            for _ in range(20):
                order = faults.derangement(generator, size)
                self.assertEqual(sorted(order), list(range(size)))
                self.assertTrue(all(offset != index for index, offset in enumerate(order)))
        with self.assertRaises(ValueError):
            _ = faults.derangement(generator, 1)

    def test_a_block_on_late_or_held_frames_is_refused(self) -> None:
        # Three copies of the diagram a second sit at 30, 50 and 70 %, on the fault events' frames
        with self.assertRaisesRegex(ValueError, "must be on time and shown for one swap interval"):
            _ = events("60-diagram-slow-frames-3x-every-1s-dropped-frames")

    def test_any_mode_can_have_a_fault(self) -> None:
        for name in ("60-dropped-frames", "30-out-of-order", "60-naive-5ms-out-of-order"):
            self.assertEqual(len(events(name)[1]), 16, name)


class ScreenTests(unittest.TestCase):
    def test_without_events_every_frame_shows_from_its_flip(self) -> None:
        self.assertEqual(faults.base_screen((0, 2, 3), 5), (0, 0, 1, 2, 2))

    def test_dropped_frames_leave_the_frame_before_on_screen(self) -> None:
        screen = faults.screen(FLIPS, 8, faults.DROPPED, [faults.Block(2, 3)])
        self.assertEqual(screen, (0, 1, 1, 1, 1, 5, 6, 7))
        shown = faults.presented(screen)
        self.assertEqual(shown, {0: 0, 1: 1, 5: 5, 6: 6, 7: 7})
        self.assertEqual((faults.skipped_frame_indices(shown), faults.out_of_order_refreshes(screen)), (3, 0))

    def test_frames_out_of_order_show_in_the_blocks_order(self) -> None:
        screen = faults.screen(FLIPS, 8, faults.OUT_OF_ORDER, [faults.Block(2, 2, (1, 0)), faults.Block(5, 3, (2, 0, 1))])
        self.assertEqual(screen, (0, 1, 3, 2, 4, 7, 5, 6))
        # 2 comes after 3, and 5 and 6 after 7: not presented, their refreshes out of order
        shown = faults.presented(screen)
        self.assertEqual(shown, {0: 0, 1: 1, 3: 2, 4: 4, 7: 5})
        self.assertEqual((faults.skipped_frame_indices(shown), faults.out_of_order_refreshes(screen)), (3, 3))


if __name__ == "__main__":
    _ = unittest.main()
