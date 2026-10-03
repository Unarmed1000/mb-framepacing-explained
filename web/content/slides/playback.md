---
title: Playing it back
eyebrow: Measure it yourself
---

# See the stutter where the numbers say it is

A report says where the animation error is; the recording shows what it looked like. mb-framepacing's playback report puts the two
side by side: the recording a capture was imported from plays next to the run's report card, with a playhead on every panel at the
frame on screen.

<figure class="live-embed">
  <iframe src="playback/60-busy-adaptive/index.html#t=2.05" title="mb-framepacing's playback report of the test clip 60-busy-adaptive" loading="lazy"></iframe>
  <figcaption>Live: mb-framepacing's playback report of the test clip 60-busy-adaptive, opened at its busy stretch. Play it,
    step it, or click a panel. <a href="playback/60-busy-adaptive/index.html#t=2.05" target="_blank" rel="noopener">Open it on its
    own</a></figcaption>
</figure>

**Photosensitivity:** the video shows mb-framepacing's marker, a small black-and-white pattern that changes every frame, and
flickering patterns can trigger seizures in people with photosensitive epilepsy. At this size it is within the
[guideline for flashing content](https://github.com/Unarmed1000/mb-framepacing/blob/master/sdk/doc/integrating.md#photosensitivity),
which lowers the risk and does not remove it. The video plays only when you press play. {.note}

:::guide

:::card What it does

- **Play it slowly:** play and pause, step one video frame or one application frame at a time, at 1×, ½×, ¼× or ⅛× speed. The
  scrubber marks the late frames.
- **Follow it on the report:** every panel shows the frame on screen as a playhead and band. Click or drag on a panel to go to that
  moment.
- **Read the frame on screen:** its frame index, video frame, display time, display time step and animation error, and whether it
  was late, static, skipped or uncertain.
- **Share a moment:** a link ending in `#t=12.345` opens the page at that moment.

:::

:::card How to get it

It is written only when you ask for it: while importing a recording, or later for an analysed import (here 5 s of it):

```sh
mb-framepacing import recording.mkv --display-hz 60 --playback
mb-framepacing render <capture folder> --playback --from 120 --to 125
```

In the GUI: **Save playback page** on the Analyze page, then **Open playback page**.

- **One folder per report,** `analysis/playback/run-<id>/`: a single HTML page, its video and `playback.json`. It runs from the
  disk in any current browser, with no server and nothing from the network, so the folder can be zipped and sent on.
- **Recordings a browser cannot play** (lossless, 4:4:4, HEVC, MKV) get a playable copy if you agree. Every frame keeps its
  timestamp.

It needs a capture imported from a video file: the page finds each frame by the video's own timestamps. {.note}

:::

:::

Every test clip on the next slides is such a video, so each one can be played back next to its report.

[The playback page](https://github.com/Unarmed1000/mb-framepacing/blob/master/measure/doc/usage.md#the-playback-page)
[mb-framepacing](https://github.com/Unarmed1000/mb-framepacing#readme)
{.more}
