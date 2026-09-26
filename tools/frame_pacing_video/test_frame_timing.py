"""Tests of frame_timing.py, the simulated frame loop. Run from the repository root (in the .venv):
python -m unittest discover -s tools/frame_pacing_video -v
"""

import itertools
import unittest
from fractions import Fraction

import frame_timing as ft

PARAMETERS = ft.TimingParameters()
MS = Fraction(1, 1000)
FRAME = Fraction(1, 60)
CLIP = 480  # 8 s at 60 fps


def frames(name: str, refreshes: int = CLIP, parameters: ft.TimingParameters = PARAMETERS) -> ft.SimulatedFrames:
    return ft.simulate(ft.parse_mode(name), parameters, refreshes)


def runs(flags: list[bool]) -> list[int]:
    """Lengths of the runs of True."""
    return [len(list(group)) for key, group in itertools.groupby(flags) if key]


class ModeTests(unittest.TestCase):
    def test_names(self) -> None:
        self.assertEqual(ft.parse_mode("60"), ft.FrameMode("60", 60, ft.Timer.IDEAL, None))
        self.assertEqual(ft.parse_mode("30-naive-heavy"), ft.FrameMode("30-naive-heavy", 30, ft.Timer.NAIVE, ft.Noise.HEAVY))
        self.assertEqual(ft.parse_mode("60-naive-1ms"), ft.FrameMode("60-naive-1ms", 60, ft.Timer.NAIVE, ft.Noise.WINDOW, MS))
        self.assertEqual(ft.parse_mode("60-naive-0.5ms").window, MS / 2)
        self.assertEqual(
            ft.parse_mode("60-naive-typical-realistic"), ft.FrameMode("60-naive-typical-realistic", 60, ft.Timer.NAIVE, ft.Noise.TYPICAL, realistic=True)
        )
        bad_names = ("60-late", "60-naive", "naive-typical", "060", "60-naive-busy", "60-naive-0ms", "60-naive-ms", "60-realistic", "60-naive-1ms-realistic")
        for bad in (*bad_names, "60-naive-synthetic-realistic", "60-naive-typical-demo"):
            with self.assertRaisesRegex(ValueError, "is not a mode"):
                _ = ft.parse_mode(bad)

    def test_labels(self) -> None:
        self.assertEqual(ft.describe(ft.parse_mode("60"), PARAMETERS), "60 Hz ideal timer")
        self.assertEqual(ft.describe(ft.parse_mode("30-naive-typical"), PARAMETERS), "30 Hz naive timer, typical load")
        self.assertEqual(ft.describe(ft.parse_mode("60-naive-heavy-realistic"), PARAMETERS), "60 Hz naive timer, heavy load (realistic)")
        self.assertEqual(ft.describe(ft.parse_mode("60-naive-4ms"), PARAMETERS), "60 Hz naive timer, ±4 ms mixed")
        self.assertEqual(ft.describe(ft.parse_mode("60-naive-synthetic"), PARAMETERS), "60 Hz naive timer, synthetic ±1 ms mixed")


class LoopTests(unittest.TestCase):
    def test_every_frame_makes_its_vsync(self) -> None:
        # Rendering always fits: frame n is flipped on refresh n x the swap interval, whatever the timer and noise
        for name, interval in (("60", 1), ("30-naive-typical", 2), ("20-naive-heavy", 3), ("60-naive-4ms", 1)):
            self.assertEqual(frames(name).flips, tuple(range(0, CLIP, interval)), name)

    def test_the_ideal_timer_shows_the_display_time(self) -> None:
        for name in ("60", "30", "20"):
            simulated = frames(name)
            self.assertEqual(simulated.animation, tuple(Fraction(flip, 60) for flip in simulated.flips), name)

    def test_the_naive_timer_reads_the_wall_clock_after_the_previous_flip(self) -> None:
        mode = ft.parse_mode("60-naive-heavy")
        simulated = ft.simulate(mode, PARAMETERS, CLIP)
        wakes = ft.wake_delays(mode, PARAMETERS, CLIP)
        # Frame n reads the clock its wake-up delay after frame n - 1 was flipped (frame 0 after the flip before the clip)
        self.assertEqual(simulated.samples, tuple((index - 1) * FRAME + wake for index, wake in enumerate(wakes)))
        # Its animation time is that reading minus the constant latency (the average delay): off by how its delay differs from it
        average = sum(wakes, Fraction(0)) / CLIP
        self.assertEqual(simulated.animation, tuple(index * FRAME + wake - average for index, wake in enumerate(wakes)))
        errors = [a - Fraction(index, 60) for index, a in enumerate(simulated.animation)]
        self.assertTrue(any(error > MS / 2 for error in errors) and any(error < -MS / 2 for error in errors), "ahead and behind")

    def test_moving_by_speed_times_dt_ends_where_the_animation_time_says(self) -> None:
        # x += speed * dt, frame after frame, is exactly speed x animation time: the errors do not build up
        simulated = frames("60-naive-heavy")
        speed = Fraction(384)
        x = speed * simulated.animation[0]
        for previous, current in itertools.pairwise(simulated.animation):
            x += speed * (current - previous)
            self.assertEqual(x, speed * current)

    def test_the_loop_seam_is_just_another_frame(self) -> None:
        for name in ("60-naive-typical", "60-naive-4ms"):
            dts = ft.delta_times(frames(name), Fraction(8))
            self.assertEqual(sum(dts), 8, name)
            self.assertTrue(all(0 < dt < 2 * FRAME for dt in dts), name)

    def test_deterministic_per_mode_and_clip(self) -> None:
        mode = ft.parse_mode("60-naive-heavy")
        self.assertEqual(frames("60-naive-heavy"), ft.simulate(mode, ft.TimingParameters(), CLIP))
        self.assertNotEqual(ft.wake_delays(mode, PARAMETERS, CLIP)[:60], ft.wake_delays(mode, PARAMETERS, 2 * CLIP)[:60])


class LoadTests(unittest.TestCase):
    def offsets(self, name: str, count: int = 60000, parameters: ft.TimingParameters = PARAMETERS) -> list[Fraction]:
        """How much later (or sooner) than the usual work each frame reads the clock."""
        return [wake - parameters.base for wake in ft.wake_delays(ft.parse_mode(name), parameters, count)]

    def assert_shares(self, offsets: list[Fraction], expected: tuple[float, float, float], name: str) -> None:
        one = sum(Fraction(8, 10) * MS <= abs(offset) <= Fraction(12, 10) * MS for offset in offsets) / len(offsets)
        two = sum(Fraction(17, 10) * MS <= abs(offset) <= 2 * MS for offset in offsets) / len(offsets)
        spike = sum(4 * MS <= offset <= 8 * MS for offset in offsets) / len(offsets)
        for share, target in zip((one, two, spike), expected, strict=True):
            self.assertAlmostEqual(float(share), target, delta=max(0.004, target * 0.25), msg=name)

    def test_each_load_has_its_share_of_longer_reads_in_both_halves(self) -> None:
        for name, expected in (
            ("60-naive-light-realistic", (0.03, 0.01, 0.0)),
            ("60-naive-typical-realistic", (0.07, 0.02, 0.0)),
            ("60-naive-heavy-realistic", (0.12, 0.06, 0.02)),
        ):
            offsets = self.offsets(name)
            self.assert_shares(offsets[:30000], expected, name)
            self.assert_shares(offsets[30000:], expected, name)
            # Everything else is the usual short read, 0 to 0.3 ms after the usual work; nothing outside the ranges
            for offset in offsets:
                self.assertTrue(
                    0 <= offset <= Fraction(3, 10) * MS
                    or Fraction(8, 10) * MS <= abs(offset) <= Fraction(12, 10) * MS
                    or Fraction(17, 10) * MS <= abs(offset) <= 2 * MS
                    or 4 * MS <= offset <= 8 * MS,
                    (name, offset),
                )

    def test_the_demo_profile_has_errors_in_most_frames_and_the_loads_differ_in_how_bad(self) -> None:
        # 95 % of the frames by default: light all about 1 ms, typical half up to 2 ms, heavy up to 2 ms and spikes
        self.assertEqual(PARAMETERS.demo_load_share, Fraction(19, 20))
        for name, expected in (
            ("60-naive-light", (0.95, 0.0, 0.0)),
            ("60-naive-typical", (0.475, 0.475, 0.0)),
            ("60-naive-heavy", (0.0, 0.855, 0.095)),
        ):
            offsets = self.offsets(name)
            self.assert_shares(offsets[:30000], expected, name)
            self.assert_shares(offsets[30000:], expected, name)
        # Any other share, split the same way
        offsets = self.offsets("60-naive-typical", parameters=ft.TimingParameters(demo_load_share=Fraction(1, 2)))
        self.assert_shares(offsets, (0.25, 0.25, 0.0), "typical at 50 %")
        # Each profile has its own draws
        self.assertNotEqual(self.offsets("60-naive-heavy", 60), self.offsets("60-naive-heavy-realistic", 60))

    def test_the_longer_reads_go_both_ways_but_spikes_only_late(self) -> None:
        offsets = self.offsets("60-naive-heavy-realistic")
        early = sum(offset < 0 for offset in offsets)
        late = sum(Fraction(3, 10) * MS < offset < 4 * MS for offset in offsets)
        self.assertAlmostEqual(early / late, 1, delta=0.1)
        self.assertGreaterEqual(min(offsets), -2 * MS)

    def test_single_frames_first_then_spells(self) -> None:
        offsets = self.offsets("60-naive-typical-realistic")
        longer = [abs(offset) > Fraction(3, 10) * MS for offset in offsets]
        singles, spells = runs(longer[:30000]), runs(longer[30000:])
        self.assertLess(sum(singles) / len(singles), 1.3)
        self.assertTrue(5.5 < sum(spells) / len(spells) < 7.5, sum(spells) / len(spells))
        # A spell keeps its direction: the sign only changes where two spells happen to touch
        longer_offsets = [offset for offset in offsets[30000:] if abs(offset) > Fraction(3, 10) * MS]
        flips = sum((a > 0) != (b > 0) for a, b in itertools.pairwise(longer_offsets))
        self.assertLess(flips, len(spells))


class WindowTests(unittest.TestCase):
    def test_a_window_follows_the_jitter_pattern(self) -> None:
        for name, window in (("60-naive-1ms", MS), ("60-naive-4ms", 4 * MS)):
            wakes = ft.wake_delays(ft.parse_mode(name), PARAMETERS, CLIP)
            self.assertEqual(wakes, [window * (1 + offset) for offset in ft.jitter_offsets(60, CLIP)], name)
        # The windows share one pattern, scaled
        one = ft.wake_delays(ft.parse_mode("60-naive-1ms"), PARAMETERS, CLIP)
        four = ft.wake_delays(ft.parse_mode("60-naive-4ms"), PARAMETERS, CLIP)
        self.assertEqual([4 * wake for wake in one], four)

    def test_synthetic_is_the_pattern_within_its_amount(self) -> None:
        mode = ft.parse_mode("60-naive-synthetic")
        for pattern in ft.JITTER_PATTERNS:
            simulated = ft.simulate(mode, ft.TimingParameters(synthetic_pattern=pattern), CLIP)
            offsets = ft.jitter_offsets(60, CLIP, pattern)
            average = sum(offsets, Fraction(0)) / CLIP
            errors = [a - Fraction(index, 60) for index, a in enumerate(simulated.animation)]
            self.assertEqual(errors, [MS * (offset - average) for offset in offsets], pattern)


class JitterPatternTests(unittest.TestCase):
    def test_random_offsets_are_deterministic_and_loop(self) -> None:
        offsets = ft.jitter_offsets(30, 135, "random")
        self.assertEqual(offsets, ft.jitter_offsets(30, 135, "random"))
        self.assertNotEqual(offsets, ft.jitter_offsets(30, 75, "random"))
        self.assertGreater(len(set(offsets)), 10)
        self.assertEqual(max(abs(offset) for offset in offsets), 1)

    def test_alternating(self) -> None:
        self.assertEqual(ft.jitter_offsets(60, 6, "alternating"), (1, -1, 1, -1, 1, -1))
        # An odd count ends on 0, so the loop does not join two +1s
        self.assertEqual(ft.jitter_offsets(30, 5, "alternating"), (1, -1, 1, -1, 0))

    def test_runs_stay_on_one_side(self) -> None:
        offsets = ft.jitter_offsets(60, CLIP, "runs")
        sides = [len(list(group)) for _, group in itertools.groupby(offsets, key=lambda offset: offset > 0)]
        # Inside the clip every run is RUN_FRAMES long (the first and last can be cut by the loop point)
        self.assertTrue(all(ft.RUN_FRAMES[0] <= length <= ft.RUN_FRAMES[1] for length in sides[1:-1]), sides)
        self.assertTrue(all(abs(offset) >= Fraction(1, 2) for offset in offsets[:-1]))

    def test_mixed_goes_through_the_patterns(self) -> None:
        kinds = ft.jitter_kinds(CLIP, "mixed")
        self.assertEqual([kind for kind, _ in itertools.groupby(kinds)], list(ft.MIXED_PATTERNS))
        self.assertEqual(kinds.count("alternating"), CLIP // 4)

    def test_every_clip_length_keeps_the_rules(self) -> None:
        # Consecutive errors always differ by at least JITTER_MIN_CHANGE, also over the loop point, and the largest is +-1
        for pattern in ft.JITTER_PATTERNS:
            for rate in (60, 30, 20):
                for count in range(2, 400):
                    offsets = ft.jitter_offsets(rate, count, pattern)
                    for a, b in itertools.pairwise([*offsets, offsets[0]]):
                        self.assertGreaterEqual(abs(b - a), ft.JITTER_MIN_CHANGE, (pattern, rate, count))
                    self.assertEqual(max(abs(offset) for offset in offsets), 1, (pattern, rate, count))


class ValidationTests(unittest.TestCase):
    def assert_rejected(self, name: str, message: str, **parameters: object) -> None:
        with self.assertRaisesRegex(ValueError, message):
            ft.validate(ft.parse_mode(name), ft.TimingParameters(**parameters))  # pyright: ignore[reportArgumentType]

    def test_every_frame_must_make_its_vsync(self) -> None:
        # Heavy load: up to 2 + 8 ms late plus 30 % of 16.7 ms rendering fits; with 50 % rendering it does not
        ft.validate(ft.parse_mode("60-naive-heavy"), PARAMETERS)
        self.assert_rejected("60-naive-heavy", "60-naive-heavy would miss a vsync", frame_cost=Fraction(1, 2))
        # A +-6 ms window (up to 12 ms late) with 30 % rendering does not fit in 16.7 ms, but does at 30 Hz
        self.assert_rejected("60-naive-6ms", "60-naive-6ms would miss a vsync")
        ft.validate(ft.parse_mode("30-naive-6ms"), PARAMETERS)
        self.assert_rejected("60", "frame cost must be at least 0 and less than 1", frame_cost=Fraction(1))

    def test_rates_and_synthetic_amount(self) -> None:
        self.assert_rejected("60", "not a whole multiple of 60 Hz", fps=Fraction(50))
        self.assert_rejected("60-naive-synthetic", "less than half the 60 Hz frame time", synthetic=9 * MS)
        self.assert_rejected("60-naive-synthetic", "unknown jitter pattern", synthetic_pattern="wobbly")

    def test_ranges(self) -> None:
        self.assert_rejected("60-naive-typical", "from a smaller to a larger delay", noise=(MS, MS / 2))
        # The demo profile leaves some frames on time
        ft.validate(ft.parse_mode("60-naive-heavy"), ft.TimingParameters(demo_load_share=Fraction(99, 100)))
        self.assert_rejected("60-naive-heavy", "demo load share must be at least 0 and less than 1", demo_load_share=Fraction(1))
        with self.assertRaisesRegex(ValueError, "not a whole number of 30 Hz frames"):
            _ = frames("30", 481)


if __name__ == "__main__":
    _ = unittest.main()
