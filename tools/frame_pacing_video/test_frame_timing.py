# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""Tests of frame_timing.py, the simulated frame loop. Run from the repository root (in the .venv):
python -m unittest discover -s tools/frame_pacing_video -v
"""

import itertools
import unittest
from fractions import Fraction

import adaptive_rate
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
            ft.parse_mode("60-naive-5ms-every-1s"),
            ft.FrameMode("60-naive-5ms-every-1s", 60, ft.Timer.NAIVE, ft.Noise.WINDOW, 5 * MS, every=Fraction(1), burst=8),
        )
        self.assertEqual(ft.parse_mode("60-naive-5ms-24f-every-1s").burst, 24)
        for bad in ("60-naive-5ms-every-0s", "60-naive-5ms-24f", "60-naive-5ms-0f-every-1s", "60-naive-heavy-every-1s", "60-naive-synthetic-every-1s"):
            with self.assertRaisesRegex(ValueError, "is not a mode"):
                _ = ft.parse_mode(bad)
        self.assertEqual(
            ft.parse_mode("60-naive-typical-realistic"), ft.FrameMode("60-naive-typical-realistic", 60, ft.Timer.NAIVE, ft.Noise.TYPICAL, realistic=True)
        )
        bad_names = ("60-late", "60-naive", "naive-typical", "060", "60-naive-busy", "60-naive-0ms", "60-naive-ms", "60-realistic", "60-naive-1ms-realistic")
        for bad in (*bad_names, "60-naive-synthetic-realistic", "60-naive-typical-demo"):
            with self.assertRaisesRegex(ValueError, "is not a mode"):
                _ = ft.parse_mode(bad)

    def test_a_presentation_fault_ends_any_mode(self) -> None:
        storm = "60-naive-5ms-diagram-slow-frames-every-1s"
        for fault in ("dropped-frames", "out-of-order"):
            mode = ft.parse_mode(f"{storm}-{fault}")
            self.assertEqual(
                mode, ft.FrameMode(f"{storm}-{fault}", 60, ft.Timer.NAIVE, ft.Noise.WINDOW, 5 * MS, diagram="slow-frames", every=Fraction(1), fault=fault)
            )
            self.assertEqual(ft.parse_mode(f"60-{fault}"), ft.FrameMode(f"60-{fault}", 60, fault=fault))
            self.assertEqual(ft.parse_mode(f"60-diagram-slow-frames-{fault}").diagram, "slow-frames")
            self.assertEqual(ft.parse_mode(f"60-busy-swappy-{fault}").busy, "swappy")
        self.assertIsNone(ft.parse_mode(storm).fault)
        for bad in ("60-dropped", "60-out-of-order-dropped-frames", "60-dropped-frames-naive-1ms"):
            with self.assertRaisesRegex(ValueError, "is not a mode"):
                _ = ft.parse_mode(bad)

    def test_an_idle_behaviour_comes_before_a_fault(self) -> None:
        for idle in ("static-rests", "static-rests-paused-clock", "on-demand", "on-demand-paused-clock", "on-demand-paused-clock-hindsight", "idle-1fps"):
            self.assertEqual(ft.parse_mode(f"60-{idle}"), ft.FrameMode(f"60-{idle}", 60, idle=idle))
        mode = ft.parse_mode("60-naive-5ms-static-rests-dropped-frames")
        self.assertEqual((mode.noise, mode.window, mode.idle, mode.fault), (ft.Noise.WINDOW, 5 * MS, "static-rests", "dropped-frames"))
        self.assertEqual(ft.parse_mode("60-diagram-slow-frames-on-demand").diagram, "slow-frames")
        for bad in ("60-dropped-frames-on-demand", "60-idle", "60-on-demand-static-rests"):
            with self.assertRaisesRegex(ValueError, "is not a mode"):
                _ = ft.parse_mode(bad)
        self.assertEqual(
            ft.describe(ft.parse_mode("60-on-demand-paused-clock-out-of-order"), PARAMETERS),
            "60 Hz ideal timer, on demand, clock paused at rest, frames out of order",
        )
        self.assertEqual(ft.describe(ft.parse_mode("60-idle-1fps"), PARAMETERS), "60 Hz ideal timer, 1 fps at rest")
        mode = ft.parse_mode("60-on-demand-paused-clock-hindsight-dropped-before-wake")
        self.assertEqual((mode.idle, mode.fault), ("on-demand-paused-clock-hindsight", "dropped-before-wake"))
        self.assertEqual(ft.describe(mode, PARAMETERS), "60 Hz ideal timer, on demand, clock paused at rest, flagged on waking, a rest's frame dropped")
        mode = ft.parse_mode("60-on-demand-paused-clock-hindsight-dropped-wake")
        self.assertEqual((mode.idle, mode.fault), ("on-demand-paused-clock-hindsight", "dropped-wake"))
        self.assertTrue(ft.describe(mode, PARAMETERS).endswith("flagged on waking, a wake-up frame dropped"))
        mode = ft.parse_mode("60-on-demand-paused-clock-hindsight-dropped-after-stall")
        self.assertEqual((mode.idle, mode.fault), ("on-demand-paused-clock-hindsight", "dropped-after-stall"))
        self.assertTrue(ft.describe(mode, PARAMETERS).endswith("flagged on waking, a frame dropped after a stall"))

    def test_labels(self) -> None:
        self.assertEqual(ft.describe(ft.parse_mode("60-dropped-frames"), PARAMETERS), "60 Hz ideal timer, dropped frames")
        self.assertEqual(ft.describe(ft.parse_mode("60-naive-4ms-out-of-order"), PARAMETERS), "60 Hz naive timer, ±4 ms mixed, frames out of order")
        self.assertEqual(ft.describe(ft.parse_mode("60"), PARAMETERS), "60 Hz ideal timer")
        self.assertEqual(ft.describe(ft.parse_mode("30-naive-typical"), PARAMETERS), "30 Hz naive timer, typical load")
        self.assertEqual(ft.describe(ft.parse_mode("60-naive-heavy-realistic"), PARAMETERS), "60 Hz naive timer, heavy load (realistic)")
        self.assertEqual(ft.describe(ft.parse_mode("60-naive-4ms"), PARAMETERS), "60 Hz naive timer, ±4 ms mixed")
        self.assertEqual(ft.describe(ft.parse_mode("60-naive-5ms-every-1s"), PARAMETERS), "60 Hz naive timer, ±5 ms mixed, 8 frames every 1 s")
        self.assertEqual(ft.describe(ft.parse_mode("60-naive-5ms-24f-every-1s"), PARAMETERS), "60 Hz naive timer, ±5 ms mixed, 24 frames every 1 s")
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

    def test_every_frame_starts_before_it_is_flipped_and_after_the_one_before(self) -> None:
        names = ("60", "30", "60-naive-heavy", "60-naive-5ms", "60-diagram-half-rate-bad-pacing", "60-busy-full-rate", "60-busy-swappy")
        for name in (*names, "60-naive-5ms-diagram-slow-frames-every-1s"):
            simulated = frames(name)
            self.assertEqual(len(simulated.starts), len(simulated.flips), name)
            self.assertTrue(all(a <= b for a, b in itertools.pairwise(simulated.starts)), name)
            self.assertTrue(all(start < Fraction(flip, 60) for start, flip in zip(simulated.starts, simulated.flips, strict=True)), name)
            # The first frame starts during the loop before the clip
            self.assertLess(simulated.starts[0], 0, name)

    def test_the_timer_loop_starts_a_frame_when_it_reads_the_clock(self) -> None:
        for name in ("60", "30-naive-typical", "60-naive-4ms"):
            simulated = frames(name)
            self.assertEqual(simulated.starts, simulated.samples, name)
        # The ideal timer reads the clock at the previous flip
        self.assertEqual(frames("30").starts[:3], (-2 * FRAME, Fraction(0), 2 * FRAME))

    def test_a_busy_frame_starts_when_the_previous_one_is_shown(self) -> None:
        for name in ("60-busy-full-rate", "60-busy-swappy"):
            simulated = frames(name)
            self.assertEqual(simulated.starts[1:], tuple(Fraction(flip, 60) for flip in simulated.flips[:-1]), name)
            # The first frame starts when the last frame of the pass before the clip is shown
            before = [record for record in adaptive_rate.with_lead(name.removeprefix("60-busy-"), CLIP, Fraction(60)) if record.shown < 0]
            self.assertEqual(simulated.starts[0], Fraction(before[-1].shown, 60), name)
            # Its CPU time is its render time; it is shown at the first refresh it targets once it is done
            records = adaptive_rate.records(name.removeprefix("60-busy-"), CLIP, Fraction(60))
            self.assertEqual(simulated.cpu, tuple(Fraction(record.render_ms) / 1000 for record in records), name)
            for start, cpu, flip, record in zip(simulated.starts, simulated.cpu, simulated.flips, records, strict=True):
                self.assertGreater(cpu, 0, name)
                self.assertLessEqual(start + cpu, Fraction(flip, 60), name)
                if record.missed:
                    # Too late for the refresh before
                    self.assertGreater(start + cpu, Fraction(flip - 1, 60), name)

    def test_a_diagram_frame_starts_at_the_previous_flip(self) -> None:
        for name in ("60-diagram-slow-frames", "60-diagram-half-rate-even", "60-naive-5ms-diagram-slow-frames-every-1s"):
            simulated = frames(name)
            self.assertEqual(simulated.starts[1:], tuple(Fraction(flip, 60) for flip in simulated.flips[:-1]), name)
            self.assertEqual(simulated.starts[0], Fraction(simulated.flips[-1] - CLIP, 60), name)

    def test_a_capped_diagram_starts_its_frames_by_the_games_own_clock(self) -> None:
        # Half rate, bad frame pacing: a frame every 2 refreshes by the game's clock, 0.2 refreshes into one, rendering 0.75 and
        # 1.3 refreshes; so an even frame time of 2 refreshes while the frames are held 3 and 1
        simulated = frames("60-diagram-half-rate-bad-pacing")
        self.assertEqual(simulated.starts[:4], tuple(Fraction(start, 600) for start in (-8, 12, 32, 52)))
        self.assertEqual(simulated.cpu[:4], (Fraction(3, 4) * FRAME, Fraction(13, 10) * FRAME) * 2)
        self.assertEqual({b - a for a, b in itertools.pairwise(simulated.starts)}, {2 * FRAME})

    def test_a_diagram_frame_takes_the_diagrams_render_time(self) -> None:
        # Slow frames, the whole diagram once a second: A to F render 0.75, 1.25, 0.75, 0.75, 1.25 and 0.75 refreshes; the on-time
        # frames around them have no known render time
        simulated = frames("60-diagram-slow-frames-every-1s")
        known = [(flip, cpu) for flip, cpu in zip(simulated.flips, simulated.cpu, strict=True) if cpu > 0]
        self.assertEqual(len(known), 6 * 8)
        self.assertEqual(
            [cpu / FRAME for _, cpu in known[:6]], [Fraction(3, 4), Fraction(5, 4), Fraction(3, 4), Fraction(3, 4), Fraction(5, 4), Fraction(3, 4)]
        )
        for name in ("60-diagram-slow-frames-every-1s", "60-diagram-half-rate-even", "60-naive-5ms-diagram-slow-frames-every-1s"):
            simulated = frames(name)
            # Done before the refresh it is shown on, and too late for the one before when it is held
            for start, cpu, flip in zip(simulated.starts, simulated.cpu, simulated.flips, strict=True):
                self.assertLessEqual(start + cpu, Fraction(flip, 60), name)

    def test_the_timer_loop_renders_for_the_frame_cost(self) -> None:
        for name, frame_time in (("60", FRAME), ("30", 2 * FRAME), ("60-naive-5ms", FRAME), ("60-naive-heavy", FRAME)):
            simulated = frames(name)
            self.assertEqual(set(simulated.cpu), {PARAMETERS.frame_cost * frame_time}, name)
            # Every frame is done before its vsync
            self.assertTrue(
                all(start + cpu < Fraction(flip, 60) for start, cpu, flip in zip(simulated.starts, simulated.cpu, simulated.flips, strict=True)), name
            )

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

    def test_the_demo_profile_is_as_busy_at_the_end_as_at_the_start(self) -> None:
        # No spells: consecutive frames are no more alike in the second half than in the first (a spell would repeat its range and
        # direction, and hide its error between its ends)
        def kind(offset: Fraction) -> tuple[int, bool]:
            size = 0 if abs(offset) <= Fraction(3, 10) * MS else 1 if abs(offset) <= Fraction(12, 10) * MS else 2 if abs(offset) <= 2 * MS else 3
            return size, offset > 0

        for name in ("60-naive-light", "60-naive-typical", "60-naive-heavy"):
            offsets = self.offsets(name)

            def alike(part: list[Fraction]) -> float:
                return sum(kind(a) == kind(b) for a, b in itertools.pairwise(part)) / (len(part) - 1)

            self.assertAlmostEqual(alike(offsets[:30000]), alike(offsets[30000:]), delta=0.02, msg=name)

    def test_the_demo_profile_shows_its_largest_range_in_the_first_2_s(self) -> None:
        def spike_early(name: str, count: int, parameters: ft.TimingParameters = PARAMETERS) -> bool:
            mode = ft.parse_mode(name)
            offsets = self.offsets(name, count, parameters)
            return any(4 * MS <= offset <= 8 * MS for offset in offsets[: 2 * mode.rate])

        # Every clip length at 60, 30 and 20 Hz (8 s is 480, 240 and 160 frames)
        for name, count in (("60-naive-heavy", 480), ("30-naive-heavy", 240), ("20-naive-heavy", 160), ("60-naive-heavy", 60)):
            self.assertTrue(spike_early(name, count), (name, count))
        # Also when spikes are so rare that the draws put none there: one frame there gets one, and only one
        rare = ft.TimingParameters(demo_load_share=Fraction(1, 100))
        for count in (480, 1000, 5000):
            self.assertTrue(spike_early("60-naive-heavy", count, rare), count)
        offsets = self.offsets("60-naive-heavy", 480, rare)
        self.assertEqual(sum(4 * MS <= offset <= 8 * MS for offset in offsets[:120]), 1)

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

    def test_bursts_jitter_the_middle_of_every_period_only(self) -> None:
        parameters = ft.TimingParameters(synthetic_pattern="random")
        simulated = frames("60-naive-5ms-every-1s", parameters=parameters)
        errors = [a - Fraction(index, 60) for index, a in enumerate(simulated.animation)]
        # Eight frames in the middle of every second (the box mid-move), each off by the pattern; every other frame exact
        bursts = [second * 60 + 26 + index for second in range(8) for index in range(8)]
        self.assertLessEqual({index for index, error in enumerate(errors) if error}, set(bursts))
        self.assertEqual([errors[index] for index in bursts], [5 * MS * offset for offset in ft.jitter_offsets(60, 64, "random")])
        self.assertEqual(max(abs(error) for error in errors), 5 * MS)
        # A longer burst, still centred
        longer = frames("60-naive-5ms-24f-every-1s", parameters=parameters)
        errors = [a - Fraction(index, 60) for index, a in enumerate(longer.animation)]
        self.assertLessEqual({index for index, error in enumerate(errors) if error}, {second * 60 + 18 + index for second in range(8) for index in range(24)})
        for bad in ("60-naive-5ms-every-3s", "60-naive-5ms-61f-every-1s"):
            with self.assertRaisesRegex(ValueError, "does not fit"):
                _ = frames(bad, parameters=parameters)

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
