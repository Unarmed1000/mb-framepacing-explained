# Frame pacing comparison videos

`generate_videos.py` makes short looping 1280×720 videos that show what animation error looks like. Every video is 8 s long.
Two kinds of scene:

- **Side by side** (`box`, `row`): the **top** half is updated with one timing mode, the **bottom** half with another, and a thin
  divider with faded ends separates them. At the `normal` and `fast` speeds each half shows a box that moves side to side along
  the same eased path; at the `ui` speeds each half is a row of identical boxes, like a list in an interface, that scrolls right to
  left at constant speed, fading in and out at the frame edges. With `--scene row` the `normal` and `fast` clips show a row too,
  paging one page (4 boxes) to the left and back.
- **Follow camera** (`--scene follow`): a stack of boxes, each with its own mode, between two fixed lines, with a camera that
  follows the ideal motion, so a timing error is the only thing that moves a box. See [Follow camera](#follow-camera).

The moving scene is drawn in [virtual pixels](#virtual-pixels), so it can be shown on a coarser pixel grid. The terms follow Intel
PresentMon and the Gamers Nexus animation error methodology; the [repository README](../../README.md#vocabulary) maps them to their
other names.

## How timing is simulated

The timing comes from [`frame_timing.py`](frame_timing.py), which simulates a game's frame loop on a **plain vsync display**, the
old-school way: there are no presentation timestamps and no API that says when a frame was shown. The game blocks in `Present`
and reads its own clock:

```text
loop:
    Present(previous frame)   blocks until that frame is flipped on screen at a vsync (double buffering)
    (work: input, OS messages)
    now = wall clock          a high-precision timer, read when the thread gets there: a little after the flip
    dt  = now - last          the naive timer
    x  += speed * dt          move the animation
    render                    always fits in the frame time here: every frame makes its vsync
    Present(frame)            shown at the next allowed vsync, every 1, 2 or 3 refreshes (60, 30, 20 Hz at 60 fps)
```

Every frame is shown at an exact **display time** (a vsync). What differs is the **animation time** it shows, which depends on the
timer:

- **Ideal** (`60`, `30`, `20`): the animation time is exactly the display time, what a perfect, display-matched timer would give.
  The reference; its animation error is always 0.
- **Naive** (`60-naive-…`): the animation time is the wall clock reading. A constant delay after the flip is only latency and cannot
  be seen, so each frame is off by how much sooner or later than usual its clock was read, ahead or behind. `dt = now − last` is
  the frame time plus the difference between two of those delays. Moving by `x += speed * dt` gives exactly the same positions as
  `x = speed × animation time`: the errors do not build up, because every dt ends where the next one starts.

How much sooner or later than usual the naive loop reads the clock:

| Mode                           | Clock read                                                                                                             | Label                                               |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| `60-naive-light` …             | **System load**, as a demo: a timing error in 95 % of the frames (`--demo-load-share`), all about 1 ms sooner or later | 60 Hz naive timer, light load                       |
| `60-naive-typical` …           | Half about 1 ms, half up to 2 ms                                                                                       | 60 Hz naive timer, typical load                     |
| `60-naive-heavy` …             | 90 % up to 2 ms, 10 % spikes of 4–8 ms, always late                                                                    | 60 Hz naive timer, heavy load                       |
| `60-naive-light-realistic` …   | **Realistic** system load, an idle system: in 3 % of the frames about 1 ms, in 1 % up to 2 ms                          | 60 Hz naive timer, light load (realistic)           |
| `60-naive-typical-realistic` … | A normal gaming PC: 7 % about 1 ms, 2 % up to 2 ms                                                                     | 60 Hz naive timer, typical load (realistic)         |
| `60-naive-heavy-realistic` …   | Background load: 12 % about 1 ms, 6 % up to 2 ms, and in 2 % spikes of 4–8 ms                                          | 60 Hz naive timer, heavy load (realistic)           |
| `60-naive-1ms` … `-4ms` …      | **A ±N ms window** (any size, e.g. `60-naive-2.5ms`), following the jitter pattern (`--jitter-pattern`)                | 60 Hz naive timer, ±1 ms mixed                      |
| `60-naive-5ms-32f-every-1s` …  | **The window in bursts** (see below): 32 frames in the middle of every second, the frames between exact                | 60 Hz naive timer, ±5 ms mixed, 32 frames every 1 s |
| `60-naive-synthetic` …         | The jitter pattern within ±1 ms (`--jitter-ms`), for teaching the metric                                               | 60 Hz naive timer, synthetic ±1 ms mixed            |
| `60-diagram-slow-frames` …     | **A timing diagram, replayed** (see below)                                                                             | 60 Hz, slow frames (as the diagram)                 |

- **System load:** the clock is read after the frame's first work (input, OS messages), usually about 2 ms plus 0–0.3 ms of noise
  (`--noise-ms`); that constant part is latency. How late the thread gets there depends on what else runs: background work,
  driver interrupts, power states. The ~1 ms and ~2 ms reads go either way (the work can also be shorter than usual); the heavy
  spikes are always late, as CPU contention only delays. In the demo profile every frame is drawn on its own for the whole clip,
  and its largest reads (heavy: a spike) always occur within the first 2 s. In the realistic profile the **first half** of a clip
  has single longer reads; in the **second half** they come in **spells** of 3–10 frames in a row, while something else keeps
  using the CPU, with the same share of longer reads in both halves. (A spell's error only shows at its ends, which is why the demo
  profile has none: its second half would look much lighter.) Unity measured 6.854, 7.423 and 6.691 ms at a steady
  144 Hz, whose frames are 6.944 ms.
- **The window in bursts** (`RATE-naive-Nms-Kf-every-Ss`, e.g. `60-naive-5ms-32f-every-1s`): only K frames in the middle of every
  S seconds read the clock off its average, following the jitter pattern; every other frame is exact. At the fast speed a move
  takes a second, so the jitter falls where the box moves fastest and shows most. Without `-Kf` a burst is 8 frames, as many as
  the delta time jitter diagram shows.
- **Timing diagrams, replayed** (`RATE-diagram-NAME`, e.g. `60-diagram-slow-frames`, `60-diagram-half-rate-bad-pacing`): the
  frames of one of the [timing diagrams](../timing_diagrams) exactly as the diagram shows them, when each is shown and which
  animation time it shows, with one diagram refresh per frame of the mode's rate.
  The diagram is reduced to its smallest repeating unit (slow frames: a frame on time, one a refresh late, the one that catches
  up), repeated back to back; when it does not divide the clip, on-time frames at full rate fill each repetition. `-every-Ns`
  repeats it only every N seconds, with on-time frames between (`60-diagram-slow-frames-every-1s`). Every diagram at a fixed
  refresh rate can be replayed: `perfect-timer`, `timer-jitter`, `slow-frames`, `half-rate-even`, `half-rate-bad-pacing`,
  `switching-naive`, `switching-hysteresis`, `recovery-half-rate`, `recovery-targeting`. The VRR diagram cannot: its frames
  appear between refreshes, which needs a much finer video (about 240 fps) and a display to match.
- **The perfect storm** (`RATE-naive-Nms-diagram-NAME…`, e.g. `60-naive-5ms-diagram-slow-frames-every-1s`): a replayed diagram
  and the naive timer's ±N ms window at once. The frames are flipped as the diagram shows them, late ones included, and every
  frame's animation time is off by its clock reading, as in a real measurement where both causes of stutter mix.
- **Demo and realistic loads:** realistically only 4, 9 and 20 % of the frames have a timing error, too rare to find in a short
  video. So by default the loads are a **demo profile**: a timing error in **95 % of the frames** (`--demo-load-share`). A load is
  really about how bad the errors get, so the loads differ in size rather than in how often: light only about 1 ms, typical also
  up to 2 ms, heavy also the 4–8 ms spikes. `-realistic` (e.g. `60-naive-heavy-realistic`) gives the realistic rates.
- **Jitter patterns** (the ±N ms windows and synthetic): `mixed` (default) goes through `alternating`, `runs`, `random`, `runs`, a
  quarter of the clip each; `alternating` flips between +N and −N every frame (the largest animation error: twice N on every
  frame); `runs` stays on one side for 4–10 frames, then on the other; `random` is anywhere in ±N. Consecutive errors always
  differ, so no step is exactly the frame time, and the largest is exactly ±N. The windows share one pattern, scaled.
- **Rendering always fits** (`--frame-cost`, the rendering work as a share of the frame time, 0.3): together with the latest clock
  read it must fit in the frame time, so every frame makes its vsync. Late frames, catch-up, frame limiters and other timers (fixed
  dt, dt smoothing, dt snapping, a fixed-step accumulator) are not simulated yet; the timer module is built so they can be added.
- **Deterministic:** the random draws come from our own generator, [`pcg32.py`](pcg32.py) (PCG32, the XSH RR 64/32 generator of
  [pcg-random.org](https://www.pcg-random.org)), seeded from the SHA-256 of a text naming the mode and clip length. The same clip
  always gets the same timing, in any Python version, and the draws can be reproduced in any language. Every clip loops: the frame
  after the last is the first frame of the next loop.
- **Sub-pixel motion:** the edge columns of each box are blended by how much the box covers them (per virtual pixel), so even small
  errors show and a perfect box is not made uneven by rounding to whole pixels.

Sources: [Fixing Time.deltaTime in Unity 2020.2](https://unity.com/blog/engine-platform/fixing-time-deltatime-in-unity-2020-2-for-smoother-gameplay)
(Unity), [The Elusive Frame Timing](https://medium.com/@alen.ladavac/the-elusive-frame-timing-168f899aec92) (Alen Ladavac,
Croteam, [GDC 2018](https://www.gdcvault.com/play/1025407/Advanced-Graphics-Techniques-Tutorial-The)),
[Frame Pacing library](https://developer.android.com/games/sdk/frame-pacing) (Android),
[Swapchains and frame pacing](https://raphlinus.github.io/ui/graphics/gpu/2021/10/22/swapchain-frame-pacing.html) (Raph Levien).
For the timers to come: [How to make your game run at 60fps](https://medium.com/@tglaiel/how-to-make-your-game-run-at-60fps-24c61210fe75)
(Tyler Glaiel, dt snapping), [Fix Your Timestep!](https://gafferongames.com/post/fix_your_timestep/) (Gaffer On Games),
[Time Delta Smoothing](https://frankforce.com/frame-rate-delta-buffering/) (Frank Force).

## Speeds

Every clip is 8 s (480 frames at 60 fps, `--seconds`), so every video shows the jitter profiles the same way: 2 s per part of the
mixed pattern, and for the realistic loads 4 s each of single longer reads and spells.

| Speed    | Scene | Motion                                                                       | Like                                                |
| -------- | ----- | ---------------------------------------------------------------------------- | --------------------------------------------------- |
| `normal` | box   | 2 round trips of 4 s: 4 box spacings in 1.9 s, eased, 0.1 s rest at each end | A slow pan: subtle effects are easiest to follow    |
| `fast`   | box   | 4 round trips of 2 s: 4 box spacings in 0.9 s                                | A quicker pan: more pixel error for the same timing |
| `slow`   | box   | As `normal` on a quarter of the path (1 box spacing), centred; not in `all`  | Small, slow movement, where 20 fps holds up best    |
| `ui-192` | row   | Scrolls right to left at a constant 192 virtual px/s                         | A slow drag                                         |
| `ui-288` | row   | 288 virtual px/s                                                             | Scrolling a list                                    |
| `ui-384` | row   | 384 virtual px/s                                                             | Holding a key in a list                             |
| `ui-768` | row   | 768 virtual px/s                                                             | A fast fling                                        |

- **`slow`** is opt-in (`--speed slow`): the normal timing on a shorter path (`--slow-travel`), for low frame rates such as 20 fps.
- **`normal` and `fast`** fit whole round trips (there and back) in the clip (`--normal-round-trips`, `--fast-round-trips`), eased
  in and out (sine) at both ends. A clip starts and ends in the middle of the first rest, so it loops seamlessly.
- **The ui speeds** show interface motion: the row never stops, so every timing error is visible for the whole clip, and there is
  no easing to hide it. Their speed is in virtual pixels per second, so 1 ms of timing error moves the row 0.19, 0.29, 0.38 or
  0.77 virtual px. A clip loops seamlessly because the row repeats every box spacing and scrolls a whole number of spacings per clip.
  `--ui-scroll` picks other speeds.
- **The default run** makes every top/bottom pair of the nine modes `60`, `30`, `20` (the ideal timer) and `60`, `30` with the
  loads `-naive-light`, `-naive-typical` and `-naive-heavy`, at all six speeds: **486 videos** (81 per speed). The
  realistic loads, 20 Hz under load, the ±N ms windows and `-naive-synthetic` are opt-in with `--top` / `--bottom`.

## Virtual pixels

`--pixel-size N` lays out and draws the moving scene in **virtual pixels** of N×N video pixels, on a fixed grid: **2×2 by default**,
so a timing error moves a box in steps a viewer on a large screen can see. The video stays 1280×720; the scene's canvas is 1280/N × 720/N virtual pixels (rounded up; a partial virtual pixel at the sides is cropped, so any
N works).

- **The layout follows the canvas**, so the scene keeps its proportions at every grid size: the box is 2/15 of the canvas height,
  the spacing twice the box, the travel 4 spacings and the gap to the divider half a box. `--box-size`, `--box-spacing`,
  `--travel` and `--box-gap` override them, in virtual pixels.
- **Motion is in virtual pixels**, with sub-pixel blending per virtual pixel. The ui scroll speeds are in virtual px/s, so on a
  coarser grid the same speed moves N times as many video pixels, and so does every timing error: 1 ms at `ui-384` moves the row
  0.38 video px at N = 1, 0.77 at N = 2 and 1.5 at N = 4. (`normal` and `fast` are timed per round trip, so they move the same share of
  the canvas at every N.)
- **The divider, labels and follow lines are drawn at native 1:1 video pixels**, so they stay sharp on any grid.

| `--pixel-size` | Canvas   | Box | Spacing | `ui-384` in video px/s    |
| -------------- | -------- | --- | ------- | ------------------------- |
| 1              | 1280×720 | 96  | 192     | 384 (2 items per second)  |
| 2 (default)    | 640×360  | 48  | 96      | 768 (4 items per second)  |
| 4              | 320×180  | 24  | 48      | 1536 (8 items per second) |

## Follow camera

`--scene follow` is a different setup, after the slow motion demo in Unity's
[Fixing Time.deltaTime in Unity 2020.2 for smoother gameplay](https://unity.com/blog/engine-platform/fixing-time-deltatime-in-unity-2020-2-for-smoother-gameplay):
a stack of boxes in the middle of the screen, each with its own mode, between two fixed red lines that mark where a perfectly
timed box stays. The camera follows the ideal motion, so the ideal box stands completely still and a timing error is the only
thing that moves a box: it leaves the lines, ahead or behind.

- **Three videos by default**, each 8 s:
  - `follow_eighth-width-per-frame.mp4`: the system loads, `60` (ideal), `60-naive-light`, `60-naive-typical`, `60-naive-heavy`;
  - `follow-realistic_eighth-width-per-frame.mp4`: the realistic loads, `60`, `60-naive-light-realistic`, `-typical-realistic`,
    `-heavy-realistic`;
  - `follow-extreme_eighth-width-per-frame.mp4`: the extreme cases, `60`, `60-naive-1ms`, `-2ms`, `-3ms`, `-4ms`, too much to watch
    for most people next to the others.

  `--follow-boxes MODE…` makes one video with that stack instead.

- **Speed:** the boxes move an eighth of the width per frame (160 px at 1280 wide, 9600 px/s), an illustration speed that makes
  1 ms of timing error about 10 px (3.75 times the speed of Unity's demo, which moves twice the width per second). `--speed`
  picks another speed.
- **Real speed.** `--slow-motion N [N …]` adds slowed down copies, in every scene (e.g. `--slow-motion 1 10`: real speed and 10
  times slower, in `follow-labels-slow10/…`), so each step can be followed by eye. The timing data in the manifest stays in real time.
- **One rate per video**, like a game: the camera is updated at the stack's rate, following the ideal motion at that rate, so an
  ideal box always stands still. Boxes of different rates are rejected: against a camera moving at another rate, a perfect box
  would judder.
- **Drawing:** the boxes in virtual pixels (`--pixel-size`), in front of the lines; the lines and labels at native 1:1 video pixels.
  The labels start right of the furthest any box swings.

The web page's appendix shows one follow video, the realistic loads at 480 px high (`follow-jitter` in
[`web/src/explain/clips.json`](../../web/src/explain/clips.json)). `generate_one_video.py [options] --output FILE` makes it: exactly one
video of this tool into a given file, as the page's other video generators do.

## Single box and the frame marker

`--single MODE…` makes one video per mode instead of top/bottom pairs: the box alone, halfway down the frame, without the divider
(`single_fast_60-naive-5ms.mp4`, in `box-single/…`). The manifest gives each video one `box` instead of `top` and `bottom`.

`--marker` adds [mb-framepacing](https://github.com/Unarmed1000/mb-framepacing)'s frame marker to those videos, so mb-framepacing can
import them and measure their animation error, and its numbers can be checked against the generator's. They go to
`box-single-marker/…`, apart from the web page's clips.

- **What it carries:** at every refresh, the index of the frame on screen (a held frame keeps its index, so mb-framepacing sees one
  presented frame), the animation time it shows, and the frame pacer's plan for it: its intended display time (the refresh it was
  rendered for, on a clock whose 0 is the clip's first refresh) and the target frame time (its swap interval: 166 667 ticks at
  60 fps, 333 333 at 30), all in 100 ns ticks; run id 1. The index counts on across loops; the manifest's `markerFirstFrameIndex`
  is the clip's first frame.
- **Start and end:** 3 refreshes of start marker before the clip (named after the mode, cut to the marker's 60 bytes) and 3 of end
  marker after it, showing the previous and next loop's frames. The measured run is then exactly the clip, and the video 6
  refreshes longer; it no longer loops seamlessly.
- **Where:** mb-framepacing's recommended place, 32 px from the top-left corner, left of the box's path, in pure black and white,
  modules of `--marker-module-px` video pixels (3; 2 is enough lossless, `--web` needs 3).
- **The library:** `mb_framemarker/`, a copy of mb-framepacing's Python marker library (`marker/python`, BSD 3-Clause, its
  `LICENSE` inside). It draws the same pixels as mb-framepacing's C++ and C# libraries; its tests check that against
  mb-framepacing's golden images when they are found (`MB_FRAMEMARKER_TEST_DATA`, or a `test-data/markers` folder above), and are
  skipped otherwise. Update it by copying the folder from mb-framepacing.

The page's scenarios as marked clips, then measured and compared, clip by clip:

```powershell
.venv\Scripts\python tools/frame_pacing_video/generate_videos.py --single 60 30 60-naive-5ms 60-diagram-slow-frames-every-1s `
  60-diagram-half-rate-even 60-diagram-half-rate-bad-pacing 60-busy-full-rate 60-busy-swappy `
  60-naive-5ms-diagram-slow-frames-every-1s --marker --speed fast
cd out/frame_pacing_video/box-single-marker/fast
mb-framepacing import single_fast_60-naive-5ms.mp4 --analyze -o single_fast_60-naive-5ms   # as the manifest's "measure" says
python ../../../../tools/frame_pacing_video/check_marker_run.py manifest.json single_fast_60-naive-5ms.mp4 single_fast_60-naive-5ms/analysis
```

`check_marker_run.py` checks that every frame of the clip was presented and that mb-framepacing's animation error of each frame is
the manifest's `animationErrorMs` (within 0.01 ms). Every one of the clips above agrees: the numbers behind the web page's charts are
what mb-framepacing measures.

`export_test_clips.py --output-dir DIR` makes the same scenarios for mb-framepacing's tests (its `test-data/videos`): a folder per
scenario, named after its mode, with `video.mp4` and its own `manifest.json`, 4 MB in all. These copies are licensed for
mb-framepacing under its PolyForm Perimeter License 1.0.1, like its other test data (the manifest's `license`); this repository's own
videos stay CC BY-NC-SA 4.0.

## Setup

From the repository root:

```powershell
setup.cmd --ffmpeg D:\path\to\ffmpeg          # Windows
./setup.sh --ffmpeg /path/to/ffmpeg           # Linux, macOS
```

This creates `.venv` with Python 3.14, installs Pillow, Ruff and basedpyright, writes `local.toml` and checks FFmpeg. It is safe
to run again; `--ffmpeg` is optional.

Manual equivalent, run from the repository root:

```powershell
py -3.14 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install --group dev
copy local.example.toml local.toml               # then set [ffmpeg] path
```

### FFmpeg

FFmpeg is an external program; it is never bundled. The build needs the `libx264` encoder: the Gyan builds have it
(`winget install Gyan.FFmpeg`), as do most Linux and Homebrew packages.

The tool looks for FFmpeg in this order, the same as [mb-framepacing](https://github.com/Unarmed1000/mb-framepacing):

1. `--ffmpeg <file or folder>`
2. the `MB_FFMPEG` environment variable
3. `local.toml` in the repository root (or `--config <file>`), under `[ffmpeg] path`. The value can be `ffmpeg.exe` itself or a
   folder that holds it directly or in `bin`:
   ```toml
   [ffmpeg]
   path = 'D:\win_apps\ffmpeg-2026-03-15-git-6ba0b59d8b-full_build'
   ```
4. `PATH`

A source that is set but does not point to FFmpeg is an error, not skipped. `--check-ffmpeg` shows which FFmpeg is used and whether
it can encode lossless H.264. `ffprobe` is only needed by the tests and is taken from the same folder.

## Usage

Run in the `.venv`:

```powershell
python tools/frame_pacing_video/generate_videos.py                       # all 486 side by side videos
python tools/frame_pacing_video/generate_videos.py --speed normal        # 81 videos
python tools/frame_pacing_video/generate_videos.py --speed ui            # 324 videos: every ui scroll speed
python tools/frame_pacing_video/generate_videos.py --top 60 --bottom 60-naive-typical 60-naive-1ms --speed ui-384 normal --labels
python tools/frame_pacing_video/generate_videos.py --scene follow --labels                 # the two follow videos, 1x and 10x slower
python tools/frame_pacing_video/generate_videos.py --scene row --speed normal             # rows of boxes paging
python tools/frame_pacing_video/generate_videos.py --pixel-size 4 --speed ui-384 --labels  # on a 4 × 4 virtual pixel grid
```

| Option                   | Default                   | Meaning                                                                                                                                          |
| ------------------------ | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `--output-dir DIR`       | `out/frame_pacing_video`  | Where the group folders go (see [Output](#output)). `out/` is git-ignored.                                                                       |
| `--top MODE…`            | the nine default modes    | Modes of the top box or row: `RATE` (ideal timer) or `RATE-naive-NOISE`, NOISE `light`, `typical`, `heavy`, a window like `1ms`, or `synthetic`. |
| `--bottom MODE…`         | the nine default modes    | Modes of the bottom box or row.                                                                                                                  |
| `--speed SPEED…`         | `all`                     | `normal`, `fast`, `slow`, a ui speed (`ui-384`), `ui` (every ui speed) or `all` (all but `slow`). The follow scene's default is its own speed.   |
| `--labels`               | off                       | Writes each box's mode next to it ("60 Hz naive timer, typical load").                                                                           |
| `--width`, `--height`    | 1280 × 720                | Video size in video pixels.                                                                                                                      |
| `--pixel-size`           | 2                         | Virtual pixel size: the moving scene is laid out and drawn in N×N blocks (see [Virtual pixels](#virtual-pixels)).                                |
| `--fps`                  | 60                        | Output frame rate: a whole multiple of every selected rate. Numbers like `120` or `60000/1001`.                                                  |
| `--seconds`              | 8                         | Every clip's length; the jitter profiles are laid out over it.                                                                                   |
| `--normal-round-trips`   | 2                         | Round trips per clip of the `normal` videos (more is faster).                                                                                    |
| `--fast-round-trips`     | 4                         | Round trips per clip of the `fast` videos.                                                                                                       |
| `--slow-travel`          | a quarter of the travel   | Virtual pixels the box travels at the `slow` speed (the normal timing, on a shorter centred path).                                               |
| `--settle`               | 0.25                      | Seconds the box rests at each end, at `normal` and `fast`.                                                                                       |
| `--no-easing`            | off                       | Constant speed instead of the sine ease-in-out.                                                                                                  |
| `--ui-scroll VPX_PER_S…` | 192 384 768               | Virtual pixels per second of each ui scroll speed; each is named by it (`480` makes `ui-480`).                                                   |
| `--noise-ms FROM TO`     | 0 0.3                     | Naive timer under system load: the usual noise on the clock read (ms).                                                                           |
| `--frame-cost`           | 0.3                       | Rendering work as a share of the frame time; with the latest clock read it must fit, so every frame makes its vsync.                             |
| `--demo-load-share`      | 0.95                      | The loads' demo profile: the share of frames that read the clock late or early (`-realistic`: 0.04, 0.09, 0.2).                                  |
| `--jitter-pattern`       | `mixed`                   | The jitter pattern of the ±N ms windows and synthetic noise: `mixed`, `alternating`, `runs` or `random`.                                         |
| `--jitter-ms`            | 1                         | Synthetic noise (`RATE-naive-synthetic`): the amount (±). Must stay below half a frame.                                                          |
| `--scene`                | `box`                     | At `normal` and `fast`: `box` or `row`; the ui speeds always scroll a row. `follow`: the [follow camera](#follow-camera).                        |
| `--follow-boxes MODE…`   | the two default videos    | Follow scene: one video with this stack of boxes, top to bottom, all of one rate.                                                                |
| `--slow-motion N…`       | 1                         | Shows every refresh for N video frames, one video per factor.                                                                                    |
| `--single MODE…`         |                           | One video per mode instead of pairs: the box alone ([single box](#single-box-and-the-frame-marker)).                                             |
| `--marker`               | off                       | With `--single`: mb-framepacing's frame marker in every frame, so mb-framepacing can measure the video.                                          |
| `--marker-module-px`     | 3                         | `--marker`: video pixels per marker module (at least 2, 3 with `--web`).                                                                         |
| `--box-size`             | 2/15 of the canvas height | Box width and height in virtual pixels (96 at pixel size 1, 24 at 4).                                                                            |
| `--box-spacing`          | twice the box size        | Virtual pixels from one box of a row to the next.                                                                                                |
| `--travel`               | 4 × the spacing           | Virtual pixels the box travels (its path is centred), or a row moves per page, at `normal` and `fast`.                                           |
| `--box-gap`              | half the box size         | Virtual pixels between each box or row and the divider.                                                                                          |
| `--background`           | `#585858`                 | Background colour: a name or `#RRGGBB`.                                                                                                          |
| `--box-color`            | `#A8A8A8`                 | Box colour.                                                                                                                                      |
| `--no-divider`           | off                       | Leaves out the divider line.                                                                                                                     |
| `--divider-color`        | `#707070`                 | Divider colour; it fades in from the background over the first and last tenth of the width.                                                      |
| `--label-color`          | `#C8C8C8`                 | Label text colour.                                                                                                                               |
| `--line-color`           | `#D04848`                 | Follow scene: the lines marking where a perfectly timed box stays.                                                                               |
| `--ffmpeg PATH`          |                           | FFmpeg executable or its folder (see [FFmpeg](#ffmpeg)).                                                                                         |
| `--config FILE`          | `local.toml`              | Machine-local settings file.                                                                                                                     |
| `--preview-png`          | off                       | Also saves each video's first frame as a PNG.                                                                                                    |
| `--check-ffmpeg`         |                           | Only reports which FFmpeg is used and whether it can encode lossless H.264.                                                                      |

### Colours

The defaults are neutral grays: background 48, box 208, divider 80, labels 200. They are chosen to look the same on LCD
(IPS, TN, VA) and OLED displays:

- **Neutral gray** carries no colour information, so the edges stay clean when the clips are later converted to web video with
  half-resolution colour (4:2:0).
- **Away from black and white.** LCD overdrive cannot push a transition past 0 or 255, near-black transitions are the slowest on
  VA panels (black smear), and some OLEDs smear or flicker near black; 48 and 208 leave room at both ends. They also stay inside
  the 16–235 range of re-encoded web video, so nothing clips.
- **Clear contrast** (about 8.5:1), so the box edges are crisp and a one or two pixel error is easy to see. On OLED a dark
  background with small bright boxes also avoids the automatic dimming of large bright areas.

### Settings that are rejected

Settings that would break the loop or the pacing are rejected with an error; nothing is silently adjusted:

- every clip must be a whole number of output frames and of updates for every selected mode;
- the frame rate must be a whole multiple of every selected rate, so every mode is evenly paced;
- every frame must make its vsync: the latest clock read plus the rendering work (`--frame-cost`) must fit in the frame time;
- synthetic noise must stay below half a frame interval;
- the round trips must fit the clip with the rest at both ends;
- a ui scroll must move a whole number of box spacings per clip;
- a follow video's boxes must share one rate and fit above each other;
- `--marker` needs `--single`, real speed (no `--slow-motion`), the box scene, and room for the marker (49 modules, the same for every main marker) in the frame
  and left of the box's path;
- the boxes must fit the height, a single box and its travel the canvas width, and the box spacing must be larger than the box
  size.

## Output

- **Folders**: every run writes into group folders, `{scene}/{speed}/` under the output folder, with `-labels` added to the scene
  when `--labels` is used, `-px4` on a 4×4 virtual pixel grid, `-slow10` in slow motion and `-alternating` / `-runs` / `-random`
  for a single synthetic pattern: `box/fast/`, `row/ui-384/`, `follow-labels-slow10/eighth-width-per-frame/`. Runs with other
  settings of these do not overwrite each other.
- **Videos**: `{speed}_top-{mode}_bottom-{mode}.mp4`, for example `box/fast/fast_top-60_bottom-30-naive-4ms.mp4`; `row_…` for a
  row; `follow_{speed}.mp4`, `follow-realistic_{speed}.mp4` and `follow-extreme_{speed}.mp4` in the follow scene; the same variants as the folder at the end
  (`_px4`, `_slow10`, …). Names stay unique when the folders are merged.
- **`manifest.json`**, one per folder: the settings (including the clip length, `pixelSize`, the `canvas` and the layout in virtual
  pixels) and, for each video in the folder:
  - file name, scene, speed (round trips, or scroll speed in virtual px/s), move and rest time, round trip, duration, fps, frame
    count, slow motion factor and video frame count, and size;
  - for the top and the bottom half (or each box of the follow stack): the mode, its timer, noise and window, its label, and
    **every frame of the clip**: the output refresh it is flipped on (`frames.refresh`), when the naive loop read the clock
    (`frames.sampleMs`, the first frame is shown at 0), the animation time it shows (`frames.animationMs`, the clip's first
    refresh is 0; the marker carries the same in ticks), the dt its animation advanced by (`frames.dtMs`) and its **animation
    error** in ms (`frames.animationErrorMs`), computed like PresentMon's `MsAnimationError`: positive = shown too soon,
    negative = shown too late, and how many refreshes after the one it was rendered for it is flipped (`frames.late`, 0 on
    time; the naive timer's frames are always on time), and the rate the game aims for while showing it (`frames.targetFps`:
    the refresh rate divided by the swap interval it is paced at; `targetFps` of the mode at full speed, which Swappy's rule
    lowers through its busy stretch). The first frame follows the last one of the previous loop. A web page can draw the dt and
    error graphs next to the video from it.
  - the licence of the videos (`license`): this repository's, CC BY-NC-SA 4.0.
- **Encoding**: lossless H.264 (`libx264 -qp 0`, High 4:4:4 Predictive profile) in YUV 4:4:4, tagged BT.709. Standard YUV rather
  than `libx264rgb`, because players that ignore the RGB tag show RGB streams in false colours. H.264 itself is lossless; the
  RGB-to-YUV conversion reproduces the background and boxes exactly and moves in-between grays (edges, text) by at most one step.
  If FFmpeg is missing, lacks the encoder or fails, the tool stops with an error; it never falls back to lossy encoding.

**Viewing:** browsers and many default players cannot play lossless H.264. Use `ffplay -loop 0 <file>` (next to `ffmpeg`), VLC or
mpv. A later tool will convert the clips for the web. **Show them at native size** (1:1 pixels): scaling blurs the steps the
videos are meant to show.

## Render scale and upscaler videos

`generate_render_scale_video.py` makes the page's appendix videos: rotating, textured 3D objects rendered with OpenGL (moderngl,
headless) at a lower render scale and scaled up, with the HUD and UI at the output resolution. Its patterns follow the dynamic
resolution model, jump between scales, hold a fixed scale (`fixed`), or compare a plain bilinear upscale with AMD's FSR 1
(`fsr`, from the MIT-licensed headers in [`fsr1/`](fsr1)). The page's build renders the ones it uses (`rendered` in
`web/src/explain/clips.json`).

`generate_upscaler_artifacts.py` makes the artifact slide's videos: the same renderer with a simple temporal upscaler of our own
(jitter, motion vectors, a depth check, a clamped history), set up per artifact to show ghosting, disocclusion, blur in motion,
flicker and soft transparent edges, exaggerated, next to the scene as it should look. It is not DLSS or FSR. The page's build
renders these too (`generator` in the `rendered` list).

It needs OpenGL 3.3, and **FSR 1 needs OpenGL 4.3, which macOS does not have: the `fsr` pattern cannot be generated on macOS**
at the moment. Windows and Linux (on a build server through Mesa's EGL) have both.

## Tests

```powershell
.venv\Scripts\python -m unittest discover -s tools/frame_pacing_video -v
```

- `test_pcg32.py`: the generator against PCG32's reference output, seeding from a text, even `randint`, `random` and `choice`.
- `test_frame_timing.py`: the ideal and naive timers, every frame making its vsync, `x += speed * dt` matching the positions, the
  system loads (shares of longer reads in both halves, both directions, spikes only late, the demo profile as busy at the end as at
  the start with its largest reads in the first 2 s, the realistic one single frames then spells), the windows
  and synthetic noise, the jitter patterns at every clip length, determinism and validation.
- `test_generate_videos.py`: the video plan, the timing of every mode, the 8 s clips and seamless loops, the easing and rest, the ui
  speeds, validation, rendering (rows, sub-pixel edges, edge fade, divider, labels, colours, virtual pixel grids and the layout per
  grid size), the follow scene (videos, one rate, boxes in front of the lines, labels clear of the swing, slow motion, loops) and
  the FFmpeg lookup. An encode test (skipped without FFmpeg) makes a small clip and checks with ffprobe that it is H.264 High
  4:4:4 Predictive at 60 fps with the right size and frame count, and that its decoded frames match the rendered ones. The single
  box and the marker: one video per mode, the payload of every refresh (held frames, the start and end markers), the marker drawn
  into every frame, its name, the manifest and the validation.
- `test_check_marker_run.py`: comparing mb-framepacing's measurement with the manifest.
- `test_export_test_clips.py`: the scenarios as marked single-box clips, each with its own manifest.
- `mb_framemarker/tests`: the marker library: payload layout and round trips, sizes and placement, and the golden images of
  mb-framepacing (module matrices of 512 payloads, 40 images through quads, triangles and indexed triangles).
