# SPDX-FileCopyrightText: Copyright (C) 2026 Mana Battery ApS
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
"""Tests of generate_one_video.py: exactly one video of generate_videos.py."""

import json
import unittest
from pathlib import Path
from typing import cast

import generate_one_video as one

CLIPS = Path(__file__).resolve().parents[2] / "web" / "src" / "explain" / "clips.json"


class OneJobTests(unittest.TestCase):
    def test_the_follow_stack_is_one_video(self) -> None:
        _, settings, job = one.one_job(["--scene", "follow", "--follow-boxes", "60", "60-naive-2ms", "--labels"])
        self.assertEqual(job.scene, "follow")
        self.assertEqual([mode.name for mode in job.boxes], ["60", "60-naive-2ms"])
        self.assertEqual(settings.video_frame_count(job), 480)

    def test_more_than_one_video_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "select 6 videos"):
            _ = one.one_job(["--pairs", "60:60", "--speed", "all"])

    def test_the_web_pages_follow_video_is_one_video(self) -> None:
        clips = cast(dict[str, list[dict[str, object]]], json.loads(CLIPS.read_text(encoding="utf-8")))
        videos = [video for video in clips["rendered"] if video.get("generator") == "generate_one_video.py"]
        self.assertTrue(videos)
        for video in videos:
            with self.subTest(video["name"]):
                _ = one.one_job(cast(list[str], video["arguments"]))


if __name__ == "__main__":
    _ = unittest.main()
