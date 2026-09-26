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
        self.assertEqual(sorted(pairs), ["fast", "normal"])
        # Slow: 3 identical pairs once, 6 other pairs in both orders; fast (no 20 Hz): 2 identical, 3 others, and the warm-up pair
        self.assertEqual(len(pairs["normal"]), 3 + 6 * 2)
        self.assertEqual(len(pairs["fast"]), 2 + 3 * 2 + 2)
        # 20 Hz only with the normal movement
        self.assertFalse([pair for pair in pairs["fast"] if "20" in pair])
        self.assertIn(("20", "30-naive-heavy"), pairs["normal"])
        self.assertNotIn(("20", "60-naive-heavy"), pairs["normal"])
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
