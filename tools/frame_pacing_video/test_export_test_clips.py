# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""Tests of export_test_clips.py: a folder per scenario with video.mp4 and its own manifest."""

import unittest
from typing import cast

import export_test_clips as export
import generate_videos as gv


class ClipManifestTests(unittest.TestCase):
    def test_every_scenario_is_a_marked_single_box_clip(self) -> None:
        clips = export.planned()
        self.assertEqual([job.top.name for _, job in clips], list(export.SCENARIOS))
        self.assertTrue(all(job.single and job.marker for _, job in clips))
        # Fast, except the device idling at 1 fps, which needs the idle speed's long rests
        speeds = {job.top.name: job.speed.name for _, job in clips}
        self.assertEqual({name for name, speed in speeds.items() if speed != "fast"}, {"60-idle-1fps"})
        self.assertEqual(speeds["60-idle-1fps"], "idle")
        self.assertEqual(len(clips), 22)
        # Every clip's start marker names it with a short text tag (its mode's name, or one of its own), never a UUID, each its own
        tags = [str(gv.marker_sequence_id(job.top)) for _, job in clips]
        # (a UUID shows as 36 characters)
        self.assertTrue(all(len(tag) <= 16 for tag in tags), tags)
        self.assertEqual(len(set(tags)), len(tags))
        self.assertEqual(set(gv.SEQUENCE_TAGS), {job.top.name for _, job in clips if len(job.top.name) > 16})

    def test_the_manifest_is_the_clips_own_named_after_the_folders_video(self) -> None:
        _, settings = gv.parse_arguments(["--single", "60-busy-adaptive", "--marker", "--speed", "fast"])
        manifest = export.clip_manifest(settings, gv.plan_videos(settings)[0])
        videos = cast(list[dict[str, object]], manifest["videos"])
        self.assertEqual(len(videos), 1)
        self.assertEqual((videos[0]["file"], videos[0]["measure"]), ("video.mp4", "mb-framepacing import video.mp4 --analyze -o analysis"))
        self.assertEqual(cast(dict[str, object], videos[0]["box"])["mode"], "60-busy-adaptive")
        self.assertTrue(cast(str, manifest["license"]).startswith("PolyForm Perimeter License 1.0.1"))


if __name__ == "__main__":
    _ = unittest.main()
