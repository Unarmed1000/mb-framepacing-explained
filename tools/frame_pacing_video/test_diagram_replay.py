"""Tests of diagram_replay.py: videos that replay a timing diagram's frames exactly. Run from the repository root (in the .venv):
python -m unittest discover -s tools/frame_pacing_video -v
"""

import unittest
from fractions import Fraction

import diagram_replay as replay
import frame_timing as ft

PARAMETERS = ft.TimingParameters()
CLIP = 480  # 8 s at 60 fps
REFRESH = Fraction(1, 60)


def frames(name: str) -> ft.SimulatedFrames:
    return ft.simulate(ft.parse_mode(name), PARAMETERS, CLIP)


def holds(simulated: ft.SimulatedFrames) -> list[int]:
    """How many refreshes each frame stays on screen (the last one until the loop's first)."""
    flips = simulated.flips
    return [b - a for a, b in zip(flips, [*flips[1:], flips[0] + CLIP], strict=True)]


def errors_ms(simulated: ft.SimulatedFrames) -> list[Fraction]:
    """Each frame's animation error (ms), as PresentMon computes it; the first frame follows the last of the previous loop."""
    flips, animation = simulated.flips, simulated.animation
    previous = [(flips[-1] - CLIP, animation[-1] - CLIP * REFRESH), *zip(flips, animation, strict=True)]
    return [
        ((moment - before_moment) - (flip - before_flip) * REFRESH) * 1000
        for (flip, moment), (before_flip, before_moment) in zip(zip(flips, animation, strict=True), previous, strict=False)
    ]


class PatternTests(unittest.TestCase):
    def test_the_smallest_unit_repeats_to_every_frame_of_the_diagram(self) -> None:
        # Slow frames: A on time and held two refreshes (B misses its refresh), B late, C catching up; the diagram is two of these
        slow = replay.pattern("slow-frames")
        self.assertEqual((slow.shown, slow.animation, slow.length), ((0, 2, 3), (0, 1, 3), 4))
        # Bad half rate: frames held for 1 and 3 refreshes, the animation stepping 2 each
        bad = replay.pattern("half-rate-bad-pacing")
        self.assertEqual((bad.shown, bad.animation, bad.length), ((0, 1), (0, 2), 4))
        # Hysteresis does not repeat within itself: its unit is the diagram up to its last frame, which is also the next unit's first
        self.assertEqual(replay.pattern("switching-hysteresis").length, 13)

    def test_every_fixed_rate_diagram_can_be_replayed_and_vrr_cannot(self) -> None:
        self.assertNotIn("vrr-slow-frames", replay.replayable())
        for name in replay.replayable():
            simulated = frames(f"60-diagram-{name}")
            self.assertEqual(simulated.flips[0], 0, name)
            self.assertEqual(sum(holds(simulated)), CLIP, name)
        with self.assertRaisesRegex(ValueError, "VRR"):
            _ = frames("60-diagram-vrr-slow-frames")
        with self.assertRaisesRegex(ValueError, "no diagram named 'hitch'"):
            _ = frames("60-diagram-hitch")


class ReplayTests(unittest.TestCase):
    def test_slow_frames_play_exactly_as_the_diagram_at_60_hz(self) -> None:
        simulated = frames("60-diagram-slow-frames")
        # One diagram refresh is one refresh: a frame held for two, then the late one and the one catching up, 120 times
        self.assertEqual(holds(simulated), [2, 1, 1] * 120)
        self.assertEqual(errors_ms(simulated), [0, Fraction(-50, 3), Fraction(50, 3)] * 120)

    def test_bad_half_rate_holds_frames_one_and_three_refreshes(self) -> None:
        simulated = frames("60-diagram-half-rate-bad-pacing")
        self.assertEqual(holds(simulated), [1, 3] * 120)
        self.assertEqual(errors_ms(simulated), [Fraction(-50, 3), Fraction(50, 3)] * 120)

    def test_a_unit_that_does_not_divide_the_clip_is_filled_with_on_time_frames(self) -> None:
        # Hysteresis: 13 refreshes, repeated every 15 (480 / 15 = 32) with two more frames at full rate
        simulated = frames("60-diagram-switching-hysteresis")
        self.assertEqual(holds(simulated)[:9], [2, 2, 2, 2, 2, 2, 1, 1, 1])
        self.assertEqual(sum(holds(simulated)[:9]), 15)

    def test_every_repeats_the_unit_once_per_period_and_plays_on_time_frames_between(self) -> None:
        simulated = frames("60-diagram-slow-frames-every-1s")
        self.assertEqual(holds(simulated)[:4], [2, 1, 1, 1])
        self.assertEqual(sum(1 for error in errors_ms(simulated) if error < 0), 8)
        with self.assertRaisesRegex(ValueError, "cannot repeat every 7 refreshes"):
            _ = replay.schedule("slow-frames", Fraction(7, 60), CLIP, 1, Fraction(60))

    def test_names_and_labels(self) -> None:
        mode = ft.parse_mode("60-diagram-slow-frames-every-1.5s")
        self.assertEqual((mode.rate, mode.diagram, mode.every), (60, "slow-frames", Fraction(3, 2)))
        self.assertEqual(ft.describe(ft.parse_mode("60-diagram-half-rate-bad-pacing"), PARAMETERS), "60 Hz, half rate, bad frame pacing (as the diagram)")
        self.assertEqual(ft.describe(mode, PARAMETERS), "60 Hz, slow frames (as the diagram, every 1.5 s)")


if __name__ == "__main__":
    _ = unittest.main()
