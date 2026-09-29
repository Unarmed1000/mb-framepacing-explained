# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""Tests of export_test_clips.py: a folder per scenario with video.mp4 and its own manifest."""

import unittest
from typing import cast

import export_test_clips as export
import generate_videos as gv


class ClipManifestTests(unittest.TestCase):
    def test_every_scenario_is_a_marked_single_box_clip(self) -> None:
        _, settings = gv.parse_arguments(["--single", *export.SCENARIOS, "--marker", "--speed", "fast"])
        jobs = gv.plan_videos(settings)
        self.assertEqual([job.top.name for job in jobs], list(export.SCENARIOS))
        self.assertTrue(all(job.single and job.marker for job in jobs))

    def test_the_manifest_is_the_clips_own_named_after_the_folders_video(self) -> None:
        _, settings = gv.parse_arguments(["--single", "60-busy-swappy", "--marker", "--speed", "fast"])
        manifest = export.clip_manifest(settings, gv.plan_videos(settings)[0])
        videos = cast(list[dict[str, object]], manifest["videos"])
        self.assertEqual(len(videos), 1)
        self.assertEqual((videos[0]["file"], videos[0]["measure"]), ("video.mp4", "mb-framepacing import video.mp4 --analyze -o analysis"))
        self.assertEqual(cast(dict[str, object], videos[0]["box"])["mode"], "60-busy-swappy")
        self.assertTrue(cast(str, manifest["license"]).startswith("PolyForm Perimeter License 1.0.1"))


if __name__ == "__main__":
    _ = unittest.main()
