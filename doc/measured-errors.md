# Measured in real games

How large animation error and delta time jitter are in real games and engines, from published measurements, and how the videos'
simulated timers compare. The videos exaggerate on purpose so the difference can be seen; this page says by how much.

Every number below was found on the linked page and its quote checked against it (September 2026), except where a note says
otherwise. Numbers we derived ourselves are marked "our arithmetic". The research was AI-assisted (see the
[README](../README.md#about-the-research)).

## Animation error in games

Measured with PresentMon's animation error (Gamers Nexus call it simulation time error): the animation time step minus the display
time step, per frame. Gamers Nexus summarise a run as the average absolute error per frame, and as a percentage of the frame time.

| Game                          | Measured                                                                                         | Hardware                                        | Source                                                                                                                                                              |
| ----------------------------- | ------------------------------------------------------------------------------------------------ | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Far Cry 5                     | 0.13 ms per frame, 0.7 %: "the single card typically had well under 1ms"                         | One GTX 1080 Ti                                 | [Gamers Nexus white paper](https://gamersnexus.net/gpus-gn-extras-cpus/problem-gpu-benchmarks-reality-vs-numbers-animation-error-methodology-white) (2025-10-28)    |
| Far Cry 5                     | 2.31 ms per frame, 17.3 %: "frequently had 2-3ms of animation error per frame"                   | Two GTX 1080 Ti in SLI (multi-GPU microstutter) | same                                                                                                                                                                |
| Strange Brigade               | "2-3ms of positive or negative error on nearly every frame, only rarely approaching zero"        | Two GTX 1080 Ti in SLI                          | same                                                                                                                                                                |
| Borderlands 2                 | "an error-to-frametime ratio of 11.9% for the 980 and 1.8% for the 5080"                         | GTX 980 (GPU PhysX), RTX 5080                   | same                                                                                                                                                                |
| Dragon's Dogma 2              | "a potential for 45ms of animation error", with "the already noticeable frametime hitch of 58ms" | Not stated                                      | same                                                                                                                                                                |
| Crimson Desert, a healthy run | "rarely greater than 4ms" either way; "+/-4 ms" when frame times "spike to about 19 ms"          | RTX 5060 Ti                                     | [Gamers Nexus, Crimson Desert](https://gamersnexus.net/gpus-game-benchmarks-graphics-guides/crimson-desert-gpu-benchmarks-bugs-simulation-error-tests) (2026-04-01) |
| Crimson Desert                | "on nearly every GPU we tested the percent sim time error was between 2% and 3%"; RTX 5090 3.8 % | 1440p Ultra, many GPUs                          | same                                                                                                                                                                |
| Crimson Desert                | 11.9 %, and "consistently frames that deviate 30ms or more from zero"                            | GTX 1070                                        | same                                                                                                                                                                |
| Crimson Desert, worst stretch | "-82ms and +63ms" at a frame-time spike; "-39ms and up to 19ms" at a spike of only 26 ms         | RTX 5060 Ti                                     | same                                                                                                                                                                |

## Delta time jitter in engines

What the naive timer videos simulate: frames reach the screen evenly, but the measured frame time wobbles.

| Engine or game                | Measured                                                                                                                                        | Source                                                                                                                                                                                                       |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Unity, before 2020.2          | `Time.deltaTime` of 6.854, 7.423, 6.691, 6.707, 7.045, 7.346, 6.513 ms at a steady 144 Hz (6.944 ms frames): −0.43 to +0.48 ms (our arithmetic) | [Unity blog](https://unity.com/blog/engine-platform/fixing-time-deltatime-in-unity-2020-2-for-smoother-gameplay)                                                                                             |
| Unity, a forum measurement    | 0.01665795, 0.01681304, 0.01697999 s … at 60 Hz with vsync: "I don't get any wild variances here", about ±0.3 ms (our arithmetic)               | [Unity discussions](https://discussions.unity.com/t/time-deltatime-not-constant-vsync-camerafollow-and-jitter/639394) (Eric5h5)                                                                              |
| Unity, the same thread        | Rare outliers in a blank project at a constant 60 fps: "as low as 2ms and as high as 31ms", later "5ms and 34ms"                                | same (Zullar)                                                                                                                                                                                                |
| The Talos Principle (Croteam) | A shipped naive timer at a steady 60 Hz: "the frame time is 24.8ms", then "only 10.7ms": +8.1 ms, then −6.0 ms (our arithmetic)                 | [The Elusive Frame Timing](https://medium.com/@alen.ladavac/the-elusive-frame-timing-168f899aec92) (Alen Ladavac); Medium blocked the automated fetch, so the quotes were checked on a mirror of the article |

## Frames arriving late, for contrast

Shader compilation and traversal stutter is the other kind of error: a frame reaches the screen late (a hitch), not at the wrong
moment. It is far larger, and not simulated in the videos yet.

| Game             | Measured                                                                                                                  | Source                                                                                                                                                                   |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Dragon's Dogma 2 | "an excursion of about 750ms" (i3-12100F); "a frametime spike nearing 270ms, with regular spikes to 60ms" (Ryzen 5 5600X) | [Gamers Nexus, Dragon's Dogma 2](https://gamersnexus.net/game-benchmarks-graphics-guides/dragons-dogma-2-mess-gpu-cpu-benchmarks-bottlenecks-crashes)                    |
| Crimson Desert   | "jumping up to 691 ms" (RTX 5060 Ti, a bridge scene)                                                                      | [Gamers Nexus, Crimson Desert](https://gamersnexus.net/gpus-game-benchmarks-graphics-guides/crimson-desert-gpu-benchmarks-bugs-simulation-error-tests)                   |
| Elden Ring       | Shader compilation stutter "of up to 250 milliseconds"                                                                    | Digital Foundry, quoted second-hand [on Steam](https://steamcommunity.com/app/1245620/discussions/0/3183486320467701860); not checked against Digital Foundry's own page |
| Bloodborne       | Bad 30 fps pacing: frame times "between 16ms and 66ms"                                                                    | [Digital Foundry](https://www.digitalfoundry.net/articles/digitalfoundry-2015-bloodborne-performance-analysis)                                                           |

## The videos' timers, in the same terms

The simulated modes over an 8 s clip (our arithmetic, from the generator's timing data):

| Mode                                            | Average error per frame | Percent of frame time | Largest | Frames over 1 ms | Close to                                              |
| ----------------------------------------------- | ----------------------- | --------------------- | ------- | ---------------- | ----------------------------------------------------- |
| `60-naive-4ms` (mixed pattern)                  | 3.80 ms                 | 22.8 %                | 8.0 ms  | 82 %             | Worse than SLI microstutter                           |
| `60-naive-5ms` (random pattern, the warm-up)    | 4.13 ms                 | 24.8 %                | 10.0 ms | 99 %             | Croteam's +8.1 / −6.0 ms, on every frame              |
| `60-naive-4ms` (random pattern, the blind test) | 3.30 ms                 | 19.8 %                | 8.0 ms  | 93 %             | SLI microstutter (17.3 %)                             |
| `60-naive-heavy` (demo)                         | 2.62 ms                 | 15.7 %                | 9.8 ms  | 65 %             | Far Cry 5 in SLI (2.31 ms, 17.3 %)                    |
| `60-naive-typical` (demo)                       | 1.68 ms                 | 10.1 %                | 4.0 ms  | 56 %             | GTX 1070 and GTX 980 outliers (11.9 %)                |
| `60-naive-light` (demo)                         | 1.03 ms                 | 6.2 %                 | 2.4 ms  | 47 %             |                                                       |
| `60-naive-heavy-realistic`                      | 0.51 ms                 | 3.1 %                 | 7.2 ms  | 13 %             | Crimson Desert on most GPUs (2–3 %), RTX 5090 (3.8 %) |
| `30-naive-4ms` (random pattern)                 | 3.47 ms                 | 10.4 %                | 7.5 ms  | 94 %             |                                                       |

- **A healthy game** measures well under 1 ms per frame (Far Cry 5 on one GPU, 0.13 ms) or 2–3 % of the frame time: the
  realistic profile's level.
- **The demo loads and the ±4 ms window** are at the level of known-bad cases: multi-GPU microstutter and the outlier GPUs. That
  is deliberate: a difference visible in an 8 s clip.
- **The 4–8 ms spikes are real:** Crimson Desert's ±4 ms at small hitches, and Croteam's +8.1 / −6.0 ms from a shipped naive
  timer at a steady 60 Hz.
- **Plain engine timer noise is smaller**, about ±0.3–0.5 ms in Unity; errors of several milliseconds come from queueing and
  background load.
- **The worst measured errors (30–80 ms) come with frame-time hitches**, which the videos do not simulate yet (see the
  [roadmap](roadmap.md)).

## The blind test

The blind test's bad timer (`60-naive-4ms` with the random jitter pattern) goes wrong on 93 % of the frames,
and on at least 88 % in any 2 s of the clip (our arithmetic), because a viewer decides within a few seconds, not after watching
all 8 s. The size of each error, 3.3 ms on average and up to 8 ms, is within what games measure; how often it happens is harsher
than a typical game, but it has been measured: the SLI setups above had "2-3ms of animation error per frame" (Far Cry 5), "on
nearly every frame" (Strange Brigade), and Crimson Desert on a GTX 1070 had "a significant simulation time error value" on
"almost every frame". The warm-up goes further on purpose, so it is easy: a ±5 ms window, errors up to 10 ms on 99 % of the frames, about the worst
timer error measured (Croteam's +8.1 / −6.0 ms) on every frame. The test page says all this before it starts.

Not found: per-game animation error from Digital Foundry (their site blocked the automated fetch), CapFrameX (it reports average
and P99 animation error, but no published game values turned up), Intel's own presentations, Unreal, Godot and Android's Swappy.
