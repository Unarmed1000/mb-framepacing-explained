# The web page (planned)

Notes for the slide-style web page that will explain the topics with the videos live, including a blind test. Nothing here is
built yet.

## Videos only on the web page

The Markdown docs link to the videos' topics but do not embed them. GitHub's README renderer does not play looping video: a
`<video>` tag's `loop`, `autoplay` and `muted` attributes are stripped, and videos can only be attached as uploads of at most 10 MB
on a free plan, stored outside the repository
([GitHub: attaching files](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/attaching-files),
[community request](https://github.com/dear-github/dear-github/issues/389)). An animated GIF is no substitute: its frame delays
come in 10 ms steps, so it cannot show 60 Hz frame pacing at all. The web page, for example on GitHub Pages, plays them with a
normal looping `<video>` element.

## What the page must check

A page about frame pacing is only honest if the viewer's own display and browser do not add pacing errors or blur of their own.

- **60 Hz compatibility.** The clips are made at 60 fps. The page measures the display's refresh rate (the intervals between
  `requestAnimationFrame` callbacks, and `requestVideoFrameCallback` to check that each video frame is actually presented) and
  says so when the display is not a whole multiple of 60 Hz, for example 144 Hz or a VRR display running at another rate: there
  every clip judders, the perfect one too, and a comparison or blind test would be meaningless. It also notices dropped or
  repeated frames during playback.
- **Browser zoom and display scaling.** The clips must be shown at 1:1 device pixels (see the
  [tool's README](../tools/frame_pacing_video/README.md)): scaling blurs the sub-pixel steps they are meant to show. The page reads
  `window.devicePixelRatio` (browser zoom times the operating system's display scaling) and `visualViewport.scale` (pinch zoom),
  sizes each video at its pixel size divided by the ratio in CSS pixels, and asks the viewer to reset the zoom when it cannot be
  shown sharp, for example at 125 % scaling.

## Other notes

- **Web encoding.** The generated clips are lossless H.264 4:4:4, which browsers do not play. The page needs a transcode: H.264
  High 4:2:0 in `.mp4`, or VP9 / AV1 in `.webm`. The neutral gray palette was chosen to survive 4:2:0.
- **Size.** Git warns at 50 MiB per file, blocks files over 100 MiB and recommends repositories under 1 GB
  ([GitHub: large files](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)).
  The web clips are generated at build time or published as release assets, not committed.
- **Canvas instead of video** is worth trying for the blind test: drawing the boxes each refresh from the same timing data
  (`manifest.json`) avoids video decoding altogether and gives exact control of every refresh.
- **Charts next to the videos**, synced to playback: see [charts](charts.md).
