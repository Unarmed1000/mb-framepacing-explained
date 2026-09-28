---
title: The usual numbers
eyebrow: Stutter at a steady frame rate
---

# Perfect numbers, uneven motion

Smoothness is usually judged by the frame rate, and for a closer look by the frame times: how long each frame stays on screen.
The two boxes below score perfectly on both, and one of them still stutters.

:::video pair fast 60 60-naive-5ms nochart frames nomodes

The two display time step charts, how long each frame stays on screen, are identical: both boxes at 60 fps, every frame on screen for
exactly one refresh, 16.7 ms. Yet the bottom box moves less smoothly.

:::

:::card What the numbers say

| Number                 | Top                  | Bottom               |
| ---------------------- | -------------------- | -------------------- |
| **Average frame rate** | 60 fps               | 60 fps               |
| **1 % lows**           | 60 fps               | 60 fps               |
| **Frame time**         | 16.7 ms, every frame | 16.7 ms, every frame |
| **Display time step**  | 16.7 ms, every frame | 16.7 ms, every frame |
| **Motion**             | Smooth               | Uneven               |

Frame time, as an overlay shows it, is the time between two frames the game hands over; the display time step, as PresentMon
(`MsBetweenDisplayChange`) and mb-framepacing measure it, is how long each one stays on screen. With every frame on time the
two are the same. {.note}

Each of these numbers counts frames or times them. None of them looks at what each frame shows, and that
is where the bottom box goes wrong. The next slide adds the number that does: **animation error**. {.note}

:::
