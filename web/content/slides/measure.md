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

## mb-framepacing: measured on the display

Made for developers, to check their own application on the real output and to automate the checks: its command line captures a
run from start to end, analyses it and writes the results as JSON and CSV, ready for a script to compare against a limit.

:::guide

:::card How it works

1. **Once: add the marker.** A small library (C++, C#, or a Unity package) draws a marker with the frame index and animation
   time as the last thing in every frame.
2. **Record:** a capture card records the display signal with its own clock, at the display's refresh rate (or import a video
   from a high-speed camera).
3. **Analyse:** it reads the marker back from every captured frame and compares the animation time with when the frame really
   appeared: animation error, display times, dropped and torn frames, as a GUI, CSV or JSON.

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

[PresentMon's columns](https://github.com/GameTechDev/PresentMon/blob/main/README-ConsoleApplication.md#csv-columns)
[mb-framepacing](https://github.com/Unarmed1000/mb-framepacing#readme)
[Integrating the marker](https://github.com/Unarmed1000/mb-framepacing/blob/master/doc/integrating.md)
[Measured in real games](https://github.com/Unarmed1000/mb-framepacing-explained/blob/master/doc/measured-errors.md)
{.more}
