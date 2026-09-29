---
title: Measuring it
eyebrow: Measure it yourself
---

# How to measure animation error

[Animation error](#/timer-jitter) needs two clocks for every frame: the moment it shows (its animation time) and when it reached
the screen (its display time). The ways to measure it differ in where they get each, and so in what they can catch.

## Ways to measure it

:::card

| Way                                                                                  | Needs                                                                | Animation time                                                                                   | Display time                                                                                                                         | Catches                                                 |
| ------------------------------------------------------------------------------------ | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------- |
| [**PresentMon**](https://github.com/GameTechDev/PresentMon), also as Intel's overlay | Any app on Windows, games included, nothing changed                  | Estimated: when the CPU starts the frame; exact when it sends Reflex, XeLL or Anti-Lag 2 markers | Estimated from software events                                                                                                       | Both causes, approximately                              |
| **The app's own log**                                                                | The source code, and the platform's presentation feedback            | Exact: the app knows it                                                                          | As the platform reports it (DXGI frame statistics, Vulkan present timing, Android's Choreographer, Wayland presentation-time, Metal) | Both causes                                             |
| [**mb-framepacing**](https://github.com/Unarmed1000/mb-framepacing)                  | The source code (a marker drawn into every frame) and a capture card | Exact: written into the frame                                                                    | Measured on the display signal                                                                                                       | Both causes, on the real output                         |
| **Capture or camera only**: an FCAT-style overlay, a high-speed camera               | Any app                                                              | None                                                                                             | Measured                                                                                                                             | Late and uneven frames only: blind to delta time jitter |

:::

## Reading a measurement

Look at the animation error next to the display time steps, frame by frame. A real measurement rarely shows one cause alone: below,
the perfect storm, both causes of stutter in one box, against a perfect 60 fps.

:::video pair fast 60 60-naive-5ms-diagram-slow-frames-every-1s frames

Top: perfect 60 fps, a flat display time step and no animation error. Bottom: the perfect storm, a naive timer that reads the clock up
to 5 ms early or late, and two frames in the middle of every move that miss their refresh.

:::

:::card What to look for

- **Error while the display time step stays flat,** as through most of the bottom lane: the frames reach the screen on time but show
  the wrong moment. That is [delta time jitter](#/timer-jitter), fixed by the [vsync timer](#/vsync-timer).
- **Error where the display time step jumps,** as in the middle of every move: frames reach the screen late, and the step
  rises to 33.3 ms where a frame is held. That is bad [frame pacing](#/slow-frames), and the next question is where the misses
  fall.
- **Where the misses fall:** single spikes, now and then, need the one miss handled; misses bunched into busy stretches, as on
  [adapting the rate](#/adapt-rate), call for a lower rate there or [a lower target](#/lower-target).
- **How small is 0:** an error within the measurement's resolution cannot be told from 0. For a capture that is one capture
  period: 2 ms at 500 fps.

:::

## mb-framepacing: measured on the display

Made for developers, to check their own application on the real output and to automate the checks: its command line captures a
run from start to end, analyses it and writes the results as JSON and CSV, ready for a script to compare against a limit.

**It is still pre-alpha:** its commands, output and results may change, so check the numbers before relying on them. {.note}

:::guide

:::card How it works

1. **Once: add the marker.** A small library (C++, C#, Python or a Unity package) draws a marker with the frame index and animation
   time as the last thing in every frame.
2. **Record:** a capture card records the display signal with its own clock, at the display's refresh rate (or import a video
   from a high-speed camera).
3. **Analyse:** it reads the marker back from every captured frame and compares the animation time with when the frame really
   appeared: animation error, display time steps, dropped and torn frames, as a GUI, CSV or JSON.

It needs the application's source code: it cannot measure an application you cannot rebuild. {.note}

:::

<figure class="screenshot">
  <a href="https://github.com/Unarmed1000/mb-framepacing#readme" target="_blank" rel="noopener">
    <img src="https://raw.githubusercontent.com/Unarmed1000/mb-framepacing/master/doc/images/gui-analysis.png" alt="The Analyze page of mb-framepacing: every presented frame, its animation error and the headline numbers" loading="lazy" />
  </a>
  <figcaption>The Analyze page: every presented frame, its animation error and the headline numbers (from the
    mb-framepacing repository).</figcaption>
</figure>

:::

Next: what mb-framepacing reports for each of its test clips, known problems measured from their videos.

[PresentMon's columns](https://github.com/GameTechDev/PresentMon/blob/main/README-ConsoleApplication.md#csv-columns)
[mb-framepacing](https://github.com/Unarmed1000/mb-framepacing#readme)
[Integrating the marker](https://github.com/Unarmed1000/mb-framepacing/blob/master/doc/integrating.md)
[Measured in real games](https://github.com/Unarmed1000/mb-framepacing-explained/blob/master/doc/measured-errors.md)
{.more}
