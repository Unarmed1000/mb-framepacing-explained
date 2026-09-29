# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""Tests of pcg32.py. Run from the repository root (in the .venv):
python -m unittest discover -s tools/frame_pacing_video -v
"""

import unittest

from pcg32 import Pcg32


class Pcg32Tests(unittest.TestCase):
    def test_reference_output(self) -> None:
        # pcg32-demo (pcg-random.org): pcg32_srandom_r(&rng, 42, 54), then six pcg32_random_r
        generator = Pcg32(42, 54)
        self.assertEqual([generator.next_u32() for _ in range(6)], [0xA15C02B7, 0x7B47F409, 0xBA1D3330, 0x83D2F293, 0xBFA4784B, 0xCBED606E])

    def test_seeded_from_a_text(self) -> None:
        first, again, other = (
            Pcg32.from_text("wake-up typical, 60 Hz, 480 frames"),
            Pcg32.from_text("wake-up typical, 60 Hz, 480 frames"),
            Pcg32.from_text("wake-up typical, 60 Hz, 240 frames"),
        )
        draws = [first.next_u32() for _ in range(8)]
        self.assertEqual(draws, [again.next_u32() for _ in range(8)])
        self.assertNotEqual(draws, [other.next_u32() for _ in range(8)])

    def test_randint_covers_the_range_evenly(self) -> None:
        generator = Pcg32(1, 2)
        counts = [0] * 7
        for _ in range(70000):
            counts[generator.randint(-3, 3) + 3] += 1
        self.assertTrue(all(9500 < count < 10500 for count in counts), counts)
        self.assertEqual({generator.randint(5, 5) for _ in range(10)}, {5})
        with self.assertRaisesRegex(ValueError, "randint needs 1 to 2\\^32 values"):
            _ = generator.randint(3, 2)

    def test_random_and_choice(self) -> None:
        generator = Pcg32(3, 4)
        values = [generator.random() for _ in range(10000)]
        self.assertTrue(all(0 <= value < 1 for value in values))
        self.assertAlmostEqual(sum(values) / len(values), 0.5, delta=0.02)
        self.assertEqual({generator.choice((1, -1)) for _ in range(100)}, {1, -1})


if __name__ == "__main__":
    _ = unittest.main()
