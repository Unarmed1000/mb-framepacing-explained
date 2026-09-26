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
        # Normal and fast: 2 identical pairs once and 3 other pairs in both orders (at fast the warm-up pair is also the pacing
        # question's)
        self.assertEqual(len(pairs["normal"]), 2 + 3 * 2)
        self.assertEqual(len(pairs["fast"]), 2 + 3 * 2)
        # No 20 fps
        self.assertFalse([pair for motion_pairs in pairs.values() for pair in motion_pairs if "20" in pair])
        self.assertIn(("60", "60-naive-4ms"), pairs["fast"])
        self.assertIn(("60-naive-4ms", "60"), pairs["fast"])
        # Every bad timer is the ±4 ms one (errors on nearly every frame, so a viewer sees them within seconds), never a load
        bad = {mode for motion_pairs in pairs.values() for pair in motion_pairs for mode in pair if "naive" in mode}
        self.assertEqual(bad, {"60-naive-4ms"})
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
