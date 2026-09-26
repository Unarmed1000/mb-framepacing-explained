"""Tests of the blind test's clip export: the pairs it asks the video tool for."""

import json
import unittest
from pathlib import Path
from typing import cast

import build_blind_test as export


class PairTests(unittest.TestCase):
    def test_pairs_of_the_real_definitions(self) -> None:
        definitions = cast(dict[str, object], json.loads(export.TRIALS.read_text(encoding="utf-8")))
        pairs = export.required_pairs(definitions)
        self.assertEqual(sorted(pairs), ["fast", "normal", "slow"])
        # Normal and fast (no 20 Hz): 2 identical pairs once, 3 other pairs in both orders, and at fast the warm-up pair; slow (20 Hz
        # only, on a shorter path): 1 identical pair and 3 others
        self.assertEqual(len(pairs["normal"]), 2 + 3 * 2)
        self.assertEqual(len(pairs["fast"]), 2 + 3 * 2 + 2)
        self.assertEqual(len(pairs["slow"]), 1 + 3 * 2)
        # 20 Hz only with the slow movement
        self.assertFalse([pair for pair in pairs["fast"] + pairs["normal"] if "20" in pair])
        self.assertTrue(all("20" in pair for pair in pairs["slow"]))
        self.assertIn(("20", "30-naive-heavy"), pairs["slow"])
        self.assertNotIn(("20", "60-naive-heavy"), pairs["slow"])
        self.assertIn(("60", "60-naive-4ms"), pairs["fast"])
        self.assertIn(("60-naive-4ms", "60"), pairs["fast"])
        self.assertNotIn(("60", "60-naive-4ms"), pairs["normal"])
        self.assertEqual(pairs["normal"].count(("60", "60")), 1)
        # Never two bad timers
        self.assertFalse([pair for pair in pairs["normal"] if all("naive" in mode for mode in pair)])

    def test_generator_command(self) -> None:
        command = export.generator_command("fast", [("60", "30"), ("30", "60")], ["--web"], Path("out"), None)
        self.assertEqual(command[2:], ["--web", "--speed", "fast", "--output-dir", "out", "--pairs", "60:30", "30:60"])
        with_ffmpeg = export.generator_command("fast", [("60", "30")], ["--web"], Path("out"), "D:/ffmpeg")
        self.assertEqual(with_ffmpeg[-2:], ["--ffmpeg", "D:/ffmpeg"])


if __name__ == "__main__":
    _ = unittest.main()
