# Showing frame pacing in charts

A video shows what animation error looks like; a chart next to it shows which frames caused it. This page collects how the
established tools and reviewers chart frame pacing, compares that with [mb-framepacing](https://github.com/Unarmed1000/mb-framepacing)
recommends a set for the web page with generated examples, and lists ideas for mb-framepacing. Sources are in
[further reading](further-reading.md#charts-and-tools).

## How others chart it

| Source                                                                                                                                  | Charts                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| --------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [Gamers Nexus](https://gamersnexus.net/gpus-gn-extras-cpus/problem-gpu-benchmarks-reality-vs-numbers-animation-error-methodology-white) | **Animation error as a signed scatter in frame order**: "The left axis shows animation error in ms, with deviations away from zero depending on whether frames showed up too soon or too late"; "The X-axis represents frames". Next to it a frametime plot and frame rate bars (average, 1 % and 0.1 % lows). Summaries: **error per frame** (sum of absolute errors / frames) and **percent error** (sum of absolute errors / run length), in absolute values, because "adding together all the positive and negative animation errors for a logging period will typically cancel out" |
| [PC Perspective / FCAT](https://pcper.com/2013/03/frame-rating-dissected-full-details-on-capture-based-graphics-performance-testing/4/) | Frame times per frame ("a 'wider' line or one with a lot of peaks and valleys indicates a lot more variance"), **observed FPS** (runts and drops removed), minimum FPS by percentile, and frame variance against the running average of the previous 20 frames. The [FCAT overlay](https://pcper.com/2013/03/frame-rating-dissected-full-details-on-capture-based-graphics-performance-testing/2/) draws a colour bar per frame into the image, so the captured video shows how long each frame was on screen                                                                            |
| [CapFrameX](https://github.com/CXWorld/CapFrameX)                                                                                       | Frametime graphs, FPS graphs and **L-shapes** (frame times sorted by percentile); a stutter share (frametimes above 2.5 × the average); the difference between consecutive frame times                                                                                                                                                                                                                                                                                                                                                                                                   |
| [Blur Busters TestUFO](https://testufo.com/stutter)                                                                                     | The same moving object switched between perfect motion, minor stutters and vsync frame rate halvings; an [animation time graph](https://testufo.com/animation-time-graph) whose frame-skip indicator flickers magenta and cyan unevenly when frames repeat or skip                                                                                                                                                                                                                                                                                                                       |
| [PresentMon](https://game.intel.com/us/intel-presentmon/)                                                                               | An overlay of "real-time performance charting that supports multi-line graphs and histograms", with percentiles and averages, for any metric, including `MsAnimationError`                                                                                                                                                                                                                                                                                                                                                                                                               |
| Digital Foundry                                                                                                                         | Frame rate and frame time graphs laid over the gameplay video, computed by comparing the captured output frame by frame rather than from the game's timing (as described by the RTSS developer on [Guru3D](https://forums.guru3d.com/threads/which-frametime-calculation-point-do-digital-foundry-use-in-their-works.453755/)); see [How We Measure Console Frame-Rate](https://www.youtube.com/watch?v=KVg19CbkXR4)                                                                                                                                                                     |

Intel's [animation error experiment app](https://github.com/GameTechDev/PresentMon/issues/580) is the closest to this repository:
a 2D shape panning across the screen to "observe effect on animation error metric vs. perceived 'smoothness' of animation".

## mb-framepacing

The Analyze page of mb-framepacing charts measured captures. Its Timeline puts four charts on one time axis: the animation
error per frame as signed bars, with a band for the error threshold (±1 ms); the display time step as held steps, red where a
frame was held too long; the share of late frames in the last 2 s; and a refresh strip. The other tabs show the error
distribution, the error by percentile (p95, p99, the same idea as an L-shape), the display time step distribution and the drift.
Headline tiles give Gamers Nexus's error per frame and percent error, the typical (p95) and worst error, the frames visibly off
and the late frames. See its [README](https://github.com/Unarmed1000/mb-framepacing#reading-the-results).

The clips here are exact, so their charts need no resolution band, and they are short (8 s) and made to be read frame by frame
next to the video, rather than summarised.

## Recommended for the web page

Every chart comes from the clip's `manifest.json`, which has four arrays per mode under `frames`:

| Chart                                                                              | Data                                                                        | Shows                                                                                          | After                        |
| ---------------------------------------------------------------------------------- | --------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- | ---------------------------- |
| **Animation error** per frame, signed bars around zero                             | `animationErrorMs`                                                          | Which frames are off, and which way                                                            | Gamers Nexus                 |
| **Display time step and animation time step** per frame, two lines on one ms scale | display time step: `refresh` differences × the refresh period; step: `dtMs` | The two ways animation error happens: even display with an uneven step, or the other way round | The two clocks               |
| **Refresh strip**: one cell per refresh, alternating colours per frame             | `refresh`                                                                   | The cadence at a glance: 1-1-1, 2-2-2, or an uneven mix                                        | FCAT overlay, TestUFO        |
| **Summary**: mean absolute error per frame                                         | `animationErrorMs`                                                          | One number to compare the top and bottom box                                                   | Gamers Nexus error per frame |

A playhead that follows the looping video ties them together: the frame on screen is the bar under the playhead. Put the grid lines
of the display time step chart at whole refreshes (16.7, 33.3, 50 ms at 60 Hz), because that is the grid a plain vsync display shows
frames on.

## Examples

These are mb-framepacing's own report cards, measured: each mode's 8 s clip at 60 Hz is rendered with the frame marker, and
mb-framepacing imports it as a capture card would see it and draws the card. The four recommended charts share one card: the
summary tiles, the animation error bars, the two clocks (the display time step, with the animation time step over it), and the
refresh strip of the first second. Every scale is shared within a chart, and the display side is always drawn next to the
animation side, the two things a first hand-made chart lacked.

The numbers are a measurement, so a clip of 480 frames has 479 display time steps: its first frame has none, because nothing was
shown before it. In the looping video on the page it follows the clip's last frame, so the page's own charts count one step more.

The naive timer under heavy load, as a demo (an error in most frames): the display is perfect, 16.7 ms on every frame and an even
refresh strip, while the animation time step jumps around it.

![Report card of 60-naive-heavy: a perfect 60 Hz display, 311 of 479 frames visibly off, animation errors up to 9.8 ms](images/report-60-naive-heavy.svg)

How often each error occurs, on a log scale: a peak within the ±1 ms threshold, and clusters around −4 and +4 ms that hold most of the frames.

![Animation error distribution of 60-naive-heavy: a peak at 0 and clusters around −4 and +4 ms](images/error-histogram-60-naive-heavy.svg)

The same load with its realistic rates: rare spikes, but the same kind of error.

![Report card of 60-naive-heavy-realistic: 61 frames visibly off, rare spikes up to 7.2 ms](images/report-60-naive-heavy-realistic.svg)

Light load: smaller errors, all around 1–2 ms.

![Report card of 60-naive-light: 227 frames visibly off, errors up to 2.4 ms](images/report-60-naive-light.svg)

Made by [`tools/timing_diagrams/generate_measured_charts.py`](../tools/timing_diagrams/generate_measured_charts.py), with the
mb-framepacing of the submodule `external/mb-framepacing` (it builds it with `dotnet build`, so it needs the .NET SDK). Any mode can
be measured: `python tools/timing_diagrams/generate_measured_charts.py 30-naive-typical 60-naive-4ms` (`--png` for bitmaps).

## Ideas for mb-framepacing

mb-framepacing already has most of these charts for measured captures, including a refresh strip, and Gamers Nexus's error per
frame and percent error. What it could add:

- **Synced playback.** It records the video, so a click on a spike in a chart could open that captured frame, and a playhead
  could follow the recording. No other tool can do this, because none of them keeps the capture.
- **A stutter share**, as in CapFrameX: the share of frames whose display time step is over 2.5 × the median.
- ~~**SVG export** of its charts~~: done. Its report cards are SVG, and the examples above are them.
